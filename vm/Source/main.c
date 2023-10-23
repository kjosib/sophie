#include "common.h"

static char *readFile(const char *path) {
	FILE *file = fopen(path, "rb");
	if (file == NULL) crashAndBurn("could not open input file");

	fseek(file, 0L, SEEK_END);
	size_t fileSize = ftell(file);
	rewind(file);

	char *buffer = (char *)malloc(fileSize + 1);
	if (buffer == NULL) crashAndBurn("not enough memory to read input file");

	size_t bytesRead = fread(buffer, sizeof(char), fileSize, file);
	if (bytesRead < fileSize) crashAndBurn("could not read input file");

	buffer[bytesRead] = '\0';

	fclose(file);
	return buffer;
}

static void runFile(const char *path) {
	char *source = readFile(path);
	InterpretResult result = interpret(source);
	free(source);

	if (result == INTERPRET_COMPILE_ERROR) exit(65);
	if (result == INTERPRET_RUNTIME_ERROR) exit(70);
}

int main(int argc, const char *argv[]) {
	init_gc();
	initVM(); // This first so that the string table is initialized first, before its first sweep.
	initLexicon();

	if (argc == 2) {
		runFile(argv[1]);
	}
	else {
		fprintf(stderr, "Usage: %s /path/to/intermediate/code\n", argv[0]);
		exit(64);
	}

	freeVM();
	return 0;
}

void crashAndBurn(char *why) {
	fprintf(stderr, "\n***\n ***\n  ***   ***   Giving up because %s.   ***", why);
	exit(74);
}

