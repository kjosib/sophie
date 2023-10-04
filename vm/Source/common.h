#pragma once

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// #define DEBUG_PRINT_CODE
// #define DEBUG_TRACE_EXECUTION

#define UINT8_COUNT (UINT8_MAX + 1)

#define DEFINE_VECTOR_TYPE(kind, type) \
    typedef struct { size_t cnt; size_t cap; type *at; } kind; \
    void init   ## kind(kind* vec); \
    void free   ## kind(kind* vec); \
    void resize ## kind(kind* vec, size_t cap); \
    size_t  append ## kind(kind* vec, type item);

__declspec(noreturn) void crashAndBurn(char *why);

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
void freeObjects();

/* value.h */

typedef struct Obj Obj;
typedef struct ObjString ObjString;

typedef enum {
	VAL_BOOL,
	VAL_NIL,
	VAL_NUMBER,
	VAL_ENUM,
	VAL_OBJ,
} ValueType;

typedef struct {
	ValueType type;
	union {
		bool boolean;
		double number;
		int tag;
		Obj *obj;
		void *ptr;
	} as;
} Value;


#define IS_BOOL(value)    ((value).type == VAL_BOOL)
#define IS_NIL(value)     ((value).type == VAL_NIL)
#define IS_NUMBER(value)  ((value).type == VAL_NUMBER)
#define IS_ENUM(value)    ((value).type == VAL_ENUM)
#define IS_OBJ(value)     ((value).type == VAL_OBJ)

#define AS_BOOL(value)    ((value).as.boolean)
#define AS_NUMBER(value)  ((value).as.number)
#define AS_ENUM(value)    ((value).as.tag)
#define AS_OBJ(value)     ((value).as.obj)

#define BOOL_VAL(value)   ((Value){VAL_BOOL, {.boolean = value}})
#define NIL_VAL	          ((Value){VAL_NIL, {.number = 0}})
#define NUMBER_VAL(value) ((Value){VAL_NUMBER, {.number = value}})
#define ENUM_VAL(value)   ((Value){VAL_ENUM, {.number = value}})
#define OBJ_VAL(object)   ((Value){VAL_OBJ, {.obj = (Obj*)object}})

DEFINE_VECTOR_TYPE(ValueArray, Value)

void printValue(Value value);
bool valuesEqual(Value a, Value b);

/* chunk.h */

typedef struct {
	size_t start;
	int line;
} Bound;

DEFINE_VECTOR_TYPE(Code, uint8_t)
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

/* debug.h */

void disassembleChunk(Chunk *chunk, const char *name);
int disassembleInstruction(Chunk *chunk, int offset);

/* object.h */

#define OBJ_TYPE(value)        (AS_OBJ(value)->type)

#define IS_FUNCTION(value)     isObjType(value, OBJ_FUNCTION)
#define IS_NATIVE(value)       isObjType(value, OBJ_NATIVE)
#define IS_STRING(value)       isObjType(value, OBJ_STRING)

#define AS_FUNCTION(value)     ((ObjFunction*)AS_OBJ(value))
#define AS_NATIVE(value)       (((ObjNative*)AS_OBJ(value)))
#define AS_STRING(value)       ((ObjString*)AS_OBJ(value))
#define AS_CSTRING(value)      (((ObjString*)AS_OBJ(value))->chars)


typedef enum {
	OBJ_FUNCTION,
	OBJ_NATIVE,
	OBJ_STRING,
} ObjType;

struct Obj {
	ObjType type;
	struct Obj *next;
};

typedef enum {
	TYPE_FUNCTION,
	TYPE_SCRIPT,
} FunctionType;

typedef struct {
	Obj obj;
	uint8_t arity;
	FunctionType type;
	Chunk chunk;
	ObjString *name;
	ValueArray children;
} ObjFunction;


typedef Value(*NativeFn)(Value *args);

typedef struct {
	Obj obj;
	uint8_t arity;
	NativeFn function;
} ObjNative;

struct ObjString {
	Obj obj;
	int length;
	char *chars;
	uint32_t hash;
};

ObjFunction *newFunction(FunctionType type, uint8_t arity, ObjString *name);
ObjNative *newNative(uint8_t arity, NativeFn function);
ObjString *takeString(char *chars, int length);
ObjString *copyString(const char *chars, int length);
void printObject(Value value);

static inline bool isObjType(Value value, ObjType type) {
	return IS_OBJ(value) && AS_OBJ(value)->type == type;
}

/* scanner.h */

typedef enum {
	// Single-character tokens.
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
	TOKEN_AND, TOKEN_CLASS, TOKEN_ELSE, TOKEN_FALSE,
	TOKEN_FOR, TOKEN_FUN, TOKEN_IF, TOKEN_NIL, TOKEN_OR,
	TOKEN_PRINT, TOKEN_RETURN, TOKEN_SUPER, TOKEN_THIS,
	TOKEN_TRUE, TOKEN_VAR, TOKEN_WHILE,

	TOKEN_ERROR, TOKEN_EOF
} TokenType;

typedef struct {
	TokenType type;
	const char *start;
	int length;
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
double parseDouble();
Value parseConstant();
ObjString *parseString();

static inline bool predictToken(TokenType type) { return type == parser.current.type; }

/* isa.h */

typedef enum {
	OP_CONSTANT,
	OP_POP,
	OP_NIL,
	OP_TRUE,
	OP_FALSE,
	OP_GET_GLOBAL,
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
	OP_RETURN,
	OP_DISPLAY,
	OP_FIB,
	OP_QUIT,
	OP_PARAM,
	OP_JF,
	OP_JT,
	OP_JMP,
	NR_OPCODES,
} OpCode;

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


/* table.h */

typedef struct {
	ObjString *key;
	Value value;
} Entry;

DEFINE_VECTOR_TYPE(Table, Entry)

bool tableGet(Table *table, ObjString *key, Value *value);
bool tableSet(Table *table, ObjString *key, Value value);
void tableAddAll(Table *from, Table *to);
Entry *tableFindString(Table *table, const char *chars, int length, uint32_t hash);

/* vm.h */

#define FRAMES_MAX 64
#define STACK_MAX (FRAMES_MAX * UINT8_COUNT)
#define STACK_MIN UINT8_COUNT

#define WORD_AT(ptr) (*((uint16_t *)(ptr)))

typedef struct {
	ObjFunction *function;
	uint8_t *ip;
	Value *base;
} CallFrame;

typedef struct {
	CallFrame frames[FRAMES_MAX + 1];
	int frameIndex;

	Value stack[STACK_MAX];
	Value *stackTop;
	Table globals;
	Table strings;
	Obj *objects;
} VM;


typedef enum {
	INTERPRET_OK,
	INTERPRET_COMPILE_ERROR,
	INTERPRET_RUNTIME_ERROR
} InterpretResult;

void declareGlobal(ObjString *name);
void defineGlobal(ObjString *name, Value value);

extern VM vm;

void initVM();
void freeVM();
InterpretResult interpret(const char *source);
void push(Value value);
Value pop();

/* compiler.h */

//typedef struct {
//	Token name;
//	int depth;
//} Local;

void initLexicon();
ObjFunction *compile(const char *source);
