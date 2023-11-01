#include "common.h"

#define NR_HOLES 4096

typedef struct Scope Scope;

struct Scope {
	Chunk chunk;
	Scope *outer;
};

static Scope *current = NULL;

static uint16_t holes[NR_HOLES];
static Table lexicon;



static void parse_function_block();
static void parse_thunk();




static void grey_the_compiling_roots() {
	darkenTable(&lexicon);
	Scope *scope = current;
	while (scope) {
		darkenChunk(&scope->chunk);
		scope = scope->outer;
	}
}

static void emit(byte code) { appendCode(&current->chunk.code, code); }

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

static void hole() {
	uint16_t *hole_ptr = parseHole();
	if (*hole_ptr) error("Busy hole");
	*hole_ptr = (uint16_t)current->chunk.code.cnt;
	emit(0);
	emit(0);
}

static void come_from() {
	uint16_t *hole_ptr = parseHole();
	uint16_t hole_offset = *hole_ptr;
	if (!hole_offset) error("Unallocated Label");
	uint16_t here = (uint16_t)current->chunk.code.cnt;
	if ( hole_offset + 2 > here || here < 4 || readWordAt(hole_offset)) error("Improper come_from");
	writeWordAt(hole_offset, (uint16_t)(here - hole_offset));
	*hole_ptr = 0;
}

void initLexicon() {
	initTable(&lexicon);
	gc_install_roots(grey_the_compiling_roots);
	for (int index = 0; index < NR_OPCODES; index++) {
		table_set_from_C(&lexicon, instruction[index].name, ENUM_VAL(index));
	}
	table_set_from_C(&lexicon, "hole", PTR_VAL(hole));
	table_set_from_C(&lexicon, "come_from", PTR_VAL(come_from));
}

static void push_new_scope(Scope *outer) {
	current = malloc(sizeof(Scope));
	if (current == NULL) crashAndBurn("oom");
	current->outer = outer;
	initChunk(&current->chunk);
}

static void pop_scope() {
	freeChunk(&current->chunk);
	Scope *old = current;
	current = old->outer;
	free(old);
}

static void initCompiler() {
	memset(holes, 0, sizeof(holes));
	push_new_scope(NULL);
}


static void perform_word(Value value) {
	if (value.type == VAL_ENUM) {
		int index = value.as.tag;
		emit(index);
		instruction[index].operand->assemble(&current->chunk);
	}
	else if (value.type == VAL_PTR) {
		Verb verb = value.as.ptr;
		verb();
	}
	else crashAndBurn("Bogosity in the lexicon");
}


static void parse_one_instruction() {
	uint32_t hash = hashString(parser.previous.start, parser.previous.length);
	Entry *entry = tableFindString(&lexicon, parser.previous.start, parser.previous.length, hash);
	if (entry == NULL) error("bogus code");
	else perform_word(entry->value);
}

static void parse_instructions() {
	for(;;) {
		if (maybe_token(TOKEN_NAME)) parse_one_instruction();
		else if (predictToken(TOKEN_LEFT_BRACE)) parse_function_block();
		else if (maybe_token(TOKEN_LEFT_BRACKET)) parse_thunk();
		else break;
	}
}

static void checkSizeLimits() {
	if (current->chunk.code.cnt > UINT16_MAX) error("function is too long");
	if (current->chunk.constants.cnt > UINT8_MAX) error("function has too many constants");
}

static Function *parse_rest_of_function(byte arity, String *name) {
	appendValueArray(&current->chunk.constants, GC_VAL(name));
	parse_instructions();
	emit(OP_PANIC);
	checkSizeLimits();
	consume(TOKEN_PIPE, "Expected vertical line");
	byte nr_captures = parseByte("Number of captures");
	Function *function = newFunction(TYPE_FUNCTION, &current->chunk, arity, nr_captures);
	// NB: current->chunk has just been re-initialized because the new function now owns the former contents of the chunk.
	for (int index = 0; index < nr_captures; index++) {
		if (maybe_token(TOKEN_STAR)) {
			function->captures[index] = (Capture){ .is_local = true, .offset=0 };
		}
		else {
			byte is_local = predictToken(TOKEN_NAME);
			if (is_local) consume(TOKEN_NAME, "");
			function->captures[index] = (Capture){ .is_local = is_local, .offset = parseByte("Capture") };
		}
	}
#ifdef DEBUG_PRINT_CODE
	disassembleChunk(&function->chunk, name_of_function(function)->text);
#endif
	return function;
}

