#include "common.h"
#include "prep.h"

typedef struct {
	const char *start;
	const char *current;
	int line;
} Scanner;

Scanner scanner;

void initScanner(const char *source) {
	scanner.start = source;
	scanner.current = source;
	scanner.line = 1;
}

static bool isAlpha(char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'; }
static bool isDigit(char c) { return c >= '0' && c <= '9'; }
static void ahead() { scanner.current++; }
static char peek() { return *scanner.current; }
static bool isAtEnd() { return peek() == '\0'; }
static char peekNext() { return isAtEnd() ? '\0' : scanner.current[1]; }

static bool match(char expected) {
	if (isAtEnd()) return false;
	if (*scanner.current != expected) return false;
	scanner.current++;
	return true;
}

static Token makeToken(TokenType type) {
	int length = (int)(scanner.current - scanner.start);
	Token token = { .type = type, .start = scanner.start, .length = length, .line = scanner.line, };
	return token;
}

static Token errorToken(const char *message) {
	Token token = {
		.type = TOKEN_ERROR,
		.start = message,
		.length = (int)strlen(message),
		.line = scanner.line,
	};
	return token;
}

static void skipWhitespace() {
	for (;;) {
		char c = peek();
		switch (c) {
		case ' ':
		case '\r':
		case '\t':
			ahead();
			break;
		case '\n':
			scanner.line++;
			ahead();
			break;
		break;
		default:
			return;
		}
	}
}

static void takeAlphaNumeric() {
	while (isAlpha(peek()) || isDigit(peek())) ahead();
}

static Token name() {
	takeAlphaNumeric();
	return makeToken(TOKEN_NAME);
}

static Token number() {
	while (isDigit(peek())) ahead();

	// Look for a fractional part.
	if (peek() == '.' && isDigit(peekNext())) {
		// Consume the ".".
		ahead();

		while (isDigit(peek())) ahead();
	}

	// Look for an exponent:
	if (peek() == 'E' || peek() == 'e') {
		ahead();
		if (peek() == '+' || peek() == '-') ahead();
		while (isDigit(peek())) ahead();
	}

	return makeToken(TOKEN_NUMBER);
}

static Token string() {
	while (peek() != '"' && !isAtEnd()) {
		if (peek() == '\n') scanner.line++;
		ahead();
	}

	if (isAtEnd()) return errorToken("Unterminated string.");

	// The closing quote.
	ahead();
	return makeToken(TOKEN_STRING);
}

static TokenType directive() {
	takeAlphaNumeric();
	int64_t len = scanner.current - scanner.start;
	switch (len) {
	case 3:
		if (!memcmp(scanner.start, ".fn", len)) return TOKEN_FN;
		break;
	case 4:
		if (!memcmp(scanner.start, ".sub", len)) return TOKEN_SUB;
		if (!memcmp(scanner.start, ".cap", len)) return TOKEN_CAPTURE;
		if (!memcmp(scanner.start, ".end", len)) return TOKEN_END;
		if (!memcmp(scanner.start, ".ffi", len)) return TOKEN_FFI;
		break;
	case 5:
		if (!memcmp(scanner.start, ".line", len)) return TOKEN_LINE;
		if (!memcmp(scanner.start, ".data", len)) return TOKEN_DATA;
		if (!memcmp(scanner.start, ".file", len)) return TOKEN_FILE;
		break;
	case 6:
		if (!memcmp(scanner.start, ".actor", len)) return TOKEN_ACTOR;
		if (!memcmp(scanner.start, ".begin", len)) return TOKEN_BEGIN;
		break;
	case 7:
		if (!memcmp(scanner.start, ".method", len)) return TOKEN_METHOD;
		if (!memcmp(scanner.start, ".vtable", len)) return TOKEN_VTABLE;
		break;
	}
	return TOKEN_ERROR;
}

Token scanToken() {
	skipWhitespace();
	scanner.start = scanner.current;

	if (isAtEnd()) return makeToken(TOKEN_EOF);

	char c = peek();
	ahead();
	if (isAlpha(c)) return name();
	if (isDigit(c)) return number();

	switch (c) {
	case '|': return makeToken(TOKEN_PIPE);
	case '(': return makeToken(TOKEN_LEFT_PAREN);
	case ')': return makeToken(TOKEN_RIGHT_PAREN);
	case '[': return makeToken(TOKEN_LEFT_BRACKET);
	case ']': return makeToken(TOKEN_RIGHT_BRACKET);
	case '{': return makeToken(TOKEN_LEFT_BRACE);
	case '}': return makeToken(TOKEN_RIGHT_BRACE);
	case ';': return makeToken(TOKEN_SEMICOLON);
	case ',': return makeToken(TOKEN_COMMA);
	case '.': return makeToken(isAlpha(peek()) ? directive() : TOKEN_DOT);
	case '-': return isDigit(peek()) ? number() : makeToken(TOKEN_MINUS);
	case '+': return makeToken(TOKEN_PLUS);
	case '/': return makeToken(TOKEN_SLASH);
	case '*': return makeToken(TOKEN_STAR);
	case '!': return makeToken(match('=') ? TOKEN_BANG_EQUAL : TOKEN_BANG);
	case '=': return makeToken(match('=') ? TOKEN_EQUAL_EQUAL : TOKEN_EQUAL);
	case '<': return makeToken(match('=') ? TOKEN_LESS_EQUAL : TOKEN_LESS);
	case '>': return makeToken(match('=') ? TOKEN_GREATER_EQUAL : TOKEN_GREATER);
	case '"': return string();
	}

	return errorToken("Unexpected character.");
}

