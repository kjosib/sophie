#include "common.h"
#include "prep.h"

static void asmSimple(Chunk *chunk) {
}

static int disSimple( Chunk *chunk, int offset) {
	byte opcode = chunk->code.at[offset++];
	printf("%s\n", instruction[opcode].name);
	return offset;
}

static void asmConstant(Chunk *chunk) {
	size_t index = appendValueArray(&chunk->constants, parseConstant());
	if (index > UINT8_MAX) error("too many constants in a chunk");
	appendCode(&chunk->code, (byte)(index));
}

static void asmString(Chunk *chunk) {
	size_t index = appendValueArray(&chunk->constants, GC_VAL(parseString()));
	appendCode(&chunk->code, (byte)(index));
}

static void asmGlobal(Chunk *chunk) {
	size_t index = appendValueArray(&chunk->constants, GLOBAL_VAL(parseString()));
	appendCode(&chunk->code, (byte)(index));
}

static int disConstant(Chunk *chunk, int offset) {
	byte opcode = chunk->code.at[offset++];
	byte operand = chunk->code.at[offset++];
	printf("%-16s %4d '", instruction[opcode].name, operand);
	printValue(chunk->constants.at[operand]);
	printf("\n");
	return offset;
}

static void asmImmediate(Chunk *chunk) {
	appendCode(&chunk->code, parseByte("Argument"));
}

static int disImmediate(Chunk *chunk, int offset) {
	byte opcode = chunk->code.at[offset++];
	byte operand = chunk->code.at[offset++];
	printf("%-16s #%4d\n", instruction[opcode].name, operand);
	return offset;
}

static int disJump(Chunk *chunk, int offset) {
	byte opcode = chunk->code.at[offset++];
	uint16_t operand = offset + word_at(&chunk->code.at[offset]);
	printf("%-16s  %4d\n", instruction[opcode].name, operand);
	return offset + 2;
}

static void asmNotByHand(Chunk *chunk) {
	error("This instruction is meant to be built automatically.");
}

static int disClosure(Chunk *chunk, int offset) {
	byte opcode  = chunk->code.at[offset++];
	int nr_closures = chunk->code.at[offset++];
	int child_index = chunk->code.at[offset++];
	printf("%-16s   %3d %3d\n", instruction[opcode].name, nr_closures, child_index);
	return offset;
}

static int disCase(Chunk *chunk, int offset) {
	byte opcode  = chunk->code.at[offset++];
	printf("%-16s ", instruction[opcode].name);
	// Now pick up operands and use them to find the start of the first consequent.
	// There must be at least one:
	int limit = offset + word_at(&chunk->code.at[offset]);

	for (; offset < limit; offset += 2) {
		int target = offset + word_at(&chunk->code.at[offset]);
		printf(" %4d", target);
		if (target < limit) limit = target;
	}

	printf("\n");
	return limit;
}

AddressingMode modeSimple = { asmSimple, disSimple };
AddressingMode modeConstant = { asmConstant, disConstant };
AddressingMode modeString = { asmString, disConstant };
AddressingMode modeGlobal = { asmGlobal, disConstant };
AddressingMode modeImmediate = { asmImmediate, disImmediate };
AddressingMode modeJump = {asmSimple, disJump};
AddressingMode modeClosure = {asmNotByHand, disClosure};
AddressingMode modeCase = {asmSimple, disCase};
AddressingMode modeThunk = {asmNotByHand, disConstant};

Instruction instruction[] = {
	[OP_PANIC] = {"PANIC", &modeSimple},
	[OP_CONSTANT] = {"CONST", &modeConstant},
	[OP_POP] = {"POP", &modeSimple},
	[OP_NIL] = {"NIL", &modeSimple},
	[OP_TRUE] = {"TRUE", &modeSimple},

	[OP_FALSE] = {"FALSE", &modeSimple},
	[OP_GLOBAL] = {"GLOBAL", &modeGlobal},
	[OP_LOCAL] = {"LOCAL", &modeImmediate},
	[OP_CAPTIVE] = {"CAPTIVE", &modeImmediate},
	[OP_CLOSURE] = {"CLOSURE", &modeClosure},

	[OP_EQUAL] = {"EQ", &modeSimple},
	[OP_GREATER] = {"GT", &modeSimple},
	[OP_LESS] = {"LT", &modeSimple},
	[OP_POWER] = {"POW", &modeSimple},
	[OP_MULTIPLY] = {"MUL", &modeSimple},
	
	[OP_DIVIDE] = {"DIV", &modeSimple},
	[OP_INTDIV] = {"IDIV", &modeSimple},
	[OP_MODULUS] = {"MOD", &modeSimple},
	[OP_ADD] = {"ADD", &modeSimple},
	[OP_SUBTRACT] = {"SUB", &modeSimple},
	
	[OP_NOT] = {"NOT", &modeSimple},
	[OP_NEGATE] = {"NEG", &modeSimple},
	[OP_CALL] = {"CALL", &modeSimple},
	[OP_EXEC] = {"EXEC", &modeSimple},
	[OP_RETURN] = {"RETURN", &modeSimple},
	
	[OP_FORCE] = {"FORCE", &modeSimple},
	[OP_FORCE_RETURN] = {"FORCE_RETURN", &modeSimple},
	[OP_JF] = {"JF", &modeJump},
	[OP_JT] = {"JT", &modeJump},
	[OP_JMP] = {"JMP", &modeJump},
	
	[OP_CASE] = {"CASE", &modeCase},
	[OP_DISPLAY] = {"DISPLAY", &modeSimple},
	[OP_FIELD] = {"FIELD", &modeString},
	[OP_SNOC] = {"SNOC", &modeSimple},
	[OP_THUNK] = {"THUNK", &modeThunk},
	
	[OP_BIND] = {"BIND", &modeString},
	[OP_TASK] = {"TASK", &modeSimple},
	[OP_PERFORM] = {"PERFORM", &modeSimple},
	[OP_PERFORM_EXEC] = {"PERFORM_EXEC", &modeSimple},
	[OP_SKIP] = {"SKIP", &modeSimple},

	[OP_CAST] = {"CAST", &modeSimple},
};

