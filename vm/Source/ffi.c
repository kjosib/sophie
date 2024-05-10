#include "common.h"

void ffi_prepare_modules() {
	// Prepare on-demand init and linkage with things considered as "FFI" in Sophie code.
	// There's nothing to do here right now.
}


NativeFn ffi_find_module(char *key) {
	if (!strcmp(key, "sophie.adapters.game_adapter")) return game_sophie_init;

	return NULL;
}

