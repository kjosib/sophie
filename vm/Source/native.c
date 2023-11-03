#include <math.h>
#include <time.h>
#include "common.h"

/***********************************************************************************/

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

Native *newNative(byte arity, NativeFn function) {
	Native *native = gc_allocate(&KIND_Native, sizeof(Native));
	native->arity = arity;
	native->function = function;
	native->name = NULL;
	return native;
}

static void defineNative(const char *name, byte arity, NativeFn function) {
	push(GC_VAL(import_C_string(name, strlen(name))));
	Native *native = newNative(arity, function);
	native->name = AS_STRING(TOP);
	defineGlobal(native->name, NATIVE_VAL(native));
	pop();
}

void install_native_functions() {
	defineNative("clock", 0, clock_native);
	defineNative("abs", 1, abs_native);
	defineNative("sqrt", 1, sqrt_native);
	defineNative("fib_native", 1, fib_native);
#ifdef DEBUG_PRINT_GLOBALS
	tableDump(&vm.globals);
#endif // DEBUG_PRINT_GLOBALS
}
