#define _USE_MATH_DEFINES

#include <ctype.h>
#include <math.h>
#include <time.h>
#include "common.h"

/***********************************************************************************/


static Value concatenate(Value *args) {
	args[0] = force(args[0]);
	args[1] = force(args[1]);
	String *dst = new_String(AS_STRING(args[0])->length + AS_STRING(args[1])->length);
	// Allocation took place: Refresh pointers.
	String *a = AS_STRING(args[0]);
	String *b = AS_STRING(args[1]);
	memcpy(dst->text, a->text, a->length);
	memcpy(dst->text + a->length, b->text, b->length);
	return GC_VAL(intern_String(dst));
}

static Value clock_native(Value *args) {
	return NUMBER_VAL((double)clock() / CLOCKS_PER_SEC);
}

static double fib(double n) {
	// Just a baseline for a certain micro-benchmark
	return n < 2 ? n : fib(n - 1) + fib(n - 2);
}

static Value fib_native(Value *args) {
	return NUMBER_VAL(fib(AS_NUMBER(force(args[0]))));
}

static Value abs_native(Value *args) {
	return NUMBER_VAL(fabs(AS_NUMBER(force(args[0]))));
}

static Value sqrt_native(Value *args) {
	return NUMBER_VAL(sqrt(AS_NUMBER(force(args[0]))));
}

static Value int_native(Value *args) {
	return NUMBER_VAL(trunc(AS_NUMBER(force(args[0]))));
}

static Value floor_native(Value *args) {
	return NUMBER_VAL(floor(AS_NUMBER(force(args[0]))));
}

static Value val_native(Value *args) {
	const char *text = AS_STRING(force(args[0]))->text;
	// This is hinkey, but it will have to do for now.
	// Ideally recognize Sophie-format numbers specifically (e.g. with underscores)
	// and leave out the other wacky formats C recognizes.
	// (Can always expose strtod more directly.)
	while (isspace(*text)) text++; // Skip leading whitespace...
	char *end = NULL;
	double d = strtod(text, &end);
	if (end == text) return vm.maybe_nope;
	while (isspace(*end)) end++; // Skip trailing whitespace...
	if (*end) return vm.maybe_nope;  // Reject trailing junk.
	if (isnan(d)) return vm.maybe_nope;  // Reject NaN input because it's not a number.
	else {
		push(NUMBER_VAL(d));
		push(vm.maybe_this);
		return GC_VAL(construct_record());
	}
}

static Value len_native(Value *args) {
	String *str = AS_STRING(force(args[0]));
	return NUMBER_VAL((double)(str->length));
}

static Value chr_native(Value *args) {
	args[0] = force(args[0]);
	String *dst = new_String(1);
	dst->text[0] = (byte)(AS_NUMBER(args[0]));
	return GC_VAL(intern_String(dst));
}

static Value mid_native(Value *args) {
	// Force the arguments, which are all needed:
	for (int i = 0; i < 3; i++) args[i] = force(args[i]);

	// Figure which part of the input string to copy
	size_t offset = (size_t)max(0, AS_NUMBER(args[1]));
	size_t len_arg = (size_t)max(0, AS_NUMBER(args[2]));
	size_t limit = AS_STRING(args[0])->length - offset;
	size_t actual_len = min(limit, len_arg);

	// Allocate the string
	String *dst = new_String(actual_len);
	memcpy(dst->text, AS_STRING(args[0])->text + offset, actual_len);
	return GC_VAL(intern_String(dst));
}

static Value str_native(Value *args) {
	double value = AS_NUMBER(force(args[0]));
	size_t len = snprintf(NULL, 0, NUMBER_FORMAT, value);
	String *dst = new_String(len);
	snprintf(dst->text, len+1, NUMBER_FORMAT, value);
	return GC_VAL(intern_String(dst));
}

/***********************************************************************************/

static Value console_echo(Value *args) {
	// Expect args[1] to be a (thunk of a) list of strings.
	// (Eventually I'll cure the thunking problem.)

	for (;;) {
		if (IS_THUNK(args[1])) args[1] = force(args[1]);
		if (IS_ENUM(args[1])) break;
		String *item = AS_STRING(force(AS_RECORD(args[1])->fields[0]));
		fputs(item->text, stdout);
		args[1] = AS_RECORD(args[1])->fields[1];
	}

	return NIL_VAL;
}

