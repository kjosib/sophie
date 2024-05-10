/*

DESIGN NOTE
------------

The hash table is principally a vector of Entry structures.

There will no no tombstones because the VM will not remove entries from tables.
These tables are to be constant data set up as part of loading the program.

*/

#include "common.h"

#define MIN_TABLE_SIZE 4

Table *new_table(size_t capacity) {
#ifdef _DEBUG
	size_t pwr = 1;
	while (pwr < capacity) pwr <<= 1;
	assert(pwr == capacity);
#endif // _DEBUG
	Table *table = gc_allocate(&KIND_Table, sizeof(Table) + (capacity * sizeof(Entry)));
	table->capacity = capacity;
	table->population = 0;
	memset(&table->at, 0, capacity * sizeof(Entry));
	return table;
}


static size_t findEntry(Table *table, String *key) {
	size_t capacity = table->capacity;
	size_t index = WRAP(key->hash, capacity);

	for (;;) {
		Entry *entry = &table->at[index];
		if (!(entry->key.bits)) {
			return index;
		}
		else if (AS_STRING(entry->key) == key) {
			return index;
		}

		index = WRAP(index + 1, capacity);
	}
}


static void rehash() {
	Table *new = new_table(max(MIN_TABLE_SIZE, 2 * AS_TABLE(TOP)->capacity));
	Table *old = AS_TABLE(TOP);
	Entry *src = &old->at[old->capacity];
	gc_forget_journal_portion(old->at, src);
	while (old->at < src) {
		src--;
		if (src->key.bits) {
			size_t index = findEntry(new, AS_STRING(src->key));
			new->at[index] = *src;
		}
	}
	new->population = old->population;
	TOP = GC_VAL(new);
}


Value tableGet(Value tableValue, String *key) {
	Table *table = AS_TABLE(tableValue);
	Entry *entry = &table->at[findEntry(table, key)];
#ifdef _DEBUG
	if (IS_UNSET(entry->key)) crashAndBurn("tableGet did not find key \"%s\"", key->text);
#endif // _DEBUG
	return entry->value;
}

void tableSet() {  // ( value key table -- table )
	assert(IS_GC_ABLE(TOP) && AS_GC(TOP)->kind == &KIND_Table);
	assert(IS_GC_ABLE(SND) && is_string(AS_GC(SND)));

	Table *table = AS_TABLE(TOP);
	table->population++;
	if (4 * (table->population) > (3 * table->capacity)) {
		rehash();
		table = AS_TABLE(TOP);
	}

	size_t index = findEntry(table, AS_STRING(SND));
	if (table->at[index].key.bits) crashAndBurn("Duplicate key \"%s\".", AS_STRING(SND)->text);

	gc_mutate(&table->at[index].key, SND);
	table = AS_TABLE(TOP);
	gc_mutate(&table->at[index].value, THD);
	THD = TOP;
	vm.stackTop -= 2;
}


Value table_get_from_C(const char *text) {  // ( Table -- Table )
	assert(text);
	push_C_string(text);
	Value answer = tableGet(SND, AS_STRING(TOP));
	pop();
	return answer;
}

void table_set_from_C(char *text, Value value) {  // ( table -- table )
	if (text) {
		push(value);
		push_C_string(text);
		push(THD);
		tableSet();
		SND = TOP;
		pop();
	}
}


static size_t table_size(Table *table) {
	return sizeof(Table) + (table->capacity * sizeof(Entry));
}

static void darkenTable(Table *table) {
	for (size_t index = 0; index < table->capacity; index++) {
		Entry *entry = &table->at[index];
		if (entry->key.bits) {
			darkenValue(&entry->key);
			darkenValue(&entry->value);
		}
	}
}

void tableDump(Table *table) {
	for (size_t index = 0; index < table->capacity; index++) {
		Entry *entry = &table->at[index];
		if (entry->key.bits) {
			printValue(entry->key);
			printf(" : ");
			printValue(entry->value);
			printf("\n");
		}
	}
}

GC_Kind KIND_Table = {
	.deeply = tableDump,
	.blacken = darkenTable,
	.size = table_size,
	.name = "Table",
};

void make_field_offset_table(int nr_fields) {  // ( Name ... -- Table )
	Value *base = vm.stackTop;
	size_t capacity = 4;
	while (capacity * 3 < nr_fields * 4) capacity <<= 1;
	push(GC_VAL(new_table(capacity)));
	while (nr_fields--) {
		push(RUNE_VAL(nr_fields));
		push(*(--base));
		push(THD);
		tableSet();
	}
	*base = TOP;
	vm.stackTop = &base[1];
}


