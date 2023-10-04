#include "common.h"

#define TABLE_MAX_LOAD 0.75

DEFINE_VECTOR_CODE(Table, Entry)

static Entry *findEntry(Entry *entries, size_t capacity, ObjString *key) {
	/*
	Implementation Notes:

	If probe sequence happens upon a tombstone before an unused bucket,
	then return that first tombstone thus to keep probe sequences short.

	Code currently represents virgin entries as those with key=NULL and value NIL.
	Tombstones are as key=NULL and value TRUE.

	What if found entries swapped places with a found tombstone?
	*/

	size_t index = key->hash % capacity;
	Entry *tombstone = NULL;

	for (;;) {
		Entry *entry = &entries[index];
		if (entry->key == NULL) {
			if (IS_NIL(entry->value)) {
				// Empty entry.
				return tombstone != NULL ? tombstone : entry;
			}
			else {
			 // We found a tombstone.
				if (tombstone == NULL) tombstone = entry;
			}
		}
		else if (entry->key == key) {
		 // We found the key.
			return entry;
		}

		index = (index + 1) % capacity;
	}
}

static void adjustCapacity(Table *table, size_t capacity) {
	Entry *entries = ALLOCATE(Entry, capacity);
	table->cnt = 0;
	for (size_t i = 0; i < capacity; i++) {
		entries[i].key = NULL;
		entries[i].value = NIL_VAL;
	}

	for (size_t i = 0; i < table->cap; i++) {
		Entry *entry = &table->at[i];
		if (entry->key == NULL) continue;

		Entry *dest = findEntry(entries, capacity, entry->key);
		dest->key = entry->key;
		dest->value = entry->value;
		table->cnt++;
	}

	FREE_ARRAY(Entry, table->at, table->cap);
	table->at = entries;
	table->cap = capacity;
}

bool tableGet(Table *table, ObjString *key, Value *value) {
	if (table->cnt == 0) return false;

	Entry *entry = findEntry(table->at, table->cap, key);
	if (entry->key == NULL) return false;

	*value = entry->value;
	return true;
}

bool tableSet(Table *table, ObjString *key, Value value) {
	// Returns true if the key is new, false if already present.

	if (table->cnt + 1 > table->cap * TABLE_MAX_LOAD) {
		adjustCapacity(table, GROW(table->cap));
	}

	Entry *entry = findEntry(table->at, table->cap, key);
	bool isNewKey = entry->key == NULL;
	if (isNewKey && IS_NIL(entry->value)) table->cnt++;

	entry->key = key;
	entry->value = value;
	return isNewKey;
}

void tableAddAll(Table *from, Table *to) {
	for (int i = 0; i < from->cap; i++) {
		Entry *entry = &from->at[i];
		if (entry->key != NULL) {
			tableSet(to, entry->key, entry->value);
		}
	}
}

Entry *tableFindString(Table *table, const char *chars, int length, uint32_t hash) {
	if (table->cnt == 0) return NULL;

	size_t index = hash % table->cap;
	for (;;) {
		Entry *entry = &table->at[index];
		if (entry->key == NULL) {
			// Stop if we find an empty non-tombstone entry.
			if (IS_NIL(entry->value)) return NULL;
		}
		else if (entry->key->length == length &&
			entry->key->hash == hash &&
			memcmp(entry->key->chars, chars, length) == 0) {
			// We found it.
			return entry;
		}

		index = (index + 1) % table->cap;
	}
}

bool tableDelete(Table *table, ObjString *key) {
	if (table->cnt == 0) return false;

	// Find the entry.
	Entry *entry = findEntry(table->at, table->cap, key);
	if (entry->key == NULL) return false;

	// Place a tombstone in the entry.
	entry->key = NULL;
	entry->value = BOOL_VAL(true);
	return true;
}