static Value console_read(Value *args) {
	/*
	Read a line of text from the console as a string,
	and send it as the parameter to a given message.

	Arbitrary-length input is rather a puzzle in C.
	Short-term, I'll cheat and use a fixed-size buffer with fgets.
	Later on, perhaps I build a list of chunks.
	*/
	static char buffer[1024];
	fgets(buffer, sizeof(buffer), stdin);
	push_C_string(buffer);
	push(args[1]);
	apply_bound_method();
	enqueue_message(pop());
	return NIL_VAL;
}

static Value console_random(Value *args) {
	/*
	Similar to console_read, but less stringy.
	Standard randomness in C is also problematic.
	It will do for the moment,
	but some day a better default random number generator would be nice.
	*/
	args[0] = NUMBER_VAL((double)rand() / RAND_MAX);
	apply_bound_method();
	enqueue_message(pop());
	return NIL_VAL;
}

/***********************************************************************************/

static void display_native(Native *native) { printf("<fn %s>", native->name->text); }

static void blacken_native(Native *native) { darken_in_place(&native->name); }

static size_t size_native(Native *native) { return sizeof(Native); }

GC_Kind KIND_Native = {
	.display = display_native,
	.deeply = display_native,
	.blacken = blacken_native,
	.size = size_native,
};

static void create_native(const char *name, byte arity, NativeFn function) {  // ( -- Native )
	push_C_string(name);
	Native *native = gc_allocate(&KIND_Native, sizeof(Native));
	native->arity = arity;
	native->function = function;
	native->name = AS_STRING(TOP);
	TOP = NATIVE_VAL(native);
}

static void install_native() {
	push(GC_VAL(AS_NATIVE(TOP)->name));
	defineGlobal();
}

static void defineNative(const char *name, byte arity, NativeFn function) {  // ( -- )
	create_native(name, arity, function);
	install_native();
}

static void install_method() {  // ( ActorDfn Native -- ActorDfn )
	ActorDef *dfn = AS_ACTOR_DFN(SND);
	String *key = AS_NATIVE(TOP)->name;
	bool was_new = tableSet(&dfn->msg_handler, key, pop());
	if (!was_new) crashAndBurn("already installed %s into %s", key->text, dfn->name->text);
}

static void create_native_method(const char *name, byte arity, NativeFn function) {  // ( ActorDfn -- ActorDfn )
	create_native(name, arity, function);
	install_method();
}

static void math_constant(const char *name, double value) {  // ( -- )
	push(NUMBER_VAL(value));
	push_C_string(name);
	defineGlobal();
}

void install_native_functions() {
	defineNative("clock", 0, clock_native);
	defineNative("abs", 1, abs_native);
	defineNative("sqrt", 1, sqrt_native);
	defineNative("int", 1, int_native);
	defineNative("floor", 1, floor_native);
	defineNative("fib_native", 1, fib_native);
	defineNative("strcat", 2, concatenate);
	defineNative("val", 1, val_native);
	defineNative("chr", 1, chr_native);
	defineNative("str", 1, str_native);
	defineNative("len", 1, len_native);
	defineNative("mid", 3, mid_native);

	math_constant("e", M_E);
	math_constant("inf", HUGE_VAL);
	math_constant("nan", NAN);
	math_constant("pi", M_PI);
	math_constant("tau", 2.0 * M_PI);

	// Now let me try to create the console.
	// It starts with the class definition:

	push_C_string("Console");
	define_actor(0);

	// Next up, define some methods:
	create_native_method("echo", 1, console_echo);
	create_native_method("read", 1, console_read);
	create_native_method("random", 1, console_random);

	// Oh yeah about that...
	srand(time(NULL));

	// Finally, create the actor itself.
	make_template_from_dfn();
	make_actor_from_template();

	push_C_string("console");
	defineGlobal();


#ifdef DEBUG_PRINT_GLOBALS
	tableDump(&vm.globals);
#endif // DEBUG_PRINT_GLOBALS
}
