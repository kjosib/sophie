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

static void finalize_function(Function *function) {
	freeChunk(&function->chunk);
}

static void display_closure(Closure *closure) {
	display_function(closure->function);
}

static void blacken_closure(Closure *closure) {
	darken_in_place(&closure->function);
	darkenValues(closure->captives, closure->function->nr_captures);
}

static size_t size_closure(Closure *closure) { return sizeof(Closure) + (sizeof(Value) * closure->function->nr_captures); }

static void display_snapped(Closure *snap) {
	printf(":");
	printValue(SNAP_RESULT(snap));
}

static void blacken_snapped(Closure *snap) {
	darkenValue(&SNAP_RESULT(snap));
}

static size_t size_snapped(Closure *snapped) { return sizeof(Closure) + sizeof(Value); }


GC_Kind KIND_Function = {
	.display = display_function,
	.deeply = display_function,
	.blacken = blacken_function,
	.size = size_function,
	.finalize = finalize_function,
};

GC_Kind KIND_Closure = {
	.display = display_closure,
	.deeply = display_closure,
	.blacken = blacken_closure,
	.size = size_closure,
};

GC_Kind KIND_snapped = {
	.display = display_snapped,
	.deeply = display_snapped,
	.blacken = blacken_snapped,
	.size = size_snapped,
};


Function *newFunction(FunctionType fn_type, Chunk *chunk, byte arity, byte nr_captures) {
	Function *function = gc_allocate(&KIND_Function, sizeof(Function) + nr_captures * sizeof(Capture));
	function->name = AS_STRING(pop());
	function->arity = arity;
	function->nr_captures = nr_captures;
	function->fn_type = fn_type;
	function->visited = false;
	function->chunk = *chunk;
	initChunk(chunk);
#if RECLAIM_CHUNKS
	gc_must_finalize(function);
#endif
	return function;
}

void close_function(Value *stack_slot) {
	// This only does most of the work.
	// Potentially several peers could refer to each other,
	// so this can't capture yet.
	// We do, however, need to clear out the captives array right quick to avoid confounding the garbage collector.
	size_t capture_size = sizeof(Value) * AS_FN(*stack_slot)->nr_captures;
	Closure *closure = gc_allocate(&KIND_Closure, sizeof(Closure) + capture_size);
	// fn is now invalid, as there's been a collection
	closure->function = AS_FN(*stack_slot);
	memset(closure->captives, 0, capture_size);
	*stack_slot = (closure->function->fn_type == TYPE_MEMOIZED) ? THUNK_VAL(closure) : CLOSURE_VAL(closure);
}

