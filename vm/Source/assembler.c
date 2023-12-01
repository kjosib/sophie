#include "common.h"
#include "prep.h"

#define NR_HOLES 4096

typedef struct Scope Scope;

struct Scope {
	Chunk chunk;
	Scope *outer;
};

static Scope *current = NULL;

static uint16_t holes[NR_HOLES];
static Table lexicon;

static Table globals;


static void parse_function_block();
static void parse_thunk();



static void grey_the_assembling_roots() {
	darkenTable(&globals);
	darkenTable(&lexicon);
	Scope *scope = current;
	while (scope) {
		darkenChunk(&scope->chunk);
		scope = scope->outer;
	}
}

void defineGlobal() {  // ( value name -- )
	String *name = AS_STRING(pop());
	assert(is_string(name));
	if (!tableSet(&globals, name, pop())) {
		crashAndBurn("Global name \"%s\" already exists", name->text);
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

static void init_assembler() {
	memset(holes, 0, sizeof(holes));
	current = NULL;
	initTable(&lexicon);
	initTable(&globals);
	gc_install_roots(grey_the_assembling_roots);
	for (int index = 0; index < NR_OPCODES; index++) {
		table_set_from_C(&lexicon, instruction[index].name, ENUM_VAL(index));
	}
	table_set_from_C(&lexicon, "hole", PTR_VAL(hole));
	table_set_from_C(&lexicon, "come_from", PTR_VAL(come_from));
}

static void dispose_assembler() {
	gc_forget_roots(grey_the_assembling_roots);
	freeTable(&globals);
	freeTable(&lexicon);
}

static void push_new_scope() {
	Scope *outer = current;
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

static Value parse_rest_of_function(byte arity) {
	parse_instructions();
	emit(OP_PANIC);
	checkSizeLimits();
	consume(TOKEN_PIPE, "Expected vertical line");
	byte nr_captures = parseByte("Number of captures");
	Function *function = newFunction(TYPE_FUNCTION, &current->chunk, arity, nr_captures);
	// NB: current->chunk has just been re-initialized because the new function now owns the former contents of the chunk.
	for (int index = 0; index < nr_captures; index++) {
		if (maybe_token(TOKEN_STAR)) {
			function->fn_type = TYPE_MEMOIZED;
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
	return FN_VAL(function);
}

static void parse_thunk() {
	emit(OP_THUNK);
	emit((byte)current->chunk.constants.cnt);

	Scope *outer = current;
	push_new_scope();
	// Name thunks for their containing function, so duplicate TOP:
	push(TOP);
	appendValueArray(&outer->chunk.constants, parse_rest_of_function(0));
	consume(TOKEN_RIGHT_BRACKET, "expected right-bracket.");
	pop_scope();
}

static Value parse_normal_function() {
	// The function's name goes in the first constant entry.
	// That way the right garbage collection things happen automatically.
	advance();
	byte arity = parseByte("arity");
	push(GC_VAL(parseString()));
	return parse_rest_of_function(arity);
}

static void parse_function_block() {
	// which will also emit into the outer scope sufficient bytecode to bring the closures onto the stack.
	emit(OP_CLOSURE);
	emit((byte)current->chunk.constants.cnt);

	Scope *outer = current;
	push_new_scope();
	int fn_count = 0;
	do {
		fn_count++;
		appendValueArray(&outer->chunk.constants, parse_normal_function());
	} while (predictToken(TOKEN_SEMICOLON));
	consume(TOKEN_RIGHT_BRACE, "expected semicolon or right-brace.");
	pop_scope();
	emit(fn_count);
}


static void parse_global_functions() {
	do {
		push(parse_normal_function());
		close_function(&TOP);
		push(GC_VAL(name_of_function(AS_CLOSURE(TOP)->function)));
		defineGlobal();
	} while (predictToken(TOKEN_SEMICOLON));
	consume(TOKEN_RIGHT_BRACE, "expected semicolon or right-brace.");
}

static Value tag_definition(int tag) {
	crashAndBurn("Tagged Values are not yet fully supported");
	defineGlobal();
}

static parse_tagged_value() {
	int tag = parseByte("tag");
	String *name = parseString();
	push(GC_VAL(name));
	tag_definition(tag);
	pop();
}

static void parse_record() {
	// Parse zero or more names. Keep them on the stack. Track how many.
	int nr_fields = 0;
	while (predictToken(TOKEN_NAME)) {
		push(GC_VAL(parseName()));
		nr_fields++;
	}
	
	if (nr_fields) {
		int tag = parseByte("tag");
		push(GC_VAL(parseString()));
		make_constructor(tag, nr_fields);
		// new_constructor(...) pops all those strings off the VM stack,
		// so there's no need to do it here.
		push(GC_VAL(AS_CTOR(TOP)->name));
	}
	else {
		push(ENUM_VAL(parseByte("tag")));
		push(GC_VAL(parseString()));
	}
	defineGlobal();
	consume(TOKEN_RIGHT_PAREN, "expected ')'");
}

static void parseScript() {
	while (maybe_token(TOKEN_LEFT_PAREN)) {
		if (maybe_token(TOKEN_STAR)) parse_tagged_value();
		else parse_record();
	}
	while (predictToken(TOKEN_LEFT_BRACE)) parse_global_functions();
	initChunk(&current->chunk);
	push(GC_VAL(import_C_string("<script>", 8)));
	parse_instructions();
	emit(OP_RETURN);
#ifdef DEBUG_PRINT_CODE
	disassembleChunk(&current->chunk, "<script>");
#endif
}

static void snap_global_pointers(Function *fn) {
	if (fn->visited) return;
	fn->visited = true;
	for (int index = 0; index < fn->chunk.constants.cnt; index++) {
		Value *item = &fn->chunk.constants.at[index];
		if (IS_GLOBAL(*item)) {
			String *key = AS_STRING(*item);
			Value found = tableGet(&globals, key);
			if (IS_NIL(found)) crashAndBurn("global not found: %s", AS_STRING(*item)->text);
			else *item = found;
		}
		if (IS_CLOSURE(*item) || IS_THUNK(*item)) snap_global_pointers(AS_CLOSURE(*item)->function);
		else if (IS_FN(*item)) snap_global_pointers(AS_FN(*item));
	}
}

void assemble(const char *source) {
	initScanner(source);
	init_assembler();
	install_native_functions();
#ifdef DEBUG_PRINT_GLOBALS
	tableDump(&globals);
#endif // DEBUG_PRINT_GLOBALS
	advance();
	push_new_scope();
	parseScript();
	consume(TOKEN_EOF, "expected end of file.");
	push(FN_VAL(newFunction(TYPE_SCRIPT, &current->chunk, 0, 0)));
	pop_scope();
	close_function(&TOP);
	snap_global_pointers(AS_CLOSURE(TOP)->function);
	vm_capture_preamble_specials(&globals);
	dispose_assembler();
}

