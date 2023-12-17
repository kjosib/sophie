#include <stdarg.h>
#include <math.h>
#include <time.h>
#include "common.h"
#include "opcodes.h"

#define CLOSURE (vm.trace->closure)


VM vm;

static void grey_the_vm_roots() {
	// Grey the value stack
	darkenValues(vm.stack, vm.stackTop - vm.stack);
	// Grey the globals
	// Grey the call frame stack
	if (vm.trace) {
		for (Trace *trace = vm.traces; trace <= vm.trace; trace++) {
			darken_in_place(&trace->closure);
		}
	}
	// Grey the known special cases.
	darkenValue(&vm.cons);
	darkenValue(&vm.nil);
	darkenValue(&vm.maybe_this);
	darkenValue(&vm.maybe_nope);
}


static void resetStack() {
	vm.stackTop = vm.stack;
	vm.trace = vm.traces-1;
}

void vm_init() {
	resetStack();
	initTable(&vm.strings);
	vm.cons = vm.nil = vm.maybe_this = vm.maybe_nope = NIL_VAL;
	gc_install_roots(grey_the_vm_roots);
}

void vm_capture_preamble_specials(Table *globals) {
	vm.cons = table_get_from_C(globals, "cons");
	vm.nil = table_get_from_C(globals, "nil");
	vm.maybe_this = table_get_from_C(globals, "this");
	vm.maybe_nope = table_get_from_C(globals, "nope");
}

void vm_dispose() {
	freeTable(&vm.strings);
}

static void displaySomeValues(Value *first, size_t count) {
	for (size_t index = 0; index < count; index++) {
		printf("[");
		printValue(first[index]);
		printf("] ");
	}
}

static void displayStack(Value *base) {
	printf(" %s         ", CLOSURE->function->name->text);
	displaySomeValues(vm.stack, (base - vm.stack));
	printf("------- ");
	displaySomeValues(base, (vm.stackTop - base));
	printf("---( ");
	displaySomeValues(CLOSURE->captives, CLOSURE->function->nr_captures);
	printf(")\n");
}


__declspec(noreturn) static void runtimeError(byte *vpc, Value *base, const char *format, ...) {
	va_list args;
	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);
	fputs("\n", stderr);
	displayStack(base);
	Function *function = CLOSURE->function;
	size_t offset = vpc - function->chunk.code.at - 1;
	int line = findLine(&function->chunk, offset);
	vm_panic("a runtime error in line %d", line);
}

__declspec(noreturn) void vm_panic(const char *format, ...) {
	va_list args;
	va_start(args, format);
	fputs("\n\n\n-----------\n", stderr);
	for (Trace *frame = vm.traces; frame <= vm.trace; frame++) {
		fprintf(stderr, "in %s\n", frame->closure->function->name->text);
	}
	fputs("\n***\n ***\n  ***   ***   Died of ", stderr);
	vfprintf(stderr, format, args);
	fputs(".\n\n", stderr);
	exit(99);
}

static void capture_closure(Closure *closure, Value *base) {
	// Precondition: *closure points to a fresh Closure object with no captures.
	Function *fn = closure->function;
	int index = 0;
	if (fn->fn_type == TYPE_MEMOIZED) closure->captives[index++] = NIL_VAL;
	for (; index < fn->nr_captures; index++) {
		Capture capture = fn->captures[index];
		Value *capture_base = capture.is_local ? base : CLOSURE->captives;
		closure->captives[index] = capture_base[capture.offset];
	}
	// Postcondition: Captures have been copied per directives in *closure's function.
}

static double knuth_mod(double numerator, double denominator) {
	double r = fmod(numerator, denominator);
	bool C_is_wrong = (numerator < 0) != (denominator < 0);
	return C_is_wrong ? r + denominator : r;
}

#ifdef _DEBUG
static double x_num(byte *vpc, Value *base, Value it) {
	if (!IS_NUMBER(it)) {
		char *ins = instruction[vpc[-1]].name;
		runtimeError(vpc, base, "Needed number for %s; got %s", ins, valKind[it.type]);
	}
	return AS_NUMBER(it);
}
#define num(it) x_num(vpc, base, it)
#else
#define num AS_NUMBER
#endif // _DEBUG

