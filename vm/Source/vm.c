#include <stdarg.h>
#include <math.h>
#include <time.h>
#include "common.h"
#include "opcodes.h"

#define CLOSURE (vm.trace->closure)


VM vm;
static Value cons;
static Value nil;

static void grey_the_vm_roots() {
	// Grey the value stack
	darkenValues(vm.stack, vm.stackTop - vm.stack);
	// Grey the globals
	darkenTable(&vm.globals);
	// Grey the call frame stack
	if (vm.trace) {
		for (Trace *trace = vm.traces; trace <= vm.trace; trace++) {
			darken_in_place(&trace->closure);
		}
	}
	// Grey the special cases "cons" and "nil"
	darkenValue(&cons);
	darkenValue(&nil);
}


static void resetStack() {
	vm.stackTop = vm.stack;
	vm.trace = vm.traces-1;
}

void defineGlobal() {
	String *name = AS_STRING(pop());
	assert(is_string(name));
	if (!tableSet(&vm.globals, name, TOP)) {
		crashAndBurn("Global name \"%s\" already exists", name->text);
	}
}

void initVM() {
	resetStack();
	initTable(&vm.globals);
	initTable(&vm.strings);
	cons = nil = NIL_VAL;
	gc_install_roots(grey_the_vm_roots);
}

static Value global_from_C(const char *text) {
	return tableGet(&vm.globals, import_C_string(text, strlen(text)));
}

void vm_capture_preamble_specials() {
	cons = global_from_C("cons");
	nil = global_from_C("nil");
}

void freeVM() {
	freeTable(&vm.globals);
	freeTable(&vm.strings);
}

static void displaySomeValues(Value *first, size_t count) {
	for (size_t index = 0; index < count; index++) {
		printf("[");
		printValue(first[index]);
		printf("] ");
	}
}

void displayStack(Value *base) {
	printf(" %s         ", vm.trace->closure->function->name->text);
	displaySomeValues(vm.stack, (base - vm.stack));
	printf("------- ");
	displaySomeValues(base, (vm.stackTop - base));
	printf("---( ");
	displaySomeValues(CLOSURE->captives, CLOSURE->function->nr_captures);
	printf(")\n");
}


__declspec(noreturn) void runtimeError(byte *vpc, Value *base, const char *format, ...) {
	va_list args;
	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);
	fputs("\n", stderr);
	displayStack(base);
	fputs("-----------\n", stderr);
	Function *function = vm.trace->closure->function;
	size_t offset = vpc - function->chunk.code.at - 1;
	int line = findLine(&function->chunk, offset);

	for (Trace *frame = vm.traces; frame <= vm.trace; frame++) {
		fprintf(stderr, "in %s\n", frame->closure->function->name->text);
	}
	fprintf(stderr, "[Line %d]\n", line);
	crashAndBurn("of a runtime error");
}


static inline bool isTwoNumbers() { return IS_NUMBER(TOP) && IS_NUMBER(SND); }

