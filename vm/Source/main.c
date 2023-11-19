#include <stdarg.h>
#include "common.h"
#include "prep.h"

#ifdef _WIN32
#pragma warning(disable : 4996)  /* Stop irrelevant warning about fopen on MS compilers */
#endif

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

static void run_program(const char *path) {
		init_gc();
		initVM(); // This first so that the string table is initialized first, before its first sweep.
		init_actor_model();
		install_native_functions();
		initLexicon();
		char *source = readFile(path);
		compile(source);
		free(source);
		// Maybe unload the compiler here and save a few bytes?
		vm_capture_preamble_specials();
		run(AS_CLOSURE(pop()));
		freeVM();
}

int main(int argc, const char *argv[]) {
	if (argc == 2) {
		run_program(argv[1]);
		exit(0);
	}
	else {
		printf("%.17g\n", 1e23);
		fprintf(stderr, "Usage: %s /path/to/intermediate/code\n", argv[0]);
		exit(64);
	}
}

__declspec(noreturn) void crashAndBurn(const char *format, ...) {
	va_list args;
	va_start(args, format);
	fputs("\n***\n ***\n  ***   ***   Giving up because ", stderr);
	vfprintf(stderr, format, args);
	va_end(args);
	fputs(".   ***\n", stderr);
	exit(74);
}

