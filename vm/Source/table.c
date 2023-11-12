/*

DESIGN NOTE
------------

The hash table is principally a vector of Entry structures.
An entry consists of a String pointer and a Value.

Code currently represents virgin entries as those with key=NULL and value NIL.
Tombstones are as key=NULL and value TRUE.

*/

#include "common.h"

#define TABLE_MAX_LOAD 0.75

DEFINE_VECTOR_CODE(Table, Entry)

#define WRAP(index, capacity) ( (index) & ( (capacity) -1 ) )

static Entry *findEntry(Entry *entries, size_t capacity, String *key) {
	/*
	Implementation Notes:

	If probe sequence happens upon a tombstone before an unused bucket,
	then return that first tombstone thus to keep probe sequences short.

	What if found entries swapped places with a found tombstone?
	(Hypothesis: Churn on the data bus.)
	*/

	size_t index = WRAP(key->hash, capacity);
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

		index = WRAP(index + 1, capacity);
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

	FREE_ARRAY(Entry, table->at);
	table->at = entries;
	table->cap = capacity;
}

Value tableGet(Table *table, String *key) {
	if (table->cnt == 0) return NIL_VAL;
	Entry *entry = findEntry(table->at, table->cap, key);
	return (entry->key == NULL) ? NIL_VAL : entry->value;
}

bool tableSet(Table *table, String *key, Value value) {
	// Returns true if the key is new, false if already present.

#ifdef _DEBUG
	if (!is_string(key)) {
		printf("Got non-string key:");
		printObject((GC*)key);
		crashAndBurn("confused");
	}
#endif // _DEBUG


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

void table_set_from_C(Table *table, char *text, Value value) {
	if (text) {
		String *key = import_C_string(text, strlen(text));
		tableSet(table, key, value);
	}
}

void tableAddAll(Table *from, Table *to) {
	for (int i = 0; i < from->cap; i++) {
		Entry *entry = &from->at[i];
		if (entry->key != NULL) {
			tableSet(to, entry->key, entry->value);
		}
	}
}

Entry *tableFindString(Table *table, const char *chars, size_t length, uint32_t hash) {
	if (table->cnt == 0) return NULL;

	size_t index = WRAP(hash, table->cap);
	for (;;) {
		Entry *entry = &table->at[index];
		if (entry->key == NULL) {
			// Stop if we find an empty non-tombstone entry.
			if (IS_NIL(entry->value)) return NULL;
		}
		else if (entry->key->length == length &&
			entry->key->hash == hash &&
			memcmp(entry->key->text, chars, length) == 0) {
			// We found it.
			return entry;
		}

		index = WRAP(index + 1, table->cap);
	}
}

bool tableDelete(Table *table, String *key) {
	if (table->cnt == 0) return false;

	// Find the entry.
	Entry *entry = findEntry(table->at, table->cap, key);
	if (entry->key == NULL) return false;

	// Place a tombstone in the entry.
	entry->key = NULL;
	entry->value = BOOL_VAL(true);
	return true;
}

void darkenTable(Table *table) {
	for (size_t index = 0; index < table->cap; index++) {
		Entry *entry = &table->at[index];
		if (entry->key != NULL) {
			darken_in_place(&entry->key);
			darkenValue(&entry->value);
		}
	}
}

void tableDump(Table *table) {
	for (size_t index = 0; index < table->cap; index++) {
		Entry *entry = &table->at[index];
		if (entry->key != NULL) {
			printObject((GC*)entry->key);
			printf(" : ");
			printValue(entry->value);
			printf("\n");
		}
	}
}


void populate_field_offset_table(Table *table, int nr_fields) {
	initTable(table);
	while (nr_fields--) {
		tableSet(table, AS_STRING(pop()), ENUM_VAL(nr_fields));
	}
}


