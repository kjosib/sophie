#include <stdarg.h>
#include <math.h>
#include "common.h"
#include "prep.h"
#include "chacha.h"

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
	vm_init(); // This first so that the string table is initialized first, before its first sweep.
	ffi_prepare_modules();
	init_actor_model();
	char *source = readFile(path);
	assemble(source);
	free(source);
	vm_run();
	vm_dispose();
}

int main(int argc, const char *argv[]) {
	if (argc == 2) {
		run_program(argv[1]);
		exit(0);
	}
	else {
		fprintf(stderr, "Usage: %s /path/to/intermediate/code\n", argv[0]);
		fprintf(stderr, "Sizes of some things in bytes, not counting payload:\n");
		fprintf(stderr, "Value: %d\n", (int)sizeof(Value));
		fprintf(stderr, "String: %d\n", (int)sizeof(String));
		fprintf(stderr, "Record: %d\n", (int)sizeof(Closure));
		fprintf(stderr, "Closure: %d\n", (int)sizeof(Closure));

		fprintf(stderr, "ChaCha20 Seed: %d\n", (int)sizeof(ChaCha_Seed));
		fprintf(stderr, "ChaCha20 Block: %d\n", (int)sizeof(ChaCha_Block));
		chacha_test_quarter_round();
		chacha_test_make_noise();
		fprintf(stderr, "Inf == Inf == %d\n", (HUGE_VAL == HUGE_VAL));
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