static void parse_thunk() {
	emit(OP_THUNK);
	emit((byte)current->chunk.constants.cnt);

	Scope *outer = current;
	push_new_scope(outer);
	Function *function = parse_rest_of_function(0, import_C_string("<thunk>", 7));
	appendValueArray(&outer->chunk.constants, GC_VAL(function));
	consume(TOKEN_RIGHT_BRACKET, "expected right-bracket.");
	pop_scope();
}

static Function *parse_normal_function() {
	// The function's name goes in the first constant entry.
	// That way the right garbage collection things happen automatically.
	advance();
	byte arity = parseByte("arity");
	String *name = parseString();
	return parse_rest_of_function(arity, name);
}

static void parse_function_block() {
	// which will also emit into the outer scope sufficient bytecode to bring the closures onto the stack.
	emit(OP_CLOSURE);
	emit((byte)current->chunk.constants.cnt);

	Scope *outer = current;
	push_new_scope(outer);
	int fn_count = 0;
	do {
		fn_count++;
		Function *function = parse_normal_function();
		appendValueArray(&outer->chunk.constants, GC_VAL(function));
	} while (predictToken(TOKEN_SEMICOLON));
	consume(TOKEN_RIGHT_BRACE, "expected semicolon or right-brace.");
	pop_scope();
	emit(fn_count);
}

static Closure *closure_for_global(Function *function) {
	if (function->nr_captures) error("Global functions cannot have captures!");
	push(GC_VAL(function));
	close_function(&TOP);
	return pop().as.ptr;
}

static void parse_global_functions() {
	do {
		Closure *closure = closure_for_global(parse_normal_function());
		defineGlobal(name_of_function(closure->function), GC_VAL(closure));
	} while (predictToken(TOKEN_SEMICOLON));
	consume(TOKEN_RIGHT_BRACE, "expected semicolon or right-brace.");
}

static Value tag_definition(int tag) {
	crashAndBurn("Tagged Values are not yet fully supported");
}

static parse_tagged_value() {
	int tag = parseByte("tag");
	String *name = parseString();
	push(GC_VAL(name));
	defineGlobal(name, tag_definition(tag));
	pop();
}

static void parse_record() {
	// Parse zero or more names. Keep them on the stack. Track how many.
	int nr_fields = 0;
	while (predictToken(TOKEN_NAME)) {
		push(GC_VAL(parseName()));
		nr_fields++;
	}
	int tag = parseByte("tag");
	String *name = parseString();
	Value constructor;
	if (nr_fields) {
		push(GC_VAL(name));
		constructor = GC_VAL(new_constructor(tag, nr_fields));
		// new_constructor(...) pops all those strings off the VM stack,
		// so there's no need to do it here.
	}
	else {
		constructor = ENUM_VAL(tag);
	}
	defineGlobal(name, constructor);
	consume(TOKEN_RIGHT_PAREN, "expected ')'");
}

static void parseScript() {
	while (maybe_token(TOKEN_LEFT_PAREN)) {
		if (maybe_token(TOKEN_STAR)) parse_tagged_value();
		else parse_record();
	}
	while (predictToken(TOKEN_LEFT_BRACE)) parse_global_functions();
	initChunk(&current->chunk);
	appendValueArray(&current->chunk.constants, GC_VAL(import_C_string("<script>", 8)));
	parse_instructions();
	emit(OP_QUIT);
#ifdef DEBUG_PRINT_CODE
	disassembleChunk(&current->chunk, "<script>");
#endif
}


Closure *compile(const char *source) {
	initScanner(source);
	initCompiler();
	advance();
	parseScript();
	consume(TOKEN_EOF, "expected end of file.");
	Closure *closure = closure_for_global(newFunction(TYPE_SCRIPT, &current->chunk, 0, 0));
	pop_scope();
	return closure;
}

