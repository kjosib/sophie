/*

Support for record-types.

*/

#include "common.h"


static inline size_t enough_space(int nr_fields) {
	return sizeof(Instance) + sizeof(Value) * nr_fields;
}


static void display_instance(Instance *instance) {
	printf("{%s:\n", instance->constructor->name->text);
	for (int index = 0; index < instance->constructor->nr_fields; index++) {
		printf("\t");
		printValue(instance->fields[index]);
		printf("\n");
	}
	printf("}\n");
}

static void blacken_instance(Instance *instance) {
	darken_in_place(&instance->constructor);
	darkenValues(instance->fields, instance->constructor->nr_fields);
}

static size_t size_instance(Instance *instance) {
	return enough_space(instance->constructor->nr_fields);
}

GC_Kind KIND_Instance = {
	.call = bad_callee,
	.exec = bad_callee,
	.display = display_instance,
	.blacken = blacken_instance,
	.size = size_instance,
};

static Instance *construct() {
	int nr_fields = ((Constructor *)(TOP.as.ptr))->nr_fields;
	Instance *instance = gc_allocate(&KIND_Instance, enough_space(nr_fields));
	instance->constructor = pop().as.ptr;
	memcpy(&instance->fields, vm.stackTop - nr_fields, sizeof(Value) * nr_fields);
	return instance;
}

static void call_ctor() {
	Instance *instance = construct();
	Value *slot = vm.stackTop - instance->constructor->nr_fields;
	*slot = GC_VAL(instance);
	vm.stackTop = slot + 1;
}

static void exec_ctor() {
	*vm.frame->base = GC_VAL(construct());
	vm.stackTop = vm.frame->base + 1;
	vm.frame--;
}

static void display_ctor(Constructor *constructor) {
	printf("(%s/%d)", constructor->name->text, constructor->nr_fields);
}

static void blacken_ctor(Constructor *constructor) {
	darken_in_place(&constructor->name);
	darkenTable(&constructor->field_offset);
}

static size_t size_ctor(Constructor *constructor) {
	return sizeof(Constructor);
}

GC_Kind KIND_Constructor = {
	.call = call_ctor,
	.exec = exec_ctor,
	.display = display_ctor,
	.blacken = blacken_ctor,
	.size = size_ctor,
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


