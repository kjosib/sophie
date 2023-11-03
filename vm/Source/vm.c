#include <stdarg.h>
#include <math.h>
#include <time.h>
#include "common.h"

#define CLOSURE (vm.trace->closure)


VM vm;
static String *cons;
static String *nil;

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
	darken_in_place(&cons);
	darken_in_place(&nil);
}


static void resetStack() {
	vm.stackTop = vm.stack;
	vm.trace = vm.traces-1;
}

void defineGlobal(String *name, Value value) {
	if (!tableSet(&vm.globals, name, value)) {
		error("Global name already exists");
	}
}

void initVM() {
	resetStack();
	initTable(&vm.globals);
	initTable(&vm.strings);
	cons = import_C_string("cons", 4);
	nil = import_C_string("nil", 3);
	gc_install_roots(grey_the_vm_roots);
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


static void concatenate() {
	String *dst = new_String(AS_STRING(SND)->length + AS_STRING(TOP)->length);
	// Allocation took place: Refresh pointers.
	String *a = AS_STRING(SND);
	String *b = AS_STRING(TOP);
	memcpy(dst->text, a->text, a->length);
	memcpy(dst->text + a->length, b->text, b->length);
	SND.as.ptr = intern_String(dst);
	pop();
}

static inline bool isTwoNumbers() { return IS_NUMBER(TOP) && IS_NUMBER(SND); }

static void capture_closure(Closure *closure, int first, Value *base) {
	// Precondition: *closure points to a fresh Closure object with no captures.
	Function *fn = closure->function;
	for (int index = first; index < fn->nr_captures; index++) {
		Capture capture = fn->captures[index];
		Value *capture_base = capture.is_local ? base : CLOSURE->captives;
		closure->captives[index] = capture_base[capture.offset];
	}
	// Postcondition: Captures have been copied per directives in *closure's function.
}


static void push_global(String *key) {
	if (tableGet(&vm.globals, key, vm.stackTop)) {
		vm.stackTop++;
	}
	else {
		crashAndBurn("Missing global: %s", key->text);
	}
}


static Instance *construct() {
	int nr_fields = AS_CTOR(TOP)->nr_fields;
	Instance *instance = gc_allocate(&KIND_Instance, size_for_nr_fields(nr_fields));
	instance->constructor = AS_CTOR(pop());
	memcpy(&instance->fields, vm.stackTop - nr_fields, sizeof(Value) * nr_fields);
	return instance;
}

static double num(Value it) {
	assert(IS_NUMBER(it));
	return AS_NUMBER(it);
}

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
		case OP_CONSTANT:
			push(constants[READ_BYTE()]);
			NEXT;
		case OP_POP: pop(); NEXT;
		case OP_GLOBAL: push_global(AS_STRING(constants[READ_BYTE()])); NEXT;
		case OP_LOCAL: {
			int index = READ_BYTE();
			assert(base + index < vm.stackTop);  // Some day, let compiler.c discern max stack usage per function, and check only once.
			push(base[index]);
			NEXT;
		}

		case OP_CAPTIVE: push(vm.trace->closure->captives[READ_BYTE()]); NEXT;
		case OP_CLOSURE: {
			// Initialize a run of closures. The underlying function definitions are in the constant table.
			int constant_index = READ_BYTE();
			int nr_closures = READ_BYTE();
			Value *slot = vm.stackTop;
			memcpy(slot, constants+constant_index, sizeof(Value) * nr_closures);
			vm.stackTop += nr_closures;
			for (int index = 0; index < nr_closures; index++) close_function(&slot[index]);
			for (int index = 0; index < nr_closures; index++) capture_closure(AS_CLOSURE(slot[index]), 0, base);
			NEXT;
		}
		case OP_THUNK: {
			push(constants[READ_BYTE()]);
			close_function(&TOP);
			AS_CLOSURE(TOP)->captives[0] = NIL_VAL;
			capture_closure(AS_CLOSURE(TOP), 1, base);
			TOP.type = VAL_THUNK;
			NEXT;
		}
		case OP_NIL: push_global(nil); NEXT;
		case OP_TRUE: push(BOOL_VAL(true)); NEXT;
		case OP_FALSE: push(BOOL_VAL(false)); NEXT;
		case OP_EQUAL:
			SND = BOOL_VAL(valuesEqual(SND, TOP));
			pop();
			NEXT;
		case OP_GREATER:  BINARY_OP(BOOL_VAL, > );
		case OP_LESS:     BINARY_OP(BOOL_VAL, < );
		case OP_POWER:
				SND = NUMBER_VAL(pow(AS_NUMBER(SND), AS_NUMBER(TOP)));
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
			TOP = NUMBER_VAL(-AS_NUMBER(TOP));
		case OP_CALL:
			if (IS_CLOSURE(TOP)) push(run(AS_CLOSURE(pop())));  // The callee will clean the stack.
			else if (IS_CTOR(TOP)) {
				Instance *instance = construct();
				Value *slot = vm.stackTop - instance->constructor->nr_fields;
				*slot = GC_VAL(instance);
				vm.stackTop = slot + 1;
			}
			else if (IS_NATIVE(TOP)) {
				Native *native = AS_NATIVE(pop());
				Value *slot = vm.stackTop - native->arity;
				*slot = native->function(slot);
				vm.stackTop = slot + 1;
			}
			else {
				printValue(TOP);
				runtimeError(vpc, base, "CALL needs a callable object; got %s.", valKind[TOP.type]);
			}
			NEXT;
		case OP_EXEC:
			if (IS_CLOSURE(TOP)) {
				Closure *subsequent = vm.trace->closure = AS_CLOSURE(pop());
				constants = subsequent->function->chunk.constants.at;
				vpc = subsequent->function->chunk.code.at;
				int arity = subsequent->function->arity;
				memmove(base, vm.stackTop - arity, arity * sizeof(Value));
				vm.stackTop = base + arity;
				NEXT;
			}
			else if (IS_CTOR(TOP)) {
				YIELD(GC_VAL(construct()));
			}
			else if (IS_NATIVE(TOP)) {
				Native *native = AS_NATIVE(pop());
				YIELD(native->function(vm.stackTop - native->arity));
			}
			else runtimeError(vpc, base, "EXEC needs a callable object; got val %s.", valKind[TOP.type]);
		case OP_RETURN: {
			assert(! IS_THUNK(TOP));  // Return values are needed values! Don't thunk them.
			YIELD(TOP);
		}
		case OP_FORCE:
			TOP = force(TOP);
			NEXT;
		case OP_DISPLAY:
			printValueDeeply(TOP);
			pop();
			printf("\n");
			NEXT;
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
		case OP_CASE: {
			int tag;
			switch (TOP.type) {
			case VAL_ENUM:
				tag = TOP.as.tag;
				break;
			case VAL_GC: {
				Instance *instance = TOP.as.ptr;
				tag = instance->constructor->tag;
				break;
			}
			default:
				runtimeError(vpc, base, "Need a case-able object; got val %s.", valKind[TOP.type]);
			}
			vpc += 2 * tag;
			LEAP();
			NEXT;
		}
		case OP_FIELD: {
			assert(TOP.type == VAL_GC);
			Instance *instance = TOP.as.ptr;
			assert(instance->header.kind == &KIND_Instance);
			Table *field_offset = &instance->constructor->field_offset;
			tableGet(field_offset, AS_STRING(constants[READ_BYTE()]), &TOP);
			TOP = instance->fields[TOP.as.tag];
			NEXT;
		}
		case OP_SNOC: {
			// Swap the top two elements;
			Value tmp = TOP;
			TOP = SND;
			SND = tmp;
			// Construct a "cons" in the usual way
			push_global(cons);
			Instance *instance = construct();
			// Fix up the stack
			pop();
			TOP = GC_VAL(instance);
			// And begone
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

