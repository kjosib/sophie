#include "common.h"

#define NR_HOLES 4096

static ValueArray scopes;
static ObjFunction *current;
static uint16_t holes[NR_HOLES];

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

uint16_t *parseHole() {
	int hole_id = (int)(parseDouble("hole ID"));
	if (hole_id < 0 || hole_id >= NR_HOLES) error("Improper hole id");
	return &holes[hole_id];
}

static void hole(CplWord *dfn) {
	uint16_t *hole_ptr = parseHole();
	if (*hole_ptr) error("Busy hole");
	*hole_ptr = (uint16_t)current->chunk.code.cnt;
	emit(0);
	emit(0);
}

static void come_from(CplWord *dfn) {
	uint16_t *hole_ptr = parseHole();
	uint16_t hole_offset = *hole_ptr;
	if (!hole_offset) error("Unallocated Label");
	uint16_t here = (uint16_t)current->chunk.code.cnt;
	if ( hole_offset + 2 > here || here < 4 || readWordAt(hole_offset)) error("Improper come_from");
	writeWordAt(hole_offset, (uint16_t)(here - hole_offset));
	*hole_ptr = 0;
}

AsmWord asmWords[NR_OPCODES];
CplWord cplWords[] = {
	{hole, "hole"},
	{come_from, "come_from"},
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
	memset(holes, 0, sizeof(holes));
	initValueArray(&scopes);
	appendValueArray(&scopes, OBJ_VAL(newFunction(TYPE_SCRIPT, 0, copyString("<script>", 8))));
	current = AS_FUNCTION(scopes.at[0]);
}

static bool finished() { return parser.current.type == TOKEN_EOF; }

static uint8_t parseByte(char *what) {
	return (uint8_t)parseDouble(what);
}

static void startFunction() {
	uint8_t arity = parseByte("arity");
	ObjString *name = parseString();
	if (1 == scopes.cnt) declareGlobal(name);
	current = newFunction(TYPE_FUNCTION, arity, name);
	appendValueArray(&scopes, OBJ_VAL(current));
}

static void parseUpvalueLinkages(int nr_captures) {
	while (nr_captures--) {
		int type;
		if (predictToken(TOKEN_NAME)) {
			consume(TOKEN_NAME, "");
			type = VAL_CAPTURE_LOCAL;
		}
		else {
			type = VAL_CAPTURE_OUTER;
		}
		Value capture = { type, {.tag = parseByte("Capture") } };
		appendValueArray(&current->captures, capture);
	}
}

static void parseVitalStatistics() {
	parseUpvalueLinkages(parseByte("Number of captures"));
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
				emit(OP_PANIC);
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

