#include "common.h"

Parser parser;

static void errorAt(Token *token, const char *message) {
	fprintf(stderr, "[line %d] Error", token->line);

	if (token->type == TOKEN_EOF) {
		fprintf(stderr, " at end");
	}
	else if (token->type == TOKEN_ERROR) {
		// Nothing.
	}
	else {
		fprintf(stderr, " at '%.*s'", token->length, token->start);
	}

	fprintf(stderr, ": %s\n", message);
	crashAndBurn("there's no point");
}

void error(const char *message) {
	errorAt(&parser.previous, message);
}

void errorAtCurrent(const char *message) {
	errorAt(&parser.current, message);
}

void advance() {
	parser.previous = parser.current;

	for (;;) {
		parser.current = scanToken();
		if (parser.current.type != TOKEN_ERROR) break;

		errorAtCurrent(parser.current.start);
	}
}

void consume(TokenType type, const char *message) {
	if (parser.current.type == type) advance();
	else errorAtCurrent(message);
}

ObjString *parseString() {
	consume(TOKEN_STRING, "Need a string here");
	return copyString(parser.previous.start + 1, parser.previous.length - 2);
}

double parseDouble() {
	consume(TOKEN_NUMBER, "Need a number here");
	return strtod(parser.previous.start, NULL);
}

Value parseConstant() {
	if (predictToken(TOKEN_NUMBER)) {
		return NUMBER_VAL(parseDouble());
	}
	else if (predictToken(TOKEN_STRING)) {
		return OBJ_VAL(parseString());
	}
	else {
		errorAtCurrent("Expected a literal constant.");
		return NIL_VAL;
	}
}
