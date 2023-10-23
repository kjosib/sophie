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
		fprintf(stderr, " at '%.*s'", (int)(token->length), token->start);
	}

	fprintf(stderr, ": %s\n", message);
	crashAndBurn("the code-file is ill-formed");
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

String *parseString() {
	consume(TOKEN_STRING, "Need a string here");
	return import_C_string(parser.previous.start + 1, parser.previous.length - 2);
}

double parseDouble(const char *message) {
	consume(TOKEN_NUMBER, message);
	return strtod(parser.previous.start, NULL);
}

byte parseByte(char *message) { return (byte)parseDouble(message); }

Value parseConstant() {
	if (predictToken(TOKEN_NUMBER)) {
		return NUMBER_VAL(parseDouble("Need a number here"));
	}
	else if (predictToken(TOKEN_STRING)) {
		return GC_VAL(parseString());
	}
	else {
		errorAtCurrent("Expected a literal constant.");
		return NIL_VAL;
	}
}
