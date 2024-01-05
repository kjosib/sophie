#include "common.h"

DEFINE_VECTOR_CODE(ValueArray, Value)
DEFINE_VECTOR_APPEND(ValueArray, Value)

void print_simply(Value value) {
	if (IS_NUMBER(value)) printf(NUMBER_FORMAT, AS_NUMBER(value));
	else if (IS_NIL(value)) printf("nil");
	else if (IS_ENUM(value)) printf("<enum: %d>", AS_ENUM(value));
	else if (IS_PTR(value)) printf("<ptr: %p>", AS_PTR(value));
	else {
		assert(IS_GC_ABLE(value));
		printf("<<%s>>", AS_GC(value)->kind->name);
	}
}

void printValue(Value value) {
	if (IS_THUNK(value) && !DID_SNAP(value)) printf("*");
	if (IS_GC_ABLE(value)) printObject(AS_PTR(value));
	else print_simply(value);
}

void printValueDeeply(Value value) {
	value = force(value);
	if (IS_GC_ABLE(value)) printObjectDeeply(AS_PTR(value));
	else print_simply(value);
}

void darkenValues(Value *at, size_t count) {
	for (size_t index = 0; index < count; index++) darkenValue(&at[index]);
}

void darkenValueArray(ValueArray *vec) {
	darkenValues(vec->at, vec->cnt);
}

char *valKind(Value value) {
	if (IS_NUMBER(value)) return "number";
	if (IS_NIL(value)) return "the formless void";
	if (IS_ENUM(value)) return "enumerated constant";
	if (IS_PTR(value)) return "opaque pointer";
	if (IS_CLOSURE(value)) return "closure";
	if (IS_THUNK(value)) return "thunk";
	if (IS_GLOBAL(value)) return "global reference";
	if (IS_GC_ABLE(value)) return "heap denizen";
	return "something terribly wrong";
}

