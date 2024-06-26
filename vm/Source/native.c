#define _USE_MATH_DEFINES

#include <ctype.h>
#include <math.h>
#include <time.h>

#include <sys/stat.h>

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
	push(GC_VAL(dst));
	intern_String();
	return TOP;
}

static Value compare_string(Value *args) {
	// NB: Forcing is not needed here because as an operator overload, the arguments are reliably strict.
	if (AS_STRING(args[0]) == AS_STRING(args[1])) return vm.same;
	else {
		int direction = strcmp(AS_STRING(args[0])->text, AS_STRING(args[1])->text);
		if (direction < 0) return vm.less;
		else if (direction == 0) return vm.same;
		else return vm.more;
	}
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
		return construct_record();
	}
}

static Value len_native(Value *args) {
	String *str = AS_STRING(force(args[0]));
	return NUMBER_VAL((double)(str->length));
}

static Value ord_native(Value *args) {
	String *str = AS_STRING(force(args[0]));
	if (str->length) return NUMBER_VAL((double)(str->text[0]));
	else return NUMBER_VAL(-1);
}

static Value chr_native(Value *args) {
	args[0] = force(args[0]);
	String *dst = new_String(1);
	dst->text[0] = (byte)(AS_NUMBER(args[0]));
	push(GC_VAL(dst));
	intern_String();
	return TOP;
}

static Value slice(Value *argp, size_t left, size_t right) {
	// Make a portion of a given string.
	assert(left <= right);
	size_t size = right - left;
	String *dst = new_String(size);
	memcpy(dst->text, AS_STRING(*argp)->text + left, size);
	push(GC_VAL(dst));
	intern_String();
	return TOP;
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
	push(GC_VAL(dst));
	intern_String();
	return TOP;
}

static Value trim_native(Value *args) {
	*args = force(*args);
	String *str = AS_STRING(*args);
	char *text = str->text;
	size_t left = 0, right = str->length;
	while (left < right && isspace(text[left])) left++;
	while (left < right && isspace(text[right-1])) right--;
	return slice(args, left, right);
}

static Value join_native(Value *args) {
	// Determine the total necessary size, which can be done by duplicating, then iterating across, the list.
	size_t size = 0;
	dup();
	FOR_LIST(args[1]) {
		Value head = LIST_HEAD(args[1]);
		size += AS_STRING(head)->length;
	}

	// Allocate the resulting string.
	String *dst = new_String(size);

	// Iterate through the list once again, copying substrings into place.
	// This time, all the allocation is surely already done.
	char *text = &dst->text[0];
	FOR_LIST(args[0]) {
		String *head = AS_STRING(LIST_HEAD(args[0]));
		memcpy(text, head->text, head->length);
		text += head->length;
	}

	// Return the result.
	push(GC_VAL(dst));
	intern_String();
	return TOP;
}

static Value str_native(Value *args) {
	double value = AS_NUMBER(force(args[0]));
	size_t len = snprintf(NULL, 0, NUMBER_FORMAT, value);
	String *dst = new_String(len);
	snprintf(dst->text, len+1, NUMBER_FORMAT, value);
	push(GC_VAL(dst));
	intern_String();
	return TOP;
}

static size_t beginning_of_line(char *text, size_t pos) {
	// Search backwards for a newline.
	// If one exists, return the index of the character after that newline.
	// Otherwise, return zero.
	while (pos) {
		pos--;
		if (text[pos] == '\n') return pos + 1;
	}
	return 0;
}

static Value split_lines(Value *args) {
	// The meat of a function to convert a string into a list of strings
	// by splitting it after every newline sequence.
	// The approach is to work with some temp space pushed on the stack.

	// args[0] = the input string.

	// An empty input becomes an empty list.
	// It's probably easiest to start at the end and work backwards.
	
	String *src = AS_STRING(args[0]);
	size_t right = src->length;
	if (!right) return vm.nil;

	push(vm.nil);

	size_t left = right;
	if (src->text[right - 1] != '\n') left++;
	while (right) {
		left = beginning_of_line(AS_STRING(args[0])->text, left-1);
		push(slice(args, left, right));
		snoc();
		right = left;
	}

	return pop();
}

