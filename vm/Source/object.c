#include "common.h"


#define ALLOCATE_OBJ(type, objectType) (type*)allocateObject(sizeof(type), objectType)

static Obj *allocateObject(size_t size, ObjType type) {
	Obj *object = (Obj *)reallocate(NULL, 0, size);
	object->type = type;
	object->next = vm.objects;
	vm.objects = object;
	return object;
}

ObjClosure *newClosure(ObjFunction *function) {
	ObjClosure *closure = ALLOCATE_OBJ(ObjClosure, OBJ_CLOSURE);
	closure->function = function;
	initValueArray(&closure->captives);
	resizeValueArray(&closure->captives, function->captures.cnt);
	return closure;
}

ObjFunction *newFunction(FunctionType type, uint8_t arity, ObjString *name) {
	ObjFunction *function = ALLOCATE_OBJ(ObjFunction, OBJ_FUNCTION);
	function->arity = arity;
	function->nr_locals = 0;
	function->type = type;
	function->name = name;
	initChunk(&function->chunk);
	initValueArray(&function->children);
	initValueArray(&function->captures);
	return function;
}

ObjNative *newNative(uint8_t arity, NativeFn function) {
	ObjNative *native = ALLOCATE_OBJ(ObjNative, OBJ_NATIVE);
	native->arity = arity;
	native->function = function;
	return native;
}

static ObjString *allocateString(char *chars, size_t length, uint32_t hash) {
	ObjString *string = ALLOCATE_OBJ(ObjString, OBJ_STRING);
	string->length = length;
	string->chars = chars;
	string->hash = hash;
	tableSet(&vm.strings, string, NIL_VAL);
	return string;
}

uint32_t hashString(const char *key, size_t length) {
	uint32_t hash = 2166136261u;
	for (int i = 0; i < length; i++) {
		hash ^= (uint8_t)key[i];
		hash *= 16777619;
	}
	return hash;
}

ObjString *takeString(char *chars, size_t length) {
	uint32_t hash = hashString(chars, length);
	Entry *interned = tableFindString(&vm.strings, chars, length, hash);
	if (interned != NULL) {
		FREE_ARRAY(char, chars, length + 1);
		return interned->key;
	}

	return allocateString(chars, length, hash);
}

ObjString *copyString(const char *chars, size_t length) {
	uint32_t hash = hashString(chars, length);
	Entry *interned = tableFindString(&vm.strings, chars, length, hash);
	if (interned != NULL) return interned->key;

	char *heapChars = ALLOCATE(char, length + 1);
	memcpy(heapChars, chars, length);
	heapChars[length] = '\0';
	return allocateString(heapChars, length, hash);
}

static void printFunction(ObjFunction *function) {
	if (function->name == NULL) {
		printf("<script>");
	}
	else {
		printf("<fn %s>", function->name->chars);
	}
}

void printObject(Value value) {
	switch (OBJ_TYPE(value)) {
	case OBJ_CLOSURE:
		printFunction(AS_CLOSURE(value)->function);
	break;

	case OBJ_FUNCTION:
		printFunction(AS_FUNCTION(value));
		break;

	case OBJ_NATIVE:
		printf("<native fn>");
		break;

	case OBJ_STRING:
		printf("%s", AS_CSTRING(value));
		break;
	}
}