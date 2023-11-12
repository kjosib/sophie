#pragma once

#include "common.h"
#include "opcodes.h"

/* scanner.h */

typedef enum {
	// Single-character tokens.
	TOKEN_PIPE,
	TOKEN_LEFT_PAREN, TOKEN_RIGHT_PAREN,
	TOKEN_LEFT_BRACE, TOKEN_RIGHT_BRACE,
	TOKEN_LEFT_BRACKET, TOKEN_RIGHT_BRACKET,
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
#include "opcodes.h"

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

/* compiler.h */

void initLexicon();
void compile(const char *source);  // ( -- closure )