/***********************************************************************************/

static Value console_echo(Value *args) {
	// Expect args[1] to be a (thunk of a) list of strings.
	FOR_LIST(args[1]) {
		fputs(AS_STRING(LIST_HEAD(args[1]))->text, stdout);
	}

	return UNSET_VAL;
}

static Value console_read(Value *args) {
	/*
	Read a line of text from the console as a string,
	and send it as the parameter to a given message.
	*/
	static char buffer[1024];
	fgets(buffer, sizeof(buffer), stdin);
	push_C_string(buffer);
	push(args[1]);
	enqueue_message(apply());
	return UNSET_VAL;
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
	enqueue_message(apply());
	return UNSET_VAL;
}

/***********************************************************************************/

static void push_file_contents(const char *path) {
	// Convenience function to pull the contents of a file (by C name) into a string and push it on the stack.
	FILE *file = fopen(path, "rb");
	if (! file) crashAndBurn("Failed to open file: %s", path);
	struct _stat64 stat;
	if (-1 == _fstat64(fileno(file), &stat)) crashAndBurn("Failed to stat file: %s", path);
	String *dst = new_String(stat.st_size);
	size_t nr_read = fread(&dst->text, sizeof(char), stat.st_size, file);
	dst->text[nr_read] = 0;  // Just in case of partial read.
	fclose(file);
	push(GC_VAL(dst));
	intern_String();
}

static Value fs_read_file(Value *args) {
	/*
	Attempts to read and send a message containing a file's contents,
	similar to what console_read does. The difference here is we can
	as the operating system in advance how big the file is.

	args[0] == self
	args[1] == the file name
	args[2] == the parametric message
	*/
	push_file_contents(AS_STRING(args[1])->text);
	push(args[2]);
	enqueue_message(apply());
	return UNSET_VAL;
}

static Value fs_read_lines(Value *args) {
	/*
	Similar to read_file, but the message contains a list of strings.
	*/
	push_file_contents(AS_STRING(args[1])->text);
	TOP = split_lines(&TOP);
	push(args[2]);
	enqueue_message(apply());
	return UNSET_VAL;
}

/***********************************************************************************/

static void display_native(Native *native) { printf("<fn %s>", native->name->text); }

static void blacken_native(Native *native) { darken_in_place(&native->name); }

static size_t size_native(Native *native) { return sizeof(Native); }
static size_t arity_native(Native *native) { return native->arity; }

static Value apply_native() {
	Native *native = AS_NATIVE(pop());
	Value *slot = vm.stackTop - native->arity;
	Value result = native->function(slot);
	vm.stackTop = slot;
	return result;
}

GC_Kind KIND_Native = {
	.display = display_native,
	.deeply = display_native,
	.blacken = blacken_native,
	.size = size_native,
	.apply = apply_native,
	.name = "Native Function",
};

static void create_native(const char *name, byte arity, NativeFn function) {  // ( -- Native Name )
	push_C_string(name);
	Native *native = gc_allocate(&KIND_Native, sizeof(Native));
	native->arity = arity;
	native->function = function;
	native->name = AS_STRING(TOP);
	dup();
	SND = NATIVE_VAL(native);

}

void create_native_function(const char *name, byte arity, NativeFn function) {  // ( -- )
	create_native(name, arity, function);
	defineGlobal();
}

