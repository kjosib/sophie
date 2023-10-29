#include <stdarg.h>
#include <math.h>
#include <time.h>
#include "common.h"

#define CLOSURE (vm.frame->closure)


VM vm;

static void grey_the_vm_roots() {
	// Grey the value stack
	darkenValues(vm.stack, vm.stackTop - vm.stack);
	// Grey the globals
	darkenTable(&vm.globals);
	// Grey the call frame stack
	if (vm.frame) {
		for (CallFrame *frame = vm.frames; frame <= vm.frame; frame++) {
			darken_in_place(&frame->closure);
		}
	}
}


static Value clockNative(Value *args) {
	return NUMBER_VAL((double)clock() / CLOCKS_PER_SEC);
}

static Value absNative(Value *args) {
	return NUMBER_VAL(fabs(AS_NUMBER(args[0])));
}

static Value sqrtNative(Value *args) {
	return NUMBER_VAL(sqrt(AS_NUMBER(args[0])));
}

static void resetStack() {
	vm.stackTop = vm.stack;
	vm.frame = vm.frames;
}

static InterpretResult runtimeError(byte *vpc, const char *format, ...) {
	va_list args;
	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);
	fputs("\n", stderr);
	vm.frame->ip = vpc;
	for (CallFrame *frame = vm.frames; frame <= vm.frame; frame++) {
		Function *function = CLOSURE->function;
		size_t offset = frame->ip - function->chunk.code.at - 1;
		int line = findLine(&function->chunk, offset);
		String *name = name_of_function(function);
		fprintf(stderr, "[line %d] in %s\n", line, (name ? name->text : "<script>"));
	}

	resetStack();
	return INTERPRET_RUNTIME_ERROR;
}

void defineGlobal(String *name, Value value) {
	if (!tableSet(&vm.globals, name, value)) {
		error("Global name already exists");
	}
}

static void defineNative(const char *name, byte arity, NativeFn function) {
	push(GC_VAL(import_C_string(name, strlen(name))));
	Native *native = newNative(arity, function);
	native->name = AS_STRING(TOP);
	defineGlobal(native->name, GC_VAL(native));
	pop();
}

static void prepare_panic_frame() {
	// Allocate a panic frame at the foundation of the call stack.
	// That way any accidental return from global scope is properly caught.
	vm.frames[0] = (CallFrame){
		.closure = NULL,
		.ip = "",  // Null terminator equals panic opcode.
		.base = vm.stack,
	};
}

