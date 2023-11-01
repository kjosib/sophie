#include "common.h"

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
static bool isAtEnd() { return *scanner.current == '\0'; }
static char ahead() { scanner.current++; return scanner.current[-1]; }
static char peek() { return *scanner.current; }
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

static Token name() {
	while (isAlpha(peek()) || isDigit(peek())) ahead();
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

Token scanToken() {
	skipWhitespace();
	scanner.start = scanner.current;

	if (isAtEnd()) return makeToken(TOKEN_EOF);

	char c = ahead();
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
	case '.': return makeToken(TOKEN_DOT);
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

