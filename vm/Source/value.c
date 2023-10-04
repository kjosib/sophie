#include "common.h"

DEFINE_VECTOR_CODE(ValueArray, Value)
DEFINE_VECTOR_APPEND(ValueArray, Value)

void printValue(Value value) {
	switch (value.type) {
	case VAL_BOOL: printf(AS_BOOL(value) ? "true" : "false"); break;
	case VAL_NIL: printf("nil"); break;
	case VAL_NUMBER: printf("%g", AS_NUMBER(value)); break;
	case VAL_OBJ: printObject(value); break;
	default: printf("<<%d>>", value.type);
	}
}

bool valuesEqual(Value a, Value b) {
	if (a.type != b.type) return false;
	switch (a.type) {
	case VAL_BOOL:   return AS_BOOL(a) == AS_BOOL(b);
	case VAL_NUMBER: return AS_NUMBER(a) == AS_NUMBER(b);
	case VAL_OBJ:    return AS_OBJ(a) == AS_OBJ(b);  // Pointer equality i.e. identity. This will change.
	default:         return false;
	}
}
