#include "common.h"

String *name_of_function(Function *function) {
	return function->name;
}

static void display_function(Function *function) {
	printf("<fn %s/%d>", name_of_function(function)->text, function->arity);
}

static void blacken_function(Function *function) {
	darken_in_place(&function->name);
	darkenChunk(&function->chunk);
}

static size_t size_function(Function *function) { return sizeof(Function) + function->nr_captures * sizeof(Capture); }

static void display_closure(Closure *closure) {
	display_function(closure->function);
}

static void blacken_closure(Closure *closure) {
	darken_in_place(&closure->function);
	darkenValues(closure->captives, closure->function->nr_captures);
}

static size_t size_closure(Closure *closure) { return sizeof(Closure) + (sizeof(Value) * closure->function->nr_captures); }

GC_Kind KIND_Function = {
	.display = display_function,
	.deeply = display_function,
	.blacken = blacken_function,
	.size = size_function,
};

GC_Kind KIND_Closure = {
	.display = display_closure,
	.deeply = display_closure,
	.blacken = blacken_closure,
	.size = size_closure,
};


Function *newFunction(FunctionType fn_type, Chunk *chunk, byte arity, byte nr_captures) {
	Function *function = gc_allocate(&KIND_Function, sizeof(Function) + nr_captures * sizeof(Capture));
	function->name = AS_STRING(pop());
	function->arity = arity;
	function->nr_captures = nr_captures;
	function->fn_type = fn_type;
	function->chunk = *chunk;
	initChunk(chunk);
	return function;
}

void close_function(Value *stack_slot) {
	// This only does most of the work.
	// Potentially several peers could refer to each other,
	// so this can't capture yet.
	// We do, however, need to clear out the captives array right quick to avoid confounding the garbage collector.
	size_t capture_size = sizeof(Value) * ((Function *)(stack_slot->as.ptr))->nr_captures;
	Closure *closure = gc_allocate(&KIND_Closure, sizeof(Closure) + capture_size);
	// fn is now invalid, as there's been a collection
	closure->function = stack_slot->as.ptr;
	memset(closure->captives, 0, capture_size);
	*stack_slot = closure->function->arity ? CLOSURE_VAL(closure) : THUNK_VAL(closure);
}

