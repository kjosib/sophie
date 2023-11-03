/*

Support for record-types.

*/

#include "common.h"


static void display_instance(Instance *instance) {
	printf("{%s:%d}", instance->constructor->name->text, instance->constructor->nr_fields);
}

static void display_instance_deeply(Instance *instance) {
	printf("{%s:", instance->constructor->name->text);
	int nr_fields = instance->constructor->nr_fields;
	push(GC_VAL(instance));
	for (int index = 0; index < nr_fields; index++) {
		printf(" ");
		instance = (Instance *)AS_PTR(TOP);
		printValueDeeply(instance->fields[index]);
	}
	pop();
	printf("}");
}

static void blacken_instance(Instance *instance) {
	darken_in_place(&instance->constructor);
	darkenValues(instance->fields, instance->constructor->nr_fields);
}

static size_t size_instance(Instance *instance) {
	return size_for_nr_fields(instance->constructor->nr_fields);
}

GC_Kind KIND_Instance = {
	.display = display_instance,
	.deeply = display_instance_deeply,
	.blacken = blacken_instance,
	.size = size_instance,
};


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


Constructor *new_constructor(int tag, int nr_fields) {
	Constructor *constructor = gc_allocate(&KIND_Constructor, sizeof(Constructor));
	constructor->name = AS_STRING(pop());
	constructor->tag = (byte)tag;
	constructor->nr_fields = (byte)nr_fields;
	initTable(&constructor->field_offset);
	while (nr_fields--) {
		tableSet(&constructor->field_offset, AS_STRING(pop()), ENUM_VAL(nr_fields));
	}
	return constructor;
}