static void capture_closure(Closure *closure, Value *base) {
	// Precondition: *closure points to a fresh Closure object with no captures.
	Function *fn = closure->function;
	int index = 0;
	if (!fn->arity) closure->captives[index++] = NIL_VAL;
	for (; index < fn->nr_captures; index++) {
		Capture capture = fn->captures[index];
		Value *capture_base = capture.is_local ? base : CLOSURE->captives;
		closure->captives[index] = capture_base[capture.offset];
	}
	// Postcondition: Captures have been copied per directives in *closure's function.
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


#define NEXT goto dispatch
#define READ_BYTE() (*vpc++)
#define LEAP() do { vpc += word_at(vpc); } while (0)
#define SKIP_AND_POP() do { pop(); vpc += 2; } while(0)
#define BINARY_OP(valueType, op) do { SND = valueType(num(SND) op num(TOP)); pop(); NEXT; } while (0)
#define YIELD(value) do { Value retval = (value); vm.stackTop = base; vm.trace--; return retval; } while (0)

Value run(Closure *closure) {
	if (vm.trace == &vm.traces[FRAMES_MAX]) crashAndBurn("Max recursion depth exceeded.");
	vm.trace++;
	vm.trace->closure = closure;
	Value *base = vm.stackTop - closure->function->arity;
	Value *constants = closure->function->chunk.constants.at;
	byte *vpc = closure->function->chunk.code.at;

	// At this point, closure becomes invalid because allocations can happen.

	assert(base >= vm.stack);  // If this fails, the script died of stack underflow.

	for (;;) {
dispatch:

#ifdef DEBUG_TRACE_EXECUTION
		printf("-----------------\n");
		displayStack(base);
		printf("%s > ", name_of_function(vm.trace->closure->function)->text);
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
			assert(base + index < vm.stackTop);  // Some day, let compiler.c discern max stack usage per function, and check only once.
			push(base[index]);
			NEXT;
		}

		case OP_CAPTIVE: push(vm.trace->closure->captives[READ_BYTE()]); NEXT;
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
		case OP_NIL: push(nil); NEXT;
		case OP_TRUE: push(BOOL_VAL(true)); NEXT;
		case OP_FALSE: push(BOOL_VAL(false)); NEXT;
		case OP_EQUAL:
			SND = BOOL_VAL(valuesEqual(SND, TOP));
			pop();
			NEXT;
		case OP_GREATER:  BINARY_OP(BOOL_VAL, > );
		case OP_LESS:     BINARY_OP(BOOL_VAL, < );
		case OP_POWER:
				SND = NUMBER_VAL(pow(num(SND), num(TOP)));
				pop();
				NEXT;
		case OP_MULTIPLY: BINARY_OP(NUMBER_VAL, * );
		case OP_DIVIDE:   BINARY_OP(NUMBER_VAL, / );
		case OP_ADD:      BINARY_OP(NUMBER_VAL, + );
		case OP_SUBTRACT: BINARY_OP(NUMBER_VAL, - );
		case OP_NOT:
			TOP = BOOL_VAL(!AS_BOOL(TOP));
			NEXT;
		case OP_NEGATE:
			TOP = NUMBER_VAL(-num(TOP));
			NEXT;
		case OP_CALL:
			switch (TOP.type) {
			case VAL_CLOSURE:
				push(run(AS_CLOSURE(pop())));  // The callee will clean the stack.
				NEXT;
			case VAL_CTOR:
			{
				Record *record = construct_record();
				Value *slot = vm.stackTop - record->constructor->nr_fields;
				*slot = GC_VAL(record);
				vm.stackTop = slot + 1;
				NEXT;
			}
			case VAL_NATIVE:
			{
				Native *native = AS_NATIVE(pop());
				Value *slot = vm.stackTop - native->arity;
				*slot = native->function(slot);
				vm.stackTop = slot + 1;
				NEXT;
			}
			case VAL_BOUND:
			{
				apply_bound_method();
				NEXT;
			}
			default:
				printValue(TOP);
				runtimeError(vpc, base, "CALL needs a callable object; got %s.", valKind[TOP.type]);
			}
		case OP_EXEC:
			switch (TOP.type) {
			case VAL_CLOSURE:
			case VAL_THUNK:
			{
				Closure *subsequent = vm.trace->closure = AS_CLOSURE(pop());
				constants = subsequent->function->chunk.constants.at;
				vpc = subsequent->function->chunk.code.at;
				int arity = subsequent->function->arity;
				memmove(base, vm.stackTop - arity, arity * sizeof(Value));
				vm.stackTop = base + arity;
				NEXT;
			}
			case VAL_CTOR:
				YIELD(GC_VAL(construct_record()));
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
				Closure *subsequent = vm.trace->closure = AS_CLOSURE(pop());
				// Has it been snapped?
				if (IS_NIL(subsequent->captives[0])) {
					// No...
					// Treat this like an exec / tail-call, but easier since arity is zero by definition.
					constants = subsequent->function->chunk.constants.at;
					vpc = subsequent->function->chunk.code.at;
					vm.stackTop = base;
					NEXT;
				}
				else {
					// Yes...
					YIELD(subsequent->captives[0]);
					NEXT;
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
			case VAL_BOUND:
			case VAL_MESSAGE:
				enqueue_message_from_top_of_stack();
				drain_the_queue();
				NEXT;
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
			push(cons);
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
			Table *msg_handler = &AS_ACTOR(TOP)->actor_dfn->msg_handler;
			push(tableGet(msg_handler, AS_STRING(constants[READ_BYTE()])));
			bind_method();
			NEXT;
		}
		default:
			runtimeError(vpc, base, "Unrecognized instruction %d.", vpc[-1]);
		}
	}
}

#undef CHECK_UNDERFLOW
#undef BINARY_OP
#undef CONSTANT
#undef LEAP
#undef SKIP
#undef READ_CONSTANT
#undef READ_BYTE
#undef NEXT

Value force(Value value) {
	if (IS_THUNK(value)) {
		if (IS_NIL(AS_CLOSURE(value)->captives[0])) {
			// Thunk has yet to be snapped.
			push(value);
			Value snapped = run(AS_CLOSURE(value));
			AS_CLOSURE(pop())->captives[0] = snapped;
			return snapped;
		}
		else return AS_CLOSURE(value)->captives[0];
	}
	else return value;
}

