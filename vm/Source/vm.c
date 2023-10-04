#include <stdarg.h>
#include <math.h>
#include <time.h>
#include "common.h"

VM vm;

static Value clockNative(Value* args) {
	return NUMBER_VAL((double)clock() / CLOCKS_PER_SEC);
}

static void resetStack() {
	vm.stackTop = vm.stack;
	vm.frameIndex = -1;
}

static InterpretResult runtimeError(uint8_t *vpc, const char *format, ...) {
	va_list args;
	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);
	fputs("\n", stderr);
	vm.frames[vm.frameIndex].ip = vpc;
	for (int i = 0; i <= vm.frameIndex; i++) {
		CallFrame *frame = &vm.frames[i];
		ObjFunction *function = frame->function;
		size_t offset = frame->ip - function->chunk.code.at - 1;
		int line = findLine(&function->chunk, offset);
		char *name = function->name == NULL ? "<script>" : function->name->chars;
		fprintf(stderr, "[line %d] in %s\n", line, name);
	}

	resetStack();
	return INTERPRET_RUNTIME_ERROR;
}

static void defineNative(const char* name, uint8_t arity, NativeFn function) {
	push(OBJ_VAL(copyString(name, (int)strlen(name))));
	push(OBJ_VAL(newNative(arity, function)));
	tableSet(&vm.globals, AS_STRING(vm.stack[0]), vm.stack[1]);
	pop();
	pop();
}

void initVM() {
	resetStack();
	vm.objects = NULL;
	initTable(&vm.globals);
	initTable(&vm.strings);

	defineNative("clock", 0, clockNative);
}

void freeVM() {
	freeTable(&vm.globals);
	freeTable(&vm.strings);
	freeObjects();
}

void declareGlobal(ObjString *name) {
	if (!tableSet(&vm.globals, name, NIL_VAL)) {
		error("Global name already exists");
	}
}

void defineGlobal(ObjString *name, Value value) {
	if (tableSet(&vm.globals, name, value)) {
		error("Global name does not exist");
	}
}

static inline void push(Value value) {
	*vm.stackTop = value;
	vm.stackTop++;
}

static inline Value pop() {
	vm.stackTop--;
	return *vm.stackTop;
}

static inline Value peek(int distance) {
	return vm.stackTop[-1 - distance];
}

void displayStack() {
	printf("          ");
	for (Value *slot = vm.stack; slot < vm.stackTop; slot++) {
		printf("[ ");
		printValue(*slot);
		printf(" ]");
	}
	printf("\n");
}

static void concatenate() {
	ObjString *b = AS_STRING(pop());
	ObjString *a = AS_STRING(pop());

	int length = a->length + b->length;
	char *chars = ALLOCATE(char, length + 1);
	memcpy(chars, a->chars, a->length);
	memcpy(chars + a->length, b->chars, b->length);
	chars[length] = '\0';

	ObjString *result = takeString(chars, length);
	push(OBJ_VAL(result));
}

static inline bool isTwoNumbers() { return IS_NUMBER(peek(0)) && IS_NUMBER(peek(1)); }
static inline bool isTwoStrings() { return IS_STRING(peek(0)) && IS_STRING(peek(1)); }

static inline uint16_t readShort(CallFrame *frame) {
	frame->ip += 2;
	return (uint16_t)((frame->ip[-2] << 8) | frame->ip[-1]);
}

static CallFrame *callFunction(ObjFunction *function) {
	/*
	The VPC in the current call-frame has already been
	incremented to point just past this instruction.
	A callable object should be on the stack.
	Create a call-frame and set it to work.
	*/
	vm.frameIndex++;
	CallFrame *frame = &vm.frames[vm.frameIndex];
	frame->function = function;
	frame->ip = function->chunk.code.at;
	frame->base = vm.stackTop - function->arity;
	return frame;
}

static double fib(double n) {
	// A theoretical maximum
	return n < 2 ? n : fib(n - 1) + fib(n - 2);
}

static inline bool outOfCallFrames() { return vm.frameIndex >= FRAMES_MAX; }
static inline bool tooShallow(uint8_t arity) { return vm.stackTop - vm.stack < arity; }

