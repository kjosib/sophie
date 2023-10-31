#include "common.h"

DEFINE_VECTOR_CODE(ValueArray, Value)
DEFINE_VECTOR_APPEND(ValueArray, Value)

void printValue(Value value) {
	switch (value.type) {
	case VAL_BOOL: printf(AS_BOOL(value) ? "true" : "false"); break;
	case VAL_NIL: printf("nil"); break;
	case VAL_NUMBER: printf("%g", AS_NUMBER(value)); break;
	case VAL_ENUM: printf("<enum: %d>", value.as.tag); break;
	case VAL_GC: printObject(value.as.gc); break;
	default: printf("<<%d>>", value.type);
	}
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
};
