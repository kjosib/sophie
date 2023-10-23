#include "common.h"

void disassembleChunk(Chunk *chunk, const char *name) {
	printf("== %s ==\n", name);
	Bound *run = &chunk->lines.at[0];
	int offset = 0;
	while (offset < chunk->code.cnt) {
		if (offset == run->start) {
			printf("%4d ", run->line);
			run++;
		}
		else {
			printf("   | ");
		}
		offset = disassembleInstruction(chunk, offset);
	}
}

int disassembleInstruction(Chunk *chunk, int offset) {
	byte opcode = chunk->code.at[offset];
	if (opcode < NR_OPCODES) {
		return instruction[opcode].operand->disassemble(chunk, offset);
	}
	else {
		printf("Unknown opcode %d\n", opcode);
		return offset + 1;
	}
}

