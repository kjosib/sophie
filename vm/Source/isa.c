#include "common.h"

DEFINE_VECTOR_CODE(Labels, uint16_t)
DEFINE_VECTOR_APPEND(Labels, uint16_t)

static void asmSimple(Chunk *chunk) {
}

static int disSimple( Chunk *chunk, int offset) {
	uint8_t opcode = chunk->code.at[offset++];
	printf("%s\n", instruction[opcode].name);
	return offset;
}

static void asmConstant(Chunk *chunk) {
	size_t index = appendValueArray(&chunk->constants, parseConstant());
	if (index > UINT8_MAX) error("too many constants in a chunk");
	appendCode(&chunk->code, (uint8_t)(index));
}

static int disConstant(Chunk *chunk, int offset) {
	uint8_t opcode = chunk->code.at[offset++];
	uint8_t operand = chunk->code.at[offset++];
	printf("%-16s %4d '", instruction[opcode].name, operand);
	printValue(chunk->constants.at[operand]);
	printf("\n");
	return offset;
}

static void asmImmediate(Chunk *chunk) {
	appendCode(&chunk->code, (uint8_t)parseDouble("Argument"));
}

static int disImmediate(Chunk *chunk, int offset) {
	uint8_t opcode = chunk->code.at[offset++];
	uint8_t operand = chunk->code.at[offset++];
	printf("%-16s #%4d\n", instruction[opcode].name, operand);
	return offset;
}

static int disJump(Chunk *chunk, int offset) {
	uint8_t opcode = chunk->code.at[offset];
	uint16_t operand = word_at(&chunk->code.at[1 + offset]);
	printf("%-16s  %4d\n", instruction[opcode].name, operand);
	return offset + 3;
}

static void asmClosure(Chunk *chunk) {
	appendCode(&chunk->code, (uint8_t)parseDouble("nr_closures"));
	appendCode(&chunk->code, (uint8_t)parseDouble("child_index"));
}

static int disClosure(Chunk *chunk, int offset) {
	uint8_t opcode  = chunk->code.at[offset++];
	int nr_closures = chunk->code.at[offset++];
	int child_index = chunk->code.at[offset++];
	printf("%-16s   %3d %3d\n", instruction[opcode].name, nr_closures, child_index);
	return offset;
}

AddressingMode modeSimple = { asmSimple, disSimple };
AddressingMode modeConstant = { asmConstant, disConstant };
AddressingMode modeImmediate = { asmImmediate, disImmediate };
AddressingMode modeJump = {asmSimple, disJump};
AddressingMode modeClosure = {asmClosure, disClosure};

Instruction instruction[] = {
	[OP_PANIC] = {"PANIC", &modeSimple},
	[OP_CONSTANT] = {"CONST", &modeConstant},
	[OP_POP] = {"POP", &modeSimple},
	[OP_NIL] = {"NIL", &modeSimple},
	[OP_TRUE] = {"TRUE", &modeSimple},
	[OP_FALSE] = {"FALSE", &modeSimple},
	[OP_GLOBAL] = {"GLOBAL", &modeConstant},
	[OP_LOCAL] = {"LOCAL", &modeImmediate},
	[OP_CAPTIVE] = {"CAPTIVE", &modeImmediate},
	[OP_CLOSURE] = {"CLOSURE", &modeClosure},
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
	[OP_EXEC] = {"EXEC", &modeSimple},
	[OP_RETURN] = {"RETURN", &modeSimple},
	[OP_DISPLAY] = {"DISPLAY", &modeSimple},
	[OP_FIB] = {"FIB", &modeSimple},
	[OP_QUIT] = {"QUIT", &modeSimple},
	[OP_JF] = {"JF", &modeJump},
	[OP_JT] = {"JT", &modeJump},
	[OP_JMP] = {"JMP", &modeJump},
	//[] = {"", &modeSimple},
};

