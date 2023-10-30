#pragma once

/*

Note on naming style:

The identifiers may look inconsistent. Some are camelCase; others are snake_case.
But there is something of a pattern. Code written on Wednesdays -- no, that's not it.
Functions completely, or nearly, cribbed from Nystrom's book start out in camel case.
And for the first brief while, I kept that for consistency.

However, I find snake_case easier to read and write. So the newer stuff mostly uses it.
Eventually I might enforce a consistent style. But for now, there are bigger fish to fry.

*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef _DEBUG
//#define DEBUG_PRINT_GLOBALS
//#define DEBUG_PRINT_CODE
//#define DEBUG_TRACE_EXECUTION
//#define DEBUG_STRESS_GC
#endif // _DEBUG

#define byte uint8_t
#define BYTE_CARDINALITY 256

#define DEFINE_VECTOR_TYPE(kind, type) \
    typedef struct { size_t cnt; size_t cap; type *at; } kind; \
    void init   ## kind(kind* vec); \
    void free   ## kind(kind* vec); \
    void resize ## kind(kind* vec, size_t cap); \
    size_t  append ## kind(kind* vec, type item);

__declspec(noreturn) void crashAndBurn(char *why);


/* gc.h */

typedef void (*Verb)();
typedef void (*Method)(void *item);
typedef size_t (*SizeMethod)(void *item); // Return the size of the payload.

typedef struct {
	Verb call;
	Verb exec;
	Method display;
	Method blacken;
	SizeMethod size;
} GC_Kind;

typedef union {
	GC_Kind *kind;
	void *ptr;
} GC;

void init_gc();
void gc_install_roots(Verb verb);

void *gc_allocate(GC_Kind *kind, size_t size);
void *darken(void *gc);

static inline void darken_in_place(void **gc) { *gc = darken(*gc); }

/* memory.h */

#define ALLOCATE(type, count) (type*)reallocate(NULL, 0, sizeof(type) * (count))
#define FREE(type, pointer) reallocate(pointer, sizeof(type), 0)
#define FREE_ARRAY(type, pointer, oldCount) reallocate(pointer, sizeof(type) * (oldCount), 0)

#define GROW(cap) ((cap) < 8 ? 8 : (cap) * 2)

#define DEFINE_VECTOR_CODE(Kind, type) \
    void init   ## Kind (Kind *vec)            { vec->cnt = vec->cap = 0; vec->at = NULL; } \
    void free   ## Kind (Kind *vec)            { FREE_ARRAY(type, vec->at, vec->cap); init ## Kind (vec); } \
    void resize ## Kind (Kind *vec, size_t cap){ vec->at = (type*)reallocate(vec->at, sizeof(type) * (vec->cnt), sizeof(type) * cap); vec->cap = cap; }

#define DEFINE_VECTOR_APPEND(Kind, type) \
  size_t append ## Kind (Kind *vec, type item) { if (vec->cap <= vec->cnt) resize ## Kind (vec, GROW(vec->cap)); vec->at[vec->cnt++] = item; return vec->cnt - 1; }

void *reallocate(void *pointer, size_t oldSize, size_t newSize);

/* value.h */

typedef enum {
	VAL_BOOL,
	VAL_NIL,
	VAL_NUMBER,
	VAL_ENUM,
	VAL_GC,     // Garbage-collected pointer.
	VAL_PTR,    // Non-collectable opaque pointer.
} ValueType;


typedef struct {
	ValueType type;
	union {
		bool boolean;
		double number;
		int tag;
		void *ptr;
		GC *gc;
	} as;
} Value;


#define IS_BOOL(value)    ((value).type == VAL_BOOL)
#define IS_NIL(value)     ((value).type == VAL_NIL)
#define IS_NUMBER(value)  ((value).type == VAL_NUMBER)
#define IS_ENUM(value)    ((value).type == VAL_ENUM)
#define IS_GC(value)     ((value).type == VAL_GC)

#define AS_BOOL(value)    ((value).as.boolean)
#define AS_NUMBER(value)  ((value).as.number)
#define AS_ENUM(value)    ((value).as.tag)
#define AS_GC(value)     ((value).as.gc)

#define BOOL_VAL(value)   ((Value){VAL_BOOL, {.boolean = value}})
#define NIL_VAL	          ((Value){VAL_NIL, {.number = 0}})
#define NUMBER_VAL(value) ((Value){VAL_NUMBER, {.number = value}})
#define ENUM_VAL(value)   ((Value){VAL_ENUM, {.tag = value}})
#define GC_VAL(object)   ((Value){VAL_GC, {.ptr = object}})
#define PTR_VAL(object)   ((Value){VAL_PTR, {.ptr = object}})

DEFINE_VECTOR_TYPE(ValueArray, Value)

void printValue(Value value);
bool valuesEqual(Value a, Value b);

static inline darkenValue(Value *value) { if (IS_GC(*value)) darken_in_place(&value->as.ptr); }
void darkenValues(Value *at, size_t count);
void darkenValueArray(ValueArray *vec);

extern char *valKind[];

/* chunk.h */

typedef struct {
	size_t start;
	int line;
} Bound;

DEFINE_VECTOR_TYPE(Code, byte)
DEFINE_VECTOR_TYPE(Lines, Bound)

typedef struct {
	Code code;
	ValueArray constants;
	Lines lines;
} Chunk;

void initChunk(Chunk *chunk);
void freeChunk(Chunk *chunk);
void setLine(Chunk *chunk, int line);
int findLine(Chunk *chunk, size_t offset);

static inline void darkenChunk(Chunk *chunk) { darkenValueArray(&chunk->constants); }

/* debug.h */

void disassembleChunk(Chunk *chunk, const char *name);
int disassembleInstruction(Chunk *chunk, int offset);