static InterpretResult run(CallFrame *frame) {

	register uint8_t *vpc = frame->ip;

#define NEXT goto top
#define READ_BYTE() (*vpc++)
#define READ_CONSTANT() (frame->function->chunk.constants.at[READ_BYTE()])
#define READ_WORD() (*((uint16_t *)(vpc)))
// #define LEAP() do { vpc = &frame->function->chunk.code.at[READ_WORD()]; } while (0)
#define LEAP() do { vpc += READ_WORD(); } while (0)
#define SKIP() do { pop(); vpc += 2; } while(0)
#define BINARY_OP(valueType, op) \
    if (isTwoNumbers()) { \
		db = AS_NUMBER(pop()); \
		da = AS_NUMBER(pop()); \
		push(valueType(da op db)); \
    } else return runtimeError(vpc, "Operands must be numbers."); \
	NEXT; \

	top:
	for (;;) {

#ifdef DEBUG_TRACE_EXECUTION
		displayStack();
		disassembleInstruction(&frame->function->chunk, (int)(vpc - frame->function->chunk.code.at));
#endif // DEBUG_TRACE_EXECUTION

		uint8_t instruction = READ_BYTE();
		switch (instruction) {
			double da, db;
			Value va, vb;
		case OP_CONSTANT:
			push(READ_CONSTANT());
			NEXT;
		case OP_POP: pop(); NEXT;
		case OP_GET_GLOBAL:
			va = READ_CONSTANT();
			if (IS_STRING(va)) {
				Value value;
				if (tableGet(&vm.globals, AS_STRING(va), &value)) {
					push(value);
					NEXT;
				}
				else return runtimeError(vpc, "Undefined global '%s'.", AS_CSTRING(va));
			} else return runtimeError(vpc, "Operand must be string.");
		case OP_TRUE: push(BOOL_VAL(true)); NEXT;
		case OP_FALSE: push(BOOL_VAL(false)); NEXT;
		case OP_EQUAL:
			vb = pop();
			va = pop();
			push(BOOL_VAL(valuesEqual(va, vb)));
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
			} else if (isTwoStrings()) {
				concatenate();
				NEXT;
			}
			else return runtimeError(vpc, "Operands must be two numbers or two strings.");
		}
		case OP_SUBTRACT: BINARY_OP(NUMBER_VAL, -)
		case OP_NOT:
			push(BOOL_VAL(!AS_BOOL(pop())));
			NEXT;
		case OP_NEGATE:
			if (IS_NUMBER(peek(0))) {
				push(NUMBER_VAL(-AS_NUMBER(pop())));
				NEXT;
			} else return runtimeError(vpc, "Operand must be a number.");
		case OP_CALL:
			va = pop();
			if (IS_OBJ(va)) switch (OBJ_TYPE(va)) {
			case OBJ_FUNCTION:
				if (outOfCallFrames()) return runtimeError(vpc, "Call depth exceeded");
				if (tooShallow(AS_FUNCTION(va)->arity)) return runtimeError(vpc, "Stack underflow calling %s", AS_FUNCTION(va)->name->chars);
				frame->ip = vpc;
				frame = callFunction(AS_FUNCTION(va));
				vpc = frame->ip;
				NEXT;
			case OBJ_NATIVE:
				vb = AS_NATIVE(va)->function(vm.stackTop - AS_NATIVE(va)->arity);
				if (tooShallow(AS_NATIVE(va)->arity)) return runtimeError(vpc, "Stack underflow");
				vm.stackTop -= AS_NATIVE(va)->arity;
				push(vb);
				NEXT;
			}
			return runtimeError(vpc, "Needed a callable object.");
		case OP_RETURN:
			va = pop();
			vm.stackTop = frame->base;
			push(va);
			if (vm.frameIndex) {
				vm.frameIndex--;
				frame = &vm.frames[vm.frameIndex];
				vpc = frame->ip;
				NEXT;
			}
			else return runtimeError(vpc, "RETURN WITHOUT GOSUB");
		case OP_QUIT: {
			displayStack();
			resetStack();
			printf("\n");
			return INTERPRET_OK;
		}
		case OP_DISPLAY:
			printValue(pop());
			NEXT;
		case OP_FIB:
			printf("%g", fib(AS_NUMBER(pop())));
			NEXT;
		case OP_PARAM:
			push(frame->base[READ_BYTE()]);
			NEXT;
		case OP_JF:
			if (AS_BOOL(peek(0))) SKIP();
			else LEAP();
			NEXT;
		case OP_JT:
			if (AS_BOOL(peek(0))) LEAP();
			else SKIP();
			NEXT;
		case OP_JMP:
			LEAP();
			NEXT;
		default:
			return runtimeError(vpc, "Unrecognized instruction.");
		}
	}

#undef BINARY_OP
#undef READ_CONSTANT
#undef READ_BYTE
}

InterpretResult interpret(const char *source) {
	resetStack();
	ObjFunction *function = compile(source);
	if (function == NULL) return INTERPRET_COMPILE_ERROR;
	else return run(callFunction(function));
}

