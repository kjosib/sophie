/*

Support for record-types.

*/

#include "common.h"


static void display_record(Record *record) {
	printf("{%s:%d}", record->constructor->name->text, record->constructor->nr_fields);
}

static void display_record_deeply(Record *record) {
	printf("{%s:", record->constructor->name->text);
	int nr_fields = record->constructor->nr_fields;
	push(GC_VAL(record));
	for (int index = 0; index < nr_fields; index++) {
		printf(" ");
		record = (Record *)AS_PTR(TOP);
		printValueDeeply(record->fields[index]);
	}
	pop();
	printf("}");
}

static void blacken_record(Record *record) {
	darken_in_place(&record->constructor);
	darkenValues(record->fields, record->constructor->nr_fields);
}

static inline size_t size_for_nr_fields(int nr_fields) {
	return sizeof(Record) + sizeof(Value) * nr_fields;
}

static size_t size_record(Record *record) {
	return size_for_nr_fields(record->constructor->nr_fields);
}

GC_Kind KIND_Record = {
	.display = display_record,
	.deeply = display_record_deeply,
	.blacken = blacken_record,
	.size = size_record,
};

Record *construct_record() {
	assert(IS_CTOR(TOP));
	int nr_fields = AS_CTOR(TOP)->nr_fields;
	Record *record = gc_allocate(&KIND_Record, size_for_nr_fields(nr_fields));
	record->constructor = AS_CTOR(pop());
	memcpy(&record->fields, vm.stackTop - nr_fields, sizeof(Value) * nr_fields);
	return record;
}

void apply_constructor() {
	Record *record = construct_record();
	Value *slot = vm.stackTop - record->constructor->nr_fields;
	*slot = GC_VAL(record);
	vm.stackTop = slot + 1;
}

static void display_constructor(Constructor *constructor) {
	printf("(%s/%d)", constructor->name->text, constructor->nr_fields);
}

static void blacken_constructor(Constructor *constructor) {
	darken_in_place(&constructor->name);
	darkenTable(&constructor->field_offset);
}

static size_t size_constructor(Constructor *constructor) {
	return sizeof(Constructor);
}

GC_Kind KIND_Constructor = {
	.display = display_constructor,
	.deeply = display_constructor,
	.blacken = blacken_constructor,
	.size = size_constructor,
};


void make_constructor(int tag, int nr_fields) {
	Constructor *constructor = gc_allocate(&KIND_Constructor, sizeof(Constructor));
	constructor->name = AS_STRING(pop());
	constructor->tag = (byte)tag;
	constructor->nr_fields = (byte)nr_fields;
	populate_field_offset_table(&constructor->field_offset, nr_fields);
	push(CTOR_VAL(constructor));
}