/* object.h */

typedef struct {
	GC header;
	uint32_t hash;
	size_t length;
	char text[];
} String;

uint32_t hashString(const char *key, size_t length);
String *new_String(size_t length);
String *intern_String(String *string);
String *import_C_string(const char *chars, size_t length);
void printObject(GC *item);
void bad_callee();

#define AS_STRING(it) ((String *)(it.as.gc))
bool is_string(void *item);

/* table.h */

typedef struct {
	String *key;
	Value value;
} Entry;

DEFINE_VECTOR_TYPE(Table, Entry)

bool tableGet(Table *table, String *key, Value *value);
bool tableSet(Table *table, String *key, Value value);
bool table_set_from_C(Table *table, char *text, Value value);
void tableAddAll(Table *from, Table *to);
Entry *tableFindString(Table *table, const char *chars, size_t length, uint32_t hash);
bool tableDelete(Table *table, String *key);
void darkenTable(Table *table);
void tableDump(Table *table);

/* function.h */

typedef enum {
	TYPE_FUNCTION,
	TYPE_SCRIPT,
} FunctionType;

typedef struct {
	byte is_local;
	byte offset;
} Capture;


typedef struct {
	// Keep child-functions as objects in the constant table.
	GC header;
	byte arity;
	byte nr_captures;
	byte fn_type;
	Chunk chunk;
	Capture captures[];
} Function;


typedef Value(*NativeFn)(Value *args);

typedef struct {
	GC header;
	byte arity;
	NativeFn function;
	String *name;
} Native;

typedef struct {
	GC header;
	Function *function;
	Value captives[];
} Closure;

void close_function(Value *stack_slot);
Function *newFunction(FunctionType fn_type, Chunk *chunk, byte arity, byte nr_captures);
Native *newNative(byte arity, NativeFn function);

String *name_of_function(Function *function);

/* record.h */

typedef struct {
	GC header;
	String *name;
	Table field_offset;
	byte tag;
	byte nr_fields;
} Constructor;

typedef struct {
	GC header;
	Constructor *constructor;
	Value fields[];
} Instance;

Constructor *new_constructor(int tag, int nr_fields);

/* scanner.h */

typedef enum {
	// Single-character tokens.
	TOKEN_PIPE,
	TOKEN_LEFT_PAREN, TOKEN_RIGHT_PAREN,
	TOKEN_LEFT_BRACE, TOKEN_RIGHT_BRACE,
	TOKEN_COMMA, TOKEN_DOT, TOKEN_MINUS, TOKEN_PLUS,
	TOKEN_SEMICOLON, TOKEN_SLASH, TOKEN_STAR,
	// One or two character tokens.
	TOKEN_BANG, TOKEN_BANG_EQUAL,
	TOKEN_EQUAL, TOKEN_EQUAL_EQUAL,
	TOKEN_GREATER, TOKEN_GREATER_EQUAL,
	TOKEN_LESS, TOKEN_LESS_EQUAL,
	// Literals.
	TOKEN_NAME, TOKEN_STRING, TOKEN_NUMBER,
	// Keywords.

	TOKEN_ERROR, TOKEN_EOF
} TokenType;

typedef struct {
	TokenType type;
	const char *start;
	size_t length;
	int line;
} Token;

void initScanner(const char *source);
Token scanToken();

/* parser.h */

typedef struct {
	Token current;
	Token previous;
	bool hadError;
	bool panicMode;
} Parser;

extern Parser parser;

void error(const char *message);
void errorAtCurrent(const char *message);
void advance();
void consume(TokenType type, const char *message);
double parseDouble(const char *message);
byte parseByte(char *message);
Value parseConstant();
String *parseString();
String *parseName();

static inline bool predictToken(TokenType type) { return type == parser.current.type; }
bool maybe_token(TokenType type);

/* isa.h */

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
	OP_POWER,
	OP_MULTIPLY,
	OP_DIVIDE,
	OP_MODULUS,
	OP_INTDIV,
	OP_INTMOD,
	OP_ADD,
	OP_SUBTRACT,
	OP_NOT,
	OP_NEGATE,
	OP_CALL,
	OP_EXEC,
	OP_RETURN,
	OP_DISPLAY,
	OP_FIB,
	OP_QUIT,
	OP_JF,
	OP_JT,
	OP_JMP,
	NR_OPCODES,
} OpCode;

DEFINE_VECTOR_TYPE(Labels, uint16_t)

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

/* vm.h */

#define FRAMES_MAX 64
#define STACK_MAX (FRAMES_MAX * BYTE_CARDINALITY)

static inline uint16_t word_at(const char *ch) {
	uint16_t *ptr = (uint16_t *)(ch);
	return *ptr;
}

typedef struct {
	Closure *closure;
	byte *ip;
	Value *base;
} CallFrame;

typedef struct {
	CallFrame frames[FRAMES_MAX + 1];
	CallFrame *frame;
	Value stack[STACK_MAX];
	Value *stackTop;
	Table globals;
	Table strings;
} VM;


typedef enum {
	INTERPRET_OK,
	INTERPRET_COMPILE_ERROR,
	INTERPRET_RUNTIME_ERROR
} InterpretResult;

void defineGlobal(String *name, Value value);

extern VM vm;

void initVM();
void freeVM();
InterpretResult interpret(const char *source);
static inline void push(Value value) {
	*vm.stackTop = value;
	vm.stackTop++;
}

static inline Value pop() {
	vm.stackTop--;
	return *vm.stackTop;
}

#define TOP (vm.stackTop[-1])
#define SND (vm.stackTop[-2])

/* compiler.h */

void initLexicon();
Closure *compile(const char *source);
