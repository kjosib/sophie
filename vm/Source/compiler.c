#include "common.h"

static ValueArray scopes;
static ObjFunction *current;
static uint16_t patchLink;

#define PTR_VAL(x) ((Value){VAL_NIL, {.ptr = x}})

typedef void (*Verb)(void *dfn);

typedef struct {
	Verb *verb;
	AsmFn operand;
	uint8_t opcode;
} AsmWord;

typedef struct {
	Verb *verb;
	char *name;
} CplWord;

static void emit(uint8_t byte) { appendCode(&current->chunk.code, byte); }

static void emitHole() {
	// This trick should work regardless of endianness.
	uint8_t *trick = (uint8_t *)(&patchLink);
	// Grow the vector one byte at a time to keep its invariants happy.
	emit(trick[0]);
	emit(trick[1]);
	// The cast will be fine because chunks larger than 64k are banned anyway.
	patchLink = (uint16_t)(current->chunk.code.cnt - 2);
}

static void writeWordAt(uint16_t offset, uint16_t word) {
	// Should work regardless of endianness.
	// May be trouble if CPU requires alignment.
	uint16_t *target = (uint16_t *)(&current->chunk.code.at[offset]);
	*target = word;
}

uint16_t readWordAt(uint16_t offset) {
	// Should work regardless of endianness.
	// May be trouble if CPU requires alignment.
	uint16_t *target = (uint16_t *)(&current->chunk.code.at[offset]);
	return *target;
}

static void patchJump(size_t target) {
	uint16_t prior = readWordAt(patchLink);
	// writeWordAt(patchLink, target);
	writeWordAt(patchLink, (uint16_t)(target - patchLink));
	patchLink = prior;
}

static void compileAnd(CplWord *dfn) {
	emit(OP_JF);
	emitHole();
}

static void compileOr(CplWord *dfn) {
	emit(OP_JT);
	emitHole();
}

static void compileElse(CplWord *dfn) {
	if (!patchLink) error("else without criteria");
	emit(OP_JMP);
	patchJump(current->chunk.code.cnt + 2);
	emitHole();
	emit(OP_POP);
}

static void compileIf(CplWord *dfn) {
	if (!patchLink) error("if without criteria");
	patchJump(current->chunk.code.cnt);
}

AsmWord asmWords[NR_OPCODES];
CplWord cplWords[] = {
	{compileAnd, "and"},
	{compileOr, "or"},
	{compileElse, "else"},
	{compileIf, "if"},
};
Table lexicon;

static void asmOne(AsmWord *dfn) {
	emit(dfn->opcode);
	dfn->operand(&current->chunk);
}

void initLexicon() {
	initTable(&lexicon);
	for (int i = 0; i < NR_OPCODES; i++) {
		ObjString *key = copyString(instruction[i].name, strlen(instruction[i].name));
		asmWords[i] = (AsmWord){ .verb = asmOne, .operand = instruction[i].operand->assemble, .opcode = i };
		tableSet(&lexicon, key, PTR_VAL(&asmWords[i]));
	}
	for (int i = 0; i < _countof(cplWords); i++) {
		ObjString *key = copyString(cplWords[i].name, strlen(cplWords[i].name));
		tableSet(&lexicon, key, PTR_VAL(&cplWords[i]));
	}
}

static void initCompiler() {
	patchLink = 0;
	initValueArray(&scopes);
	appendValueArray(&scopes, OBJ_VAL(newFunction(TYPE_SCRIPT, 0, copyString("<script>", 8))));
	current = AS_FUNCTION(scopes.at[0]);
}

static bool finished() { return parser.current.type == TOKEN_EOF; }

static void startFunction() {
	if (patchLink) error("must resolve forward branches before starting a function");
	uint8_t arity = (uint8_t)parseDouble("arity");
	ObjString *name = parseString();
	if (1 == scopes.cnt) declareGlobal(name);
	current = newFunction(TYPE_FUNCTION, arity, name);
	appendValueArray(&scopes, OBJ_VAL(current));
}

static void checkPatchLinkage() {
	if (patchLink) error("must resolve forward branches before finishing a function");
}

static void parseUpvalueLinkages(int nr_captures) {
	while (nr_captures--) {
		int type;
		if (predictToken(TOKEN_NAME)) {
			consume(TOKEN_NAME, "");
			type = VAL_CAPTURE_LOCAL;
			printf("Local ");
		}
		else {
			type = VAL_CAPTURE_OUTER;
			printf("Outer ");
		}
		Value capture = { type, {.tag = parseDouble("Capture") } };
		printf("%d\n", capture.as.tag);
		appendValueArray(&current->captures, capture);
	}
}

static void parseVitalStatistics() {
	current->nr_locals = parseDouble("number of additional stack slots to reserve for locals");
	parseUpvalueLinkages(parseDouble("number of captures"));
	consume(TOKEN_SEMICOLON, "Semicolon to delimit the end of the stats");
}

static void checkSizeLimits() {
	if (current->chunk.code.cnt > UINT16_MAX) error("function is too long");
	if (current->chunk.constants.cnt > UINT8_MAX) error("function has too many constants");
	if (current->children.cnt > UINT8_MAX) error("function has too many children");
	if (current->captures.cnt > UINT8_MAX) error("function has too many captures");
}

static void finishFunction() {
#ifdef DEBUG_PRINT_CODE
	disassembleChunk(&current->chunk, current->name->chars);
#endif


	checkPatchLinkage();
	parseVitalStatistics();
	checkSizeLimits();

	// Insert function into its containing scope.
	ObjFunction *function = current;
	scopes.cnt--;
	current = AS_FUNCTION(scopes.at[scopes.cnt - 1]);
	switch (current->type) {
	case TYPE_SCRIPT:
		defineGlobal(function->name, OBJ_VAL(newClosure(function)));
		break;
	case TYPE_FUNCTION:
		appendValueArray(&current->children, OBJ_VAL(function));
		break;
	default:
		error("Houston, we have a problem.");
	}
}

static bool predictConstant() { return predictToken(TOKEN_NUMBER) || predictToken(TOKEN_STRING); }

static void parseScript() {
	while (!finished()) {
		Chunk *chunk = &current->chunk;
		if (predictToken(TOKEN_NAME)) {
			advance();
			uint32_t hash = hashString(parser.previous.start, parser.previous.length);
			Entry *entry = tableFindString(&lexicon, parser.previous.start, parser.previous.length, hash);
			if (entry == NULL) error("bogus code");
			else {
				Verb *dfn = (Verb *)(entry->value.as.ptr);
				(*dfn)(dfn);
			}
		}
		else if (predictToken(TOKEN_LEFT_BRACE)) {
			advance();
			startFunction();
		}
		else if (predictToken(TOKEN_RIGHT_BRACE)) {
			advance();
			if (1 == scopes.cnt) {
				error("close without open");
			}
			else {
				emit(OP_RETURN);
				finishFunction();
			}
		}
		else {
			errorAtCurrent("expected instruction");
		}
	}
	emit(OP_QUIT);
}


ObjFunction *compile(const char *source) {
	initScanner(source);
	initCompiler();
	advance();
	parseScript();
	consume(TOKEN_EOF, "Expect end of expression.");
	freeValueArray(&scopes);
	return current;
}

