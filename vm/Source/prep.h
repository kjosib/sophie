#pragma once

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
	// Directives.
	TOKEN_ACTOR, TOKEN_BEGIN, TOKEN_CAPTURE, TOKEN_DATA,
	TOKEN_END, TOKEN_FFI, TOKEN_FILE, TOKEN_FN,
	TOKEN_LINE, TOKEN_METHOD, TOKEN_VTABLE,
	TOKEN_ADD, TOKEN_SUB, TOKEN_MUL, TOKEN_DIV, TOKEN_NEG, TOKEN_POW, TOKEN_IDIV, TOKEN_MOD, TOKEN_CMP,
	// Other stuff.
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
void parseConstant();  // ( -- value )
void parseString();  // ( -- string )
void parseName();  // ( -- string )

static inline bool predictToken(TokenType type) { return type == parser.current.type; }
bool maybe_token(TokenType type);

/* isa.h */


/* assembler.h */

void assemble(const char *source);  // ( -- closure )


