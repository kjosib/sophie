#include "common.h"

static int value_array_counter;

void initValueArray(ValueArray *vec) {
	vec->cnt = vec->cap = 0; vec->at = ((void *)0);
	// vec->id = value_array_counter++;
	// printf("#");
}
void freeValueArray(ValueArray *vec) {
	free(vec->at);
	initValueArray(vec);
}

static void grow_value_array(ValueArray *vec) {
	// Postcondition: the ValueArray has a bigger buffer, with all its original data,
	// but more room to grow. If any of the values are from a younger generation,
	// the corresponding GC journal entries are adjusted point into the new buffer.
	Value *prior = vec->at;
	size_t new_capacity = max(4, 2 * vec->cap);
	Value *new_buffer = reallocate(prior, sizeof(Value) * new_capacity);
	gc_move_journal(prior, prior + vec->cap, new_buffer);
	vec->at = new_buffer;
	vec->cap = new_capacity;
}

size_t appendValueArray(ValueArray *vec) {  // ( value -- )
	if (vec->cap <= vec->cnt) grow_value_array(vec);
	gc_mutate(&vec->at[vec->cnt++], pop());
	return vec->cnt - 1;
}

void print_simply(Value value) {
	if (IS_NUMBER(value)) printf(NUMBER_FORMAT, AS_NUMBER(value));
	else if (IS_UNSET(value)) printf("unset");
	else if (IS_RUNE(value)) printf("<rune: %d>", AS_RUNE(value));
	else if (IS_ENUM(value)) {
		int vt_idx = AS_ENUM_VT_IDX(value);
		VTable *vt = &vmap.at[vt_idx];
		printf("<enum: %s/%d>", vt->type_name->text, AS_ENUM_TAG(value));
	}
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

void printObject(GC *item) {
	Method display = item->kind->display;
	if (display) display(item);
	else printf("<{%s}>", item->kind->name);
}
void printObjectDeeply(GC *item) { item->kind->deeply(item); }


void darkenValues(Value *at, size_t count) {
	for (size_t index = 0; index < count; index++) darkenValue(&at[index]);
}

void darkenValueArray(ValueArray *vec) {
	darkenValues(vec->at, vec->cnt);
}

char *valKind(Value value) {
	if (IS_NUMBER(value)) return "number";
	if (IS_UNSET(value)) return "the formless void";
	if (IS_RUNE(value)) return "rune";
	if (IS_ENUM(value)) return "enumerated constant";
	if (IS_PTR(value)) return "opaque pointer";
	if (IS_CLOSURE(value)) return "closure";
	if (IS_THUNK(value)) return "thunk";
	if (IS_GLOBAL(value)) return "global reference";
	if (IS_GC_ABLE(value)) return AS_GC(value)->kind->name;
	return "unrecognized value kind";
}

