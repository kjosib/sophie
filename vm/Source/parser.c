#include "common.h"
#include "prep.h"

Parser parser;

static void errorAt(Token *token, const char *message) {
	fprintf(stderr, "[line %d] Error", token->line);

	if (token->type == TOKEN_EOF) {
		fprintf(stderr, " at end");
	}
	//else if (token->type == TOKEN_ERROR) {
	//	// Nothing.
	//}
	else {
		fprintf(stderr, " at '%.*s'", (int)(min(60, token->length)), token->start);
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

		errorAtCurrent("Unrecognized Token.");
	}
}

void consume(TokenType type, const char *message) {
	if (parser.current.type == type) advance();
	else errorAtCurrent(message);
}

bool maybe_token(TokenType type) {
	if (predictToken(type)) {
		advance();
		return true;
	} else {
		return false;
	}
}

void parseString() {  // ( -- string )
	consume(TOKEN_STRING, "Need a string here");
	import_C_string(parser.previous.start + 1, parser.previous.length - 2);
}

void parseName() {  // ( -- string )
	consume(TOKEN_NAME, "Need a string here");
	import_C_string(parser.previous.start, parser.previous.length);
}


double parseDouble(const char *message) {
	consume(TOKEN_NUMBER, message);
	return strtod(parser.previous.start, NULL);
}

byte parseByte(char *message) { return (byte)parseDouble(message); }

void parseConstant() {  // ( -- value )
	if (predictToken(TOKEN_NUMBER)) {
		push(NUMBER_VAL(parseDouble("Need a number here")));
	}
	else if (predictToken(TOKEN_STRING)) {
		parseString();
	}
	else {
		errorAtCurrent("Expected a literal constant.");
		push(UNSET_VAL);
	}
}