void create_native_method(const char *name, byte arity, NativeFn function) {  // ( ActorDfn -- ActorDfn )
	assert(arity);
	create_native(name, arity, function);    // ActorDfn Native Name
	install_method();                        // ActorDfn
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
	create_native_function("acos", 1, acos_native);
	create_native_function("acosh", 1, acosh_native);
	create_native_function("asin", 1, asin_native);
	create_native_function("asinh", 1, asinh_native);
	create_native_function("atan", 1, atan_native);
	create_native_function("atanh", 1, atanh_native);
	create_native_function("ceil", 1, ceil_native);
	create_native_function("cos", 1, cos_native);
	create_native_function("cosh", 1, cosh_native);
	create_native_function("erf", 1, erf_native);
	create_native_function("erfc", 1, erfc_native);
	create_native_function("exp", 1, exp_native);
	create_native_function("expm1", 1, expm1_native);
	create_native_function("factorial", 1, factorial_native);
	create_native_function("abs", 1, fabs_native);
	create_native_function("floor", 1, floor_native);
	create_native_function("lgamma", 1, lgamma_native);
	create_native_function("log", 1, log_native);
	create_native_function("log10", 1, log10_native);
	create_native_function("log1p", 1, log1p_native);
	create_native_function("log2", 1, log2_native);
	create_native_function("sin", 1, sin_native);
	create_native_function("sinh", 1, sinh_native);
	create_native_function("sqrt", 1, sqrt_native);
	create_native_function("tan", 1, tan_native);
	create_native_function("tanh", 1, tanh_native);
	create_native_function("gamma", 1, tgamma_native);
	create_native_function("trunc", 1, trunc_native);
	create_native_function("int", 1, trunc_native);
	create_native_function("fib_native", 1, fib_native); // Just for access to that baseline microbenchmark

	create_native_function("atan2", 2, atan2_native);
	create_native_function("copysign", 2, copysign_native);
	create_native_function("fmod", 2, fmod_native);
	create_native_function("ldexp", 2, ldexp_native);
	create_native_function("pow", 2, pow_native);

	math_constant("e", M_E);
	math_constant("inf", HUGE_VAL);
	math_constant("nan", NAN);
	math_constant("pi", M_PI);
	math_constant("tau", 2.0 * M_PI);
}

/***********************************************************************************/

static void install_strings() {
	create_native("<=>|string|string", 2, compare_string);
	pop();  // Don't need the name on the stack now.
	install_binop(BOP_CMP, TX_STRING, TX_STRING);

	create_native_function("strcat", 2, concatenate);
	create_native_function("val", 1, val_native);
	create_native_function("chr", 1, chr_native);
	create_native_function("str", 1, str_native);
	create_native_function("len", 1, len_native);
	create_native_function("ord", 1, ord_native);
	create_native_function("mid", 3, mid_native);
	create_native_function("join", 1, join_native);
	create_native_function("trim", 1, trim_native);
	create_native_function("split_lines", 1, split_lines);
}

static void install_the_console() {
	// Now let me try to create the console.
	// It starts with the class definition:

	push(UNSET_VAL);
	push_C_string("Console");  // Implements the Console interface; just happens to share the name.
	define_actor();

	// Next up, define some methods:
	create_native_method("echo", 2, console_echo);
	create_native_method("read", 2, console_read);
	create_native_method("random", 2, console_random);

	// Oh yeah about that...
	seed_random_number_generator();

	// Finally, create the actor itself.
	push(make_template_from_dfn());
	make_actor_from_template();

	push_C_string("console");
	defineGlobal();
}

static void install_the_filesystem() {
	// Similar linguistic interface to the console.
	// Just happens to have some different methods.

	push(UNSET_VAL);
	push_C_string("FileSystem");
	define_actor();

	create_native_method("read_file", 3, fs_read_file);
	create_native_method("read_lines", 3, fs_read_lines);

	push(make_template_from_dfn());
	make_actor_from_template();

	push_C_string("filesystem");
	defineGlobal();
}

void install_native_functions() {
	create_native_function("clock", 0, clock_native);
	install_numerics();
	install_strings();
	install_the_console();
	install_the_filesystem();
}
