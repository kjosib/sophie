#define _USE_MATH_DEFINES

#include <ctype.h>
#include <math.h>
#include <time.h>

#include "common.h"
#include "chacha.h"
#include "platform_specific.h"

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

static ChaCha_Seed seed;
static ChaCha_Block randomness;
static int noise_index;

static void seed_random_number_generator() {
	platform_entropy(&seed, sizeof(seed));
	noise_index = 8;
}

static Value console_random(Value *args) {
	/*
	Similar to console_read, but less stringy.
	*/
	if (noise_index >= 8) {
		noise_index = 0;
		seed.count++;
		chacha_make_noise(&randomness, &seed);
	}
	args[0] = NUMBER_VAL((double)randomness.noise_64[noise_index++] / UINT64_MAX);
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

void native_create_function(const char *name, byte arity, NativeFn function) {  // ( -- )
	create_native(name, arity, function);
	install_native();
}

static void install_method() {  // ( ActorDfn Native -- ActorDfn )
	ActorDef *dfn = AS_ACTOR_DFN(SND);
	String *key = AS_NATIVE(TOP)->name;
	bool was_new = tableSet(&dfn->msg_handler, key, pop());
	if (!was_new) crashAndBurn("already installed %s into %s", key->text, dfn->name->text);
}

void native_create_method(const char *name, byte arity, NativeFn function) {  // ( ActorDfn -- ActorDfn )
	create_native(name, arity, function);
	install_method();
}

/***********************************************************************************/

static void math_constant(const char *name, double value) {  // ( -- )
	push(NUMBER_VAL(value));
	push_C_string(name);
	defineGlobal();
}

static double factorial(double d) { return tgamma(d + 1); }

#define NUMERIC_1(fn) static Value fn ## _native(Value *args) {\
	return NUMBER_VAL(fn(AS_NUMBER(force(args[0])))); \
}

#define NUMERIC_2(fn) static Value fn ## _native(Value *args) {\
	return NUMBER_VAL(fn(AS_NUMBER(force(args[0])), AS_NUMBER(force(args[1])))); \
}

NUMERIC_1(acos)
NUMERIC_1(acosh)
NUMERIC_1(asin)
NUMERIC_1(asinh)
NUMERIC_1(atan)
NUMERIC_1(atanh)
NUMERIC_1(ceil)
NUMERIC_1(cos)
NUMERIC_1(cosh)
NUMERIC_1(erf)
NUMERIC_1(erfc)
NUMERIC_1(exp)
NUMERIC_1(expm1)
NUMERIC_1(fib)
NUMERIC_1(factorial)
NUMERIC_1(fabs)
NUMERIC_1(floor)
NUMERIC_1(lgamma)
NUMERIC_1(log)
NUMERIC_1(log10)
NUMERIC_1(log1p)
NUMERIC_1(log2)
NUMERIC_1(sin)
NUMERIC_1(sinh)
NUMERIC_1(sqrt)
NUMERIC_1(tan)
NUMERIC_1(tanh)
NUMERIC_1(tgamma)
NUMERIC_1(trunc)

NUMERIC_2(atan2)
NUMERIC_2(copysign)
NUMERIC_2(fmod)
static Value ldexp_native(Value *args) {
	// Cast avoids a warning due to the type of the second argument.
	return NUMBER_VAL(ldexp(AS_NUMBER(force(args[0])), (int)AS_NUMBER(force(args[1]))));
}
NUMERIC_2(pow)

static void install_numerics() {
	native_create_function("acos", 1, acos_native);
	native_create_function("acosh", 1, acosh_native);
	native_create_function("asin", 1, asin_native);
	native_create_function("asinh", 1, asinh_native);
	native_create_function("atan", 1, atan_native);
	native_create_function("atanh", 1, atanh_native);
	native_create_function("ceil", 1, ceil_native);
	native_create_function("cos", 1, cos_native);
	native_create_function("cosh", 1, cosh_native);
	native_create_function("erf", 1, erf_native);
	native_create_function("erfc", 1, erfc_native);
	native_create_function("exp", 1, exp_native);
	native_create_function("expm1", 1, expm1_native);
	native_create_function("factorial", 1, factorial_native);
	native_create_function("abs", 1, fabs_native);
	native_create_function("floor", 1, floor_native);
	native_create_function("lgamma", 1, lgamma_native);
	native_create_function("log", 1, log_native);
	native_create_function("log10", 1, log10_native);
	native_create_function("log1p", 1, log1p_native);
	native_create_function("log2", 1, log2_native);
	native_create_function("sin", 1, sin_native);
	native_create_function("sinh", 1, sinh_native);
	native_create_function("sqrt", 1, sqrt_native);
	native_create_function("tan", 1, tan_native);
	native_create_function("tanh", 1, tanh_native);
	native_create_function("gamma", 1, tgamma_native);
	native_create_function("trunc", 1, trunc_native);
	native_create_function("int", 1, trunc_native);
	native_create_function("fib_native", 1, fib_native); // Just for access to that baseline microbenchmark

	native_create_function("atan2", 2, atan2_native);
	native_create_function("copysign", 2, copysign_native);
	native_create_function("fmod", 2, fmod_native);
	native_create_function("ldexp", 2, ldexp_native);
	native_create_function("pow", 2, pow_native);

	math_constant("e", M_E);
	math_constant("inf", HUGE_VAL);
	math_constant("nan", NAN);
	math_constant("pi", M_PI);
	math_constant("tau", 2.0 * M_PI);
}

/***********************************************************************************/

static void install_strings() {
	native_create_function("strcat", 2, concatenate);
	native_create_function("val", 1, val_native);
	native_create_function("chr", 1, chr_native);
	native_create_function("str", 1, str_native);
	native_create_function("len", 1, len_native);
	native_create_function("mid", 3, mid_native);
}

static void install_the_console() {
	// Now let me try to create the console.
	// It starts with the class definition:

	push_C_string("Console");  // Implements the Console interface; just happens to share the name.
	define_actor(0);

	// Next up, define some methods:
	native_create_method("echo", 1, console_echo);
	native_create_method("read", 1, console_read);
	native_create_method("random", 1, console_random);

	// Oh yeah about that...
	seed_random_number_generator();

	// Finally, create the actor itself.
	make_template_from_dfn();
	make_actor_from_template();

	push_C_string("console");
	defineGlobal();
}

void native_install_functions() {
	native_create_function("clock", 0, clock_native);
	install_numerics();
	install_strings();
	install_the_console();
}