void initVM() {
	prepare_panic_frame();
	resetStack();
	initTable(&vm.globals);
	initTable(&vm.strings);

	gc_install_roots(grey_the_vm_roots);

	defineNative("clock", 0, clockNative);
	defineNative("abs", 1, absNative);
	defineNative("sqrt", 1, sqrtNative);
#ifdef DEBUG_PRINT_GLOBALS
	tableDump(&vm.globals);
#endif // DEBUG_PRINT_GLOBALS
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

void displayStack() {
	printf("          ");
	displaySomeValues(vm.stack, (vm.frame->base - vm.stack));
	printf("/ ");
	displaySomeValues(vm.frame->base, (vm.stackTop - vm.frame->base));
	printf("( ");
	displaySomeValues(CLOSURE->captives, CLOSURE->function->nr_captures);
	printf(") ");
	printf("\n");
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

static double fib(double n) {
	// A theoretical maximum
	return n < 2 ? n : fib(n - 1) + fib(n - 2);
}

#define CONSTANT(index) (CLOSURE->function->chunk.constants.at[index])
#define LOCAL(index) (vm.frame->base[index])

static void capture_closure(Closure *closure) {
	// Precondition: *closure points to a fresh Closure object with no captures.
	Function *fn = closure->function;
	for (int index = 0; index < fn->nr_captures; index++) {
		Capture capture = fn->captures[index];
		Value *capture_base = capture.is_local ? vm.frame->base : CLOSURE->captives;
		closure->captives[index] = capture_base[capture.offset];
	}
	// Postcondition: Captures have been copied per directives in *closure's function.
}

#define NEXT goto dispatch
#define READ_BYTE() (*vpc++)
#define READ_CONSTANT() CONSTANT(READ_BYTE())
#define LEAP() do { vpc += word_at(vpc); } while (0)
#define SKIP() do { pop(); vpc += 2; } while(0)
#define BINARY_OP(valueType, op) \
    if (isTwoNumbers()) { \
		db = AS_NUMBER(pop()); \
		da = AS_NUMBER(pop()); \
		push(valueType(da op db)); \
    } else return runtimeError(vpc, "Operands must be numbers."); \
	NEXT; \

static InterpretResult run() {

	register byte *vpc = vm.frame->ip;

dispatch:
	for (;;) {

#ifdef DEBUG_TRACE_EXECUTION
		displayStack();
		disassembleInstruction(&CLOSURE->function->chunk, (int)(vpc - CLOSURE->function->chunk.code.at));
#endif // DEBUG_TRACE_EXECUTION

		switch (READ_BYTE()) {
			double da, db;
		case OP_PANIC:
			return runtimeError(vpc, "PANIC instruction encountered.");
		case OP_CONSTANT:
			push(READ_CONSTANT());
			NEXT;
		case OP_POP: pop(); NEXT;
		case OP_GLOBAL:
		{
			String *key = AS_STRING(READ_CONSTANT());
			if (tableGet(&vm.globals, key, vm.stackTop)) {
				vm.stackTop++;
				NEXT;
			}
			else {
				tableDump(&vm.globals);
				tableDump(&vm.strings);
				return runtimeError(vpc, "Undefined global '%s'.", key->text);
			}
		}
		case OP_LOCAL:
			push(LOCAL(READ_BYTE()));
			NEXT;
		case OP_CAPTIVE: push(CLOSURE->captives[READ_BYTE()]); NEXT;
		case OP_CLOSURE: {
			// Initialize a run of closures. The underlying function definitions are in the constant table.
			int constant_index = READ_BYTE();
			int nr_closures = READ_BYTE();
			Value *base = vm.stackTop;
			memcpy(base, &CONSTANT(constant_index), sizeof(Value) * nr_closures);
			vm.stackTop += nr_closures;
			for (int index = 0; index < nr_closures; index++) close_function(&base[index]);
			for (int index = 0; index < nr_closures; index++) capture_closure(base[index].as.ptr);
			NEXT;
		}
		case OP_TRUE: push(BOOL_VAL(true)); NEXT;
		case OP_FALSE: push(BOOL_VAL(false)); NEXT;
		case OP_EQUAL:
			SND = BOOL_VAL(valuesEqual(SND, TOP));
			pop();
			NEXT;
		case OP_GREATER:  BINARY_OP(BOOL_VAL, > )
		case OP_LESS:     BINARY_OP(BOOL_VAL, < )
		case OP_POWER:
			if (isTwoNumbers()) {
				db = AS_NUMBER(pop());
				da = AS_NUMBER(pop());
				push(NUMBER_VAL(pow(da, db)));
				NEXT;
			}
			else return runtimeError(vpc, "Operands must be numbers.");
		case OP_MULTIPLY: BINARY_OP(NUMBER_VAL, *)
		case OP_DIVIDE:   BINARY_OP(NUMBER_VAL, / )
		case OP_ADD: {
			if (isTwoNumbers()) {
				db = AS_NUMBER(pop());
				da = AS_NUMBER(pop());
				push(NUMBER_VAL(da + db));
				NEXT;
			}
			else return runtimeError(vpc, "Operands must be two numbers or two strings.");
		}
		case OP_SUBTRACT: BINARY_OP(NUMBER_VAL, -)
		case OP_NOT:
			push(BOOL_VAL(!AS_BOOL(pop())));
			NEXT;
		case OP_NEGATE:
			if (IS_NUMBER(TOP)) {
				push(NUMBER_VAL(-AS_NUMBER(pop())));
				NEXT;
			}
			else return runtimeError(vpc, "Operand must be a number.");
		case OP_CALL:
			if (IS_GC(TOP)) {
				vm.frame->ip = vpc;
				GC *item = AS_GC(pop());
				item->kind->call(item);
				vpc = vm.frame->ip;
				NEXT;
			}
			return runtimeError(vpc, "Needed a callable object; got val %s.", valKind[TOP.type]);
		case OP_EXEC:
			if (IS_GC(TOP)) {
				GC *item = AS_GC(pop());
				item->kind->exec(item);
				vpc = vm.frame->ip;
				NEXT;
			}
			return runtimeError(vpc, "Needed a callable object; got val %s.", valKind[TOP.type]);
		case OP_RETURN:
			*vm.frame->base = TOP;
			vm.stackTop = vm.frame->base + 1;
			vm.frame--;
			vpc = vm.frame->ip;
			NEXT;
		case OP_QUIT: {
#ifdef DEBUG_TRACE_EXECUTION
			displayStack();
#endif // DEBUG_TRACE_EXECUTION
			resetStack();
			printf("\n");
			return INTERPRET_OK;
		}
		case OP_DISPLAY:
			printValue(pop());
			printf("\n");
			NEXT;
		case OP_FIB:
			printf("%g\n", fib(AS_NUMBER(pop())));
			NEXT;
		case OP_JF:
			if (AS_BOOL(TOP)) SKIP();
			else LEAP();
			NEXT;
		case OP_JT:
			if (AS_BOOL(TOP)) LEAP();
			else SKIP();
			NEXT;
		case OP_JMP:
			LEAP();
			NEXT;
		default:
			return runtimeError(vpc, "Unrecognized instruction.");
		}
	}
}

#undef CHECK_UNDERFLOW
#undef BINARY_OP
#undef LOCAL
#undef CONSTANT
#undef LEAP
#undef SKIP
#undef READ_CONSTANT
#undef READ_BYTE
#undef NEXT

InterpretResult interpret(const char *source) {
	resetStack();
	Closure *closure = compile(source);
	closure->header.kind->call(closure);
	return run();
}

