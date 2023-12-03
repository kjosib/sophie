#include "common.h"

static Table ffi_modules;

void ffi_prepare_modules() {
	// Prepare on-demand init and linkage with things considered as "FFI" in Sophie code.
	initTable(&ffi_modules);

	table_set_from_C(&ffi_modules, "sophie.adapters.game_adapter", PTR_VAL(&game_sophie_init));
}


NativeFn ffi_find_module(String *key) {
	return AS_PTR(tableGet(&ffi_modules, key));
}

