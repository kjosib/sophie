#include "common.h"

DEFINE_VECTOR_CODE(ValueArray, Value)
DEFINE_VECTOR_APPEND(ValueArray, Value)

void print_simply(Value value) {
switch (value.type) {
	case VAL_NUMBER: printf(NUMBER_FORMAT, AS_NUMBER(value)); break;
	case VAL_ENUM: printf("<enum: %d>", AS_ENUM(value)); break;
	case VAL_PTR: printf("<ptr: %p>", AS_PTR(value)); break;
	default:
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

char *valKind[] = {
	[VAL_NUMBER] = "number",
	[VAL_ENUM] = "enumerated constant",
	[VAL_PTR] = "opaque pointer",
	[VAL_GC] = "heap denizen",
	[VAL_THUNK] = "thunk",
	[VAL_CLOSURE] = "closure",
	[VAL_GLOBAL] = "global reference",
};
