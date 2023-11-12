#include <float.h>
#include "common.h"

DEFINE_VECTOR_CODE(ValueArray, Value)
DEFINE_VECTOR_APPEND(ValueArray, Value)

static void print_simply(Value value) {
switch (value.type) {
	case VAL_NIL: printf("nil"); break;
	case VAL_BOOL: printf(AS_BOOL(value) ? "true" : "false"); break;
	case VAL_NUMBER: printf("%.*g", DBL_DECIMAL_DIG, AS_NUMBER(value)); break;
	case VAL_ENUM: printf("<enum: %d>", AS_ENUM(value)); break;
	case VAL_PTR: printf("<ptr: %p>", AS_PTR(value)); break;
	default: printf("<<%d>>", value.type);
	}
}

void printValue(Value value) {
	if (IS_THUNK(value)) printf("*");
	if (IS_GC_ABLE(value)) printObject(AS_PTR(value));
	else print_simply(value);
}

void printValueDeeply(Value value) {
	value = force(value);
	if (IS_GC_ABLE(value)) printObjectDeeply(AS_PTR(value));
	else print_simply(value);
}

bool valuesEqual(Value a, Value b) {
	if (a.type != b.type) return false;
	switch (a.type) {
	case VAL_BOOL:   return AS_BOOL(a) == AS_BOOL(b);
	case VAL_NUMBER: return AS_NUMBER(a) == AS_NUMBER(b);
	case VAL_GC:    return AS_GC(a) == AS_GC(b);  // Pointer equality i.e. identity. This will change.
	default:         return false;
	}
}

void darkenValues(Value *at, size_t count) {
	for (size_t index = 0; index < count; index++) darkenValue(&at[index]);
}

void darkenValueArray(ValueArray *vec) {
	darkenValues(vec->at, vec->cnt);
}

char *valKind[] = {
	[VAL_NIL] = "nil",
	[VAL_BOOL] = "bool",
	[VAL_NUMBER] = "number",
	[VAL_ENUM] = "enum",
	[VAL_PTR] = "opaque pointer",
	[VAL_GC] = "heap denizen",
	[VAL_THUNK] = "thunk",
	[VAL_CLOSURE] = "closure",
	[VAL_NATIVE] = "native function",
	[VAL_CTOR] = "constructor",
};
