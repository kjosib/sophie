#include "common.h"

String *name_of_function(Function *function) {
	if (function->fn_type == TYPE_SCRIPT) return NULL;
	else return AS_STRING(function->chunk.constants.at[0]);
}

static void check_underflow(int arity, String *name) {
	// For use in debug modes?
	if (&vm.frame->base[arity] > vm.stackTop) {
		fprintf(stderr, "Stack underflow calling %s", name->text);
		crashAndBurn("panic");
	}
}

static void display_function(Function *function) {
	if (function->fn_type == TYPE_SCRIPT) printf("<script>");
	else {
		printf("<fn ");
		printValue(function->chunk.constants.at[0]);
		printf("/%d>", function->arity);
	}
}

static void blacken_function(Function *function) { darkenChunk(&function->chunk); }

static size_t size_function(Function *function) { return sizeof(Function) + function->nr_captures * sizeof(Capture); }


static void call_closure(Closure *closure) {
	if (vm.frame == &vm.frame[FRAMES_MAX]) crashAndBurn("Call depth exceeded");
	vm.frame++;
	vm.frame->closure = closure;
	vm.frame->ip = closure->function->chunk.code.at;
	vm.frame->base = vm.stackTop - closure->function->arity;
}

static void exec_closure(Closure *closure) {
	int arity = closure->function->arity;
	// Hand-rolled or memmove here? Let's profile!
	// ?? memmove(vm.frame->base, vm.stackTop - arity, arity * sizeof(Value)); ??
	// In practice this will generally be a small number of iterations.
	// Also, Value structures are big enough for a good optimizer to use SSE instructions on.
	Value *args = vm.stackTop - arity;
	if (vm.frame->base < args) {
		for (int index = 0; index < arity; index++) {
			vm.frame->base[index] = args[index];
		}
		vm.stackTop = &vm.frame->base[arity];
	}
	vm.frame->closure = closure;
	vm.frame->ip = closure->function->chunk.code.at;
}

static void display_closure(Closure *closure) {
	display_function(closure->function);
}

static void blacken_closure(Closure *closure) {
	darken_in_place(&closure->function);
	darkenValues(closure->captives, closure->function->nr_captures);
}

static size_t size_closure(Closure *closure) { return sizeof(Closure) + (sizeof(Value) * closure->function->nr_captures); }

static void call_native(Native *native) {
	Value *base = vm.stackTop - native->arity;
	*base = native->function(base);
	vm.stackTop = base + 1;
}

static void exec_native(Native *native) {
	Value *base = vm.stackTop - native->arity;
	*vm.frame->base = native->function(base);
	vm.stackTop = vm.frame->base + 1;
	vm.frame--;
}

static void display_native(Native *native) { printf("<fn %s>", native->name->text); }

static void blacken_native(Native *native) { darken_in_place(&native->name); }

static size_t size_native(Native *native) { return sizeof(Native); }


GC_Kind KIND_Function = {
	.call = bad_callee,
	.exec = bad_callee,
	.display = display_function,
	.blacken = blacken_function,
	.size = size_function,
};

GC_Kind KIND_Closure = {
	.call = call_closure,
	.exec = exec_closure,
	.display = display_closure,
	.blacken = blacken_closure,
	.size = size_closure,
};

GC_Kind KIND_Native = {
	.call = call_native,
	.exec = exec_native,
	.display = display_native,
	.blacken = blacken_native,
	.size = size_native,
};


Function *newFunction(FunctionType fn_type, Chunk *chunk, byte arity, byte nr_captures) {
	Function *function = gc_allocate(&KIND_Function, sizeof(Function) + nr_captures * sizeof(Capture));
	function->arity = arity;
	function->nr_captures = nr_captures;
	function->fn_type = fn_type;
	function->chunk = *chunk;
	initChunk(chunk);  // Function takes ownership of the heap memory associated with the chunk.
	return function;
}

void close_function(Value *stack_slot) {
	// This only does most of the work.
	// Potentially several peers could refer to each other,
	// so this can't capture yet.
	// We do, however, need to clear out the captives array right quick to avoid confounding the garbage collector.
	Function *fn = stack_slot->as.ptr;
	size_t capture_size = sizeof(Value) * fn->nr_captures;
	Closure *closure = gc_allocate(&KIND_Closure, sizeof(Closure) + capture_size);
	// fn is now invalid, as there's been a collection
	closure->function = stack_slot->as.ptr;
	memset(closure->captives, 0, capture_size);
	stack_slot->as.ptr = closure;
}

Native *newNative(byte arity, NativeFn function) {
	Native *native = gc_allocate(&KIND_Native, sizeof(Native));
	native->arity = arity;
	native->function = function;
	native->name = NULL;
	return native;
}


