#include "common.h"

DEFINE_VECTOR_CODE(Code, byte)
DEFINE_VECTOR_APPEND(Code, byte)

DEFINE_VECTOR_CODE(Lines, Bound)
DEFINE_VECTOR_APPEND(Lines, Bound)

Bound BEGIN_LINES = { .start=0, .line=-1 };
Bound END_LINES = { .start=SIZE_MAX, .line=-1 };

void initChunk(Chunk *chunk) {
	initCode(&chunk->code);
	initValueArray(&chunk->constants);
	initLines(&chunk->lines);
	appendLines(&chunk->lines, BEGIN_LINES);
	appendLines(&chunk->lines, END_LINES);
}

void freeChunk(Chunk *chunk) {
	freeCode(&chunk->code);
	freeValueArray(&chunk->constants);
	freeLines(&chunk->lines);
}

void setLine(Chunk *chunk, int line) {
	size_t pos = chunk->code.cnt;
	Bound *prior = &chunk->lines.at[chunk->lines.cnt - 2];
	if (pos == prior->start) {
		prior->line = line;
	}
	else if (prior->line != line) {
		Bound nextBound = { .start = chunk->code.cnt, .line = line };
		chunk->lines.at[chunk->lines.cnt - 2] = nextBound;
		appendLines(&chunk->lines, END_LINES);
	}
}


int findLine(Chunk *chunk, size_t offset) {
	// Return the line corresponding to the bound with the greatest start not after offset.
	// Linear search is fine; this shouldn't happen often.
	Bound *at = &chunk->lines.at[chunk->lines.cnt - 1];
	while (at->start > offset) at--;
	return at->line;
}
