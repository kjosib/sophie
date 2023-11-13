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

static Value chr_native(Value *args) {
	args[0] = force(args[0]);
	String *dst = new_String(1);
	dst->text[0] = AS_NUMBER(args[0]);
	return GC_VAL(intern_String(dst));
}

static Value str_native(Value *args) {
	double value = AS_NUMBER(force(args[0]));
	int len = snprintf(NULL, 0, NUMBER_FORMAT, value);
	String *dst = new_String(len);
	snprintf(dst->text, len+1, NUMBER_FORMAT, value);
	return GC_VAL(intern_String(dst));
}


static Value native_echo(Value *args) {
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

static Value native_read(Value *args) {
	crashAndBurn("read is not yet implemented");
}

static Value native_random(Value *args) {
	crashAndBurn("random is not yet implemented");
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

static void create_native(const char *name, byte arity, NativeFn function) {
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
	pop();
}

static void defineNative(const char *name, byte arity, NativeFn function) {
	create_native(name, arity, function);
	install_native();
}

static void install_method() {
	ActorDef *dfn = AS_ACTOR_DFN(SND);
	String *key = AS_NATIVE(TOP)->name;
	bool was_new = tableSet(&dfn->msg_handler, key, pop());
	if (!was_new) crashAndBurn("already installed %s into %s", key->text, dfn->name->text);
}

static void create_native_method(const char *name, byte arity, NativeFn function) {
	create_native(name, arity, function);
	install_method();
}

void install_native_functions() {
	defineNative("clock", 0, clock_native);
	defineNative("abs", 1, abs_native);
	defineNative("sqrt", 1, sqrt_native);
	defineNative("fib_native", 1, fib_native);
	defineNative("strcat", 2, concatenate);
	defineNative("chr", 1, chr_native);
	defineNative("str", 1, str_native);

	// Now let me try to create the console.
	// It starts with the class definition:

	push_C_string("Console");
	define_actor(0);
	push(GC_VAL(AS_ACTOR_DFN(TOP)->name));
	defineGlobal();

	// Next up, define some methods:
	create_native_method("echo", 1, native_echo);
	create_native_method("read", 1, native_read);
	create_native_method("random", 1, native_random);

	// Finally, create the actor itself.
	make_template_from_dfn();
	make_actor_from_template();

	push_C_string("console");
	defineGlobal();
	pop();


#ifdef DEBUG_PRINT_GLOBALS
	tableDump(&vm.globals);
#endif // DEBUG_PRINT_GLOBALS
}