void perform(Value action) {
	// Where all the action happens, so to speak.
	switch (action.type)
	{
	case VAL_NIL:  // The empty action
		break;
	case VAL_CLOSURE:
		run(AS_CLOSURE(action));
		break;
	case VAL_MESSAGE:
	case VAL_BOUND:
		enqueue_message(action);
		break;
	default:
		crashAndBurn("Can't yet handle a %s action.", valKind[action.type]);
	}
}

#define NEXT goto dispatch
#define READ_BYTE() (*vpc++)
#define LEAP() do { vpc += word_at(vpc); } while (0)
#define SKIP_AND_POP() do { pop(); vpc += 2; } while(0)
#define YIELD(value) do { Value retval = (value); vm.stackTop = base; vm.trace--; return retval; } while (0)

Value run(Closure *closure) {
	if (vm.trace == &vm.traces[FRAMES_MAX]) crashAndBurn("Max recursion depth exceeded.");
	vm.trace++;
	Value *base = vm.stackTop - closure->function->arity;
	Value *constants;
	byte *vpc;
enter:
	constants = closure->function->chunk.constants.at;
	vpc = closure->function->chunk.code.at;
	CLOSURE = closure;
	// At this point, closure becomes invalid because allocations can happen.

	assert(base >= vm.stack);  // If this fails, the script died of stack underflow.

	for (;;) {
dispatch:

#ifdef DEBUG_TRACE_EXECUTION
		printf("-----------------\n");
		displayStack(base);
		printf("%s > ", name_of_function(CLOSURE->function)->text);
		disassembleInstruction(&CLOSURE->function->chunk, (int)(vpc - CLOSURE->function->chunk.code.at));
#endif // DEBUG_TRACE_EXECUTION

		switch (READ_BYTE()) {
		case OP_PANIC:
			runtimeError(vpc, base, "PANIC instruction encountered.");
		case OP_GLOBAL:  // Fall-through to OP_CONSTANT
		case OP_CONSTANT:
			push(constants[READ_BYTE()]);
			NEXT;
		case OP_POP: pop(); NEXT;
		case OP_LOCAL: {
			int index = READ_BYTE();
			assert(base + index < vm.stackTop);  // Some day, let assembler.c discern max stack usage per function, and check only once.
			push(base[index]);
			NEXT;
		}

		case OP_CAPTIVE: push(CLOSURE->captives[READ_BYTE()]); NEXT;
		case OP_CLOSURE:
		{
			// Initialize a run of closures. The underlying function definitions are in the constant table.
			int constant_index = READ_BYTE();
			int nr_closures = READ_BYTE();
			Value *slot = vm.stackTop;
			memcpy(slot, constants+constant_index, sizeof(Value) * nr_closures);
			vm.stackTop += nr_closures;
			for (int index = 0; index < nr_closures; index++) close_function(&slot[index]);
			for (int index = 0; index < nr_closures; index++) capture_closure(AS_CLOSURE(slot[index]), base);
			NEXT;
		}
		case OP_THUNK: {
			push(constants[READ_BYTE()]);
			close_function(&TOP);
			capture_closure(AS_CLOSURE(TOP), base);
			NEXT;
		}
		case OP_NIL: push(vm.nil); NEXT;
		case OP_TRUE: push(BOOL_VAL(true)); NEXT;
		case OP_FALSE: push(BOOL_VAL(false)); NEXT;
		case OP_EQUAL:
			if (IS_NUMBER(SND)) merge(BOOL_VAL(AS_NUMBER(SND) == num(TOP)));
			else if (IS_BOOL(SND)) merge(BOOL_VAL(AS_BOOL(SND) == AS_BOOL(TOP)));
			else {
				// For now, this must be a string.
				assert(IS_GC_ABLE(SND));
				assert(IS_GC_ABLE(TOP));
				AS_GC(SND)->kind->compare();
				TOP = BOOL_VAL(AS_ENUM(TOP) == SAME);
			}
		NEXT;
		case OP_GREATER:
			if (IS_NUMBER(SND)) merge(BOOL_VAL(AS_NUMBER(SND) > num(TOP)));
			else {
				// For now, this must be a string.
				assert(IS_GC_ABLE(SND));
				assert(IS_GC_ABLE(TOP));
				AS_GC(SND)->kind->compare();
				TOP = BOOL_VAL(AS_ENUM(TOP) == MORE);
			}
		NEXT;
		case OP_LESS:
			if (IS_NUMBER(SND)) merge(BOOL_VAL(num(SND) < num(TOP)));
			else {
				// For now, this must be a string.
				assert(IS_GC_ABLE(SND));
				assert(IS_GC_ABLE(TOP));
				AS_GC(SND)->kind->compare();
				TOP = BOOL_VAL(AS_ENUM(TOP) == LESS);
			}
		NEXT;
		case OP_POWER: merge(NUMBER_VAL(pow(num(SND), num(TOP)))); NEXT;
		case OP_MULTIPLY: merge(NUMBER_VAL(num(SND) * num(TOP))); NEXT;
		case OP_DIVIDE: merge(NUMBER_VAL(num(SND) / num(TOP))); NEXT;
		case OP_INTDIV: merge(NUMBER_VAL(floor(num(SND) / num(TOP)))); NEXT;
		case OP_MODULUS: merge(NUMBER_VAL(knuth_mod(num(SND), num(TOP)))); NEXT;
		case OP_ADD: merge(NUMBER_VAL(num(SND) + num(TOP))); NEXT;
		case OP_SUBTRACT: merge(NUMBER_VAL(num(SND) - num(TOP))); NEXT;
		case OP_NOT: TOP = BOOL_VAL(!AS_BOOL(TOP)); NEXT;
		case OP_NEGATE: TOP = NUMBER_VAL(-num(TOP)); NEXT;
		case OP_CALL:
			switch (TOP.type) {
			case VAL_CLOSURE:
				push(run(AS_CLOSURE(pop())));  // The callee will clean the stack.
				NEXT;
			case VAL_CTOR: apply_constructor(); NEXT;
			case VAL_NATIVE:
			{
				Native *native = AS_NATIVE(pop());
				Value *slot = vm.stackTop - native->arity;
				*slot = native->function(slot);
				vm.stackTop = slot + 1;
				NEXT;
			}
			case VAL_BOUND: apply_bound_method(); NEXT;
			default:
				printValue(TOP);
				runtimeError(vpc, base, "CALL needs a callable object; got %s.", valKind[TOP.type]);
			}
		case OP_EXEC:
			switch (TOP.type) {
			case VAL_CLOSURE:
			case VAL_THUNK:
			{
				closure = AS_CLOSURE(pop());
				int arity = closure->function->arity;
				memmove(base, vm.stackTop - arity, arity * sizeof(Value));
				vm.stackTop = base + arity;
				goto enter;
			}
			case VAL_CTOR: YIELD(GC_VAL(construct_record()));
			case VAL_NATIVE:
			{
				Native *native = AS_NATIVE(pop());
				YIELD(native->function(vm.stackTop - native->arity));
			}
			case VAL_BOUND:
			{
				apply_bound_method();
				YIELD(TOP);
			}
			default:
				runtimeError(vpc, base, "EXEC needs a callable object; got val %s.", valKind[TOP.type]);
			}
		case OP_FORCE_RETURN:
		{
			if (IS_THUNK(TOP)) {
				closure = AS_CLOSURE(pop());
				if (DID_SNAP(closure)) {
					YIELD(SNAP_RESULT(closure));
				}
				else {
					// Treat this like an exec / tail-call, but easier since arity is zero by definition.
					vm.stackTop = base;
					goto enter;
				}
			}
			// else fall-through to OP_RETURN;
		}
		case OP_RETURN:
		{
			assert(! IS_THUNK(TOP));  // Return values are needed values! Don't thunk them.
			YIELD(TOP);
		}
		case OP_FORCE:
			TOP = force(TOP);
			assert(!IS_THUNK(TOP));
			NEXT;
		case OP_DISPLAY:
			switch (TOP.type) {
			case VAL_NIL: NEXT;  // The empty action
			case VAL_BOUND:
			case VAL_MESSAGE:
				enqueue_message(pop());
				drain_the_queue();
				NEXT;
			case VAL_CLOSURE:
				if (AS_CLOSURE(TOP)->function->arity == 0) {
					run(AS_CLOSURE(pop()));
					drain_the_queue();
					NEXT;
				}
			default:
				printValueDeeply(TOP);
				pop();
				printf("\n");
				NEXT;
			}
		case OP_JF:
			if (AS_BOOL(TOP)) SKIP_AND_POP();
			else LEAP();
			NEXT;
		case OP_JT:
			if (AS_BOOL(TOP)) LEAP();
			else SKIP_AND_POP();
			NEXT;
		case OP_JMP:
			LEAP();
			NEXT;
		case OP_CASE:
		{
			int tag;
			switch (TOP.type) {
			case VAL_ENUM:
				tag = TOP.as.tag;
				break;
			case VAL_GC: {
				tag = AS_RECORD(TOP)->constructor->tag;
				break;
			}
			default:
				runtimeError(vpc, base, "Need a case-able object; got val %s.", valKind[TOP.type]);
			}
			vpc += 2 * tag;
			LEAP();
			NEXT;
		}
		case OP_FIELD:
		{
			assert(TOP.type == VAL_GC);
			Record *record = AS_RECORD(TOP);
			assert(record->header.kind == &KIND_Record);
			Table *field_offset = &record->constructor->field_offset;
			int offset = tableGet(field_offset, AS_STRING(constants[READ_BYTE()])).as.tag;
			TOP = record->fields[offset];
			NEXT;
		}
		case OP_SNOC:
		{
			swap();
			// Construct a "cons" in the usual way
			push(vm.cons);
			Record *record = construct_record();
			// Fix up the stack
			pop();
			TOP = GC_VAL(record);
			// And begone
			NEXT;
		}
		case OP_BIND:
		{
			// ( actor -- bound_method )
			// Simple approach: Push the callable and then snap these into a bound message.
			push(constants[READ_BYTE()]);
			bind_method_by_name();
			NEXT;
		}
		case OP_TASK:
			bind_task_from_closure();
			NEXT;
		case OP_PERFORM:
			perform(pop());
			NEXT;
		case OP_PERFORM_EXEC:
			switch (TOP.type) {
			case VAL_NIL: YIELD(NIL_VAL);
			case VAL_CLOSURE:
			{
				closure = AS_CLOSURE(pop());
				assert(0 == closure->function->arity);
				vm.stackTop = base;
				goto enter;
			}
			case VAL_MESSAGE:
			case VAL_BOUND:
				enqueue_message(TOP);
				YIELD(NIL_VAL);
			default:
				crashAndBurn("Can't yet handle a %s action.", valKind[TOP.type]);
			}
		case OP_SKIP:
			push(NIL_VAL);  // Something that will get treated as an empty action.
			NEXT;
		default:
			runtimeError(vpc, base, "Unrecognized instruction %d.", vpc[-1]);
		}
	}
}

#undef LEAP
#undef SKIP_AND_POP
#undef READ_BYTE
#undef NEXT

Value force(Value value) {
	if (IS_THUNK(value)) {
		Closure *thunk_ptr = AS_CLOSURE(value);
		if DID_SNAP(thunk_ptr) {
			return SNAP_RESULT(thunk_ptr);
		}
		else {
			// Thunk has yet to be snapped.
			push(value);
			Value result = run(thunk_ptr);
			thunk_ptr = AS_CLOSURE(pop());
			SNAP_RESULT(thunk_ptr) = result;
			thunk_ptr->header.kind = &KIND_snapped;  // Lest a snapped thunk somehow survives GC?
			// That last assignment probably serves more to align code with cache lines.
			return result;
		}
	}
	else return value;
}

