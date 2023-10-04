#include "common.h"

static void asmSimple(Chunk *chunk) {
}

static int disSimple( Chunk *chunk, int offset) {
	uint8_t opcode = chunk->code.at[offset];
	printf("%s\n", instruction[opcode].name);
	return offset + 1;
}

static void asmConstant(Chunk *chunk) {
	size_t index = appendValueArray(&chunk->constants, parseConstant());
	if (index > UINT8_MAX) error("too many constants in a chunk");
	appendCode(&chunk->code, (uint8_t)(index));
}

static int disConstant(Chunk *chunk, int offset) {
	uint8_t opcode = chunk->code.at[offset];
	uint8_t operand = chunk->code.at[offset + 1];
	printf("%-16s %4d '", instruction[opcode].name, operand);
	printValue(chunk->constants.at[operand]);
	printf("\n");
	return offset + 2;
}

static void asmImmediate(Chunk *chunk) {
	appendCode(&chunk->code, (uint8_t)parseDouble());
}

static int disImmediate(Chunk *chunk, int offset) {
	uint8_t opcode = chunk->code.at[offset];
	uint8_t operand = chunk->code.at[offset + 1];
	printf("%-16s #%4d\n", instruction[opcode].name, operand);
	return offset + 2;
}

static void asmJump(Chunk *chunk) {
	error("this instruction is not meant to be assembled by hand");
}

static int disJump(Chunk *chunk, int offset) {
	uint8_t opcode = chunk->code.at[offset];
	uint16_t operand = WORD_AT(1 + offset + chunk->code.at);
	printf("%-16s  %4d\n", instruction[opcode].name, operand);
	return offset + 3;
}

AddressingMode modeSimple = { asmSimple, disSimple };
AddressingMode modeConstant = { asmConstant, disConstant };
AddressingMode modeImmediate = { asmImmediate, disImmediate };
AddressingMode modeJump = {asmJump, disJump};

Instruction instruction[] = {
	[OP_CONSTANT] = {"CONST", &modeConstant},
	[OP_POP] = {"POP", &modeSimple},
	[OP_NIL] = {"NIL", &modeSimple},
	[OP_TRUE] = {"TRUE", &modeSimple},
	[OP_FALSE] = {"FALSE", &modeSimple},
	[OP_GET_GLOBAL] = {"GLOBAL", &modeConstant},
	[OP_EQUAL] = {"EQ", &modeSimple},
	[OP_GREATER] = {"GT", &modeSimple},
	[OP_LESS] = {"LT", &modeSimple},
	[OP_POWER] = {"POW", &modeSimple},
	[OP_MULTIPLY] = {"MUL", &modeSimple},
	[OP_DIVIDE] = {"DIV", &modeSimple},
	[OP_MODULUS] = {"MOD", &modeSimple},
	[OP_INTDIV] = {"IDIV", &modeSimple},
	[OP_INTMOD] = {"IMOD", &modeSimple},
	[OP_ADD] = {"ADD", &modeSimple},
	[OP_SUBTRACT] = {"SUB", &modeSimple},
	[OP_NOT] = {"NOT", &modeSimple},
	[OP_NEGATE] = {"NEG", &modeSimple},
	[OP_CALL] = {"CALL", &modeSimple},
	[OP_RETURN] = {"RET", &modeSimple},
	[OP_DISPLAY] = {"DISPLAY", &modeSimple},
	[OP_FIB] = {"FIB", &modeSimple},
	[OP_QUIT] = {"QUIT", &modeSimple},
	[OP_PARAM] = {"PARAM", &modeImmediate},
	[OP_JF] = {"JF", &modeJump},
	[OP_JT] = {"JT", &modeJump},
	[OP_JMP] = {"JMP", &modeJump},
	//[] = {"", &modeSimple},
};

