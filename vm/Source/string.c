#include "common.h"
#define LOAD_FACTOR 0.75
#define INITIAL_CAPACITY 64
#define GROWTH_RATE 2

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

void string_table_init(StringTable *table, size_t capacity) {
	assert(capacity >= INITIAL_CAPACITY);
	*table = (StringTable){
		.capacity = capacity,
		.population = 0,
		.threshold = (size_t)(capacity * LOAD_FACTOR),
		.at = calloc(capacity, sizeof(Value)),
	};
	if (!table->at) crashAndBurn("No space for string internship table.");
}

void string_table_free(StringTable *table) {
	free(table->at);
	table->at = NULL;
}

static Value *probe_string_table(StringTable *table, const char *chars, size_t length, uint32_t hash) {
	size_t index = WRAP(hash, table->capacity);
	Value *tombstone = NULL;
	for (;;) {
		Value *entry = &table->at[index];
		if (entry->bits == 0) {
			return tombstone ? tombstone : entry;
		}
		else if (IS_UNSET(*entry)) {
			if (tombstone == NULL) tombstone = entry;
		} 
		else {
			String *key = AS_STRING(*entry);
			if (key->length == length && key->hash == hash && !memcmp(key->text, chars, length)) {
				// We found it.
				return entry;
			}
		}
		index = WRAP(index + 1, table->capacity);
	}
}

static void grow_string_table() {
	StringTable old = vm.strings;
	string_table_init(&vm.strings, GROWTH_RATE * old.capacity);
	for (size_t i = 0; i < old.capacity; i++) {
		if IS_GC_ABLE(old.at[i]) {
			String *string = AS_STRING(old.at[i]);
			Value *slot = probe_string_table(&vm.strings, string->text, string->length, string->hash);
			*slot = old.at[i];
			vm.strings.population++;
		}
	}
	string_table_free(&old);
}

static void install_string(Value *slot) {  // ( string -- string )
	if (slot->bits == 0) {
		*slot = TOP;
		vm.strings.population++;
		if (vm.strings.population > vm.strings.threshold) grow_string_table();
	}
	else {
		*slot = TOP;
	}
}

void intern_String() {  // ( string -- string )
	// The input string is not expected to have been hashed yet.
	String *string = AS_STRING(TOP);
	string->hash = hashString(string->text, string->length);
	Value *slot = probe_string_table(&vm.strings, string->text, string->length, string->hash);
	if (IS_GC_ABLE(*slot)) TOP = *slot;
	else install_string(slot);
}

void import_C_string(const char *text, size_t length) {  // ( -- string )
	uint32_t hash = hashString(text, length);
	Value *slot = probe_string_table(&vm.strings, text, length, hash);
	if (IS_GC_ABLE(*slot)) push(*slot);
	else {
		String *string = new_String(length);
		memcpy(string->text, text, length);
		string->hash = hash;
		push(GC_VAL(string));
		install_string(slot);
	}
}

void push_C_string(const char *text) {  // ( -- string )
	import_C_string(text, strlen(text));
}

bool is_string(void *item) {
	return ((GC*)item)->kind == &KIND_String;
}





