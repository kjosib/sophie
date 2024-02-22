#pragma once
#include "common.h"

typedef enum {
	OP_PANIC,
	OP_CONSTANT,
	OP_POP,
	OP_NIL,
	OP_TRUE,

	OP_FALSE,
	OP_GLOBAL,
	OP_LOCAL,
	OP_CAPTIVE,
	OP_CLOSURE,

	OP_EQUAL,
	OP_GREATER,
	OP_LESS,
	OP_CMP,
	OP_CMP_EXEC,

	OP_POWER,
	OP_MULTIPLY,
	OP_DIVIDE,
	OP_INTDIV,
	OP_MODULUS,

	OP_ADD,
	OP_SUBTRACT,
	OP_NOT,
	OP_NEGATE,
	OP_CALL,

	OP_EXEC,
	OP_RETURN,
	OP_FORCE,
	OP_FORCE_RETURN,
	OP_STRICT,

	OP_JF,
	OP_JT,
	OP_JMP,
	OP_CASE,
	OP_DISPLAY,

	OP_FIELD,
	OP_SNOC,
	OP_THUNK,
	OP_BIND,
	OP_TASK,

	OP_PERFORM,
	OP_PERFORM_EXEC,
	OP_SKIP,
	OP_CAST,
	OP_MEMBER,

	OP_ASSIGN,

	NR_OPCODES,
} OpCode;


typedef void (*AsmFn)(Chunk *chunk);
typedef int (*DisFn)(Chunk *chunk, int offset);

typedef struct {
	AsmFn assemble;
	DisFn disassemble;
} AddressingMode;

typedef struct {
	char *name;
	AddressingMode *operand;
} Instruction;

extern Instruction instruction[];


