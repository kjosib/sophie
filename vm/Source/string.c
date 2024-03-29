#include "common.h"

uint32_t hashString(const char *text, size_t length) {
	uint32_t hash = 2166136261u;
	for (int i = 0; i < length; i++) {
		hash ^= (byte)text[i];
		hash *= 16777619;
	}
	return hash;
}

static void blacken_string(String *string) {}

static size_t size_string(String *string) {
	return sizeof(*string) + string->length + 1;
}

static void display_string(String *string) {
	printf("%s", string->text);
}

static int type_index_string(String *string) {
	// See in assembler.c where it creates the built-in types.
	return TX_STRING;
}

GC_Kind KIND_String = {
	.display = display_string,
	.deeply = display_string,
	.blacken = blacken_string,
	.size = size_string,
	.type_index = type_index_string,
	.name = "String",
};


String *new_String(size_t length) {
	// Returns partially-initialized string object.
	// It will have length and null-terminator set properly.
	// This makes it safe for GC, but the VM must still
	// fill in the text and then intern the result.
	String *string = gc_allocate(&KIND_String, sizeof(String) + length + 1);
	string->length = length;
	string->text[length] = 0;
	return string;
}

String *intern_String(String *string) {
	// If the new string is known to the string table,
	// return the version from the string table.
	// (GC will reap the new duplicate.)
	// Otherwise, enter this new string into the string table,
	// and return the argument.
	// In this manner, string equality is pointer equality.

	// (A single global string table may prove a point of contention in thread-world.)

	// The input string is not expected to have been hashed yet.
	string->hash = hashString(string->text, string->length);
	Entry *interned = tableFindString(&vm.strings, string->text, string->length, string->hash);
	if (interned) return interned->key;
	else {
		tableSet(&vm.strings, string, UNSET_VAL);
		return string;
	}
}

String *import_C_string(const char *text, size_t length) {
	uint32_t hash = hashString(text, length);
	Entry *interned = tableFindString(&vm.strings, text, length, hash);
	if (interned) return interned->key;
	else {
		String *string = new_String(length);
		memcpy(string->text, text, length);
		string->hash = hash;
		tableSet(&vm.strings, string, UNSET_VAL);
		return string;
	}
}

void push_C_string(const char *text) {
	push(GC_VAL(import_C_string(text, strlen(text))));
}

bool is_string(void *item) {
	return ((GC*)item)->kind == &KIND_String;
}