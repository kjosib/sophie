/*
The plan here is to do something for double dispatch.
Reasonable plans are plentiful.
For now I'm doing something fairly simple:
Each user-mode type has a dispatch table, which 
*/

#include "common.h"

static void darken_DispatchEntry(DispatchEntry *de) {
	darkenValue(&(de->callable));
}

DEFINE_VECTOR_CODE(DispatchTable, DispatchEntry)
DEFINE_VECTOR_APPEND(DispatchTable, DispatchEntry)

// The concept is LRU: Whenever there's a search in a dispatch table, move the found-entry to the front.
// Nine times in ten, this should make the search tolerably fast.

Value find_dispatch(DispatchTable *dt, int type_index) {
	if (dt->at[0].type_index == type_index) {
		return dt->at[0].callable;
	}

	for (size_t i = 1; i < dt->cnt; i++) {
		if (dt->at[i].type_index == type_index) {
			Value callable = dt->at[i].callable;
			// Suppose we find the goal at offset two:
			// Then there are two entries (at offsets zero and one) to move.
			memmove(&dt->at[1], &dt->at[0], i * sizeof(DispatchEntry));
			dt->at[0] = (DispatchEntry){.callable=callable, .type_index = type_index};
			return callable;
		}
	}

	crashAndBurn("Failed to resolve a dispatch.");
}

// This means (for now) that dispatch entries are consecutive in the table,
// so darkening them is a straightforward array operation:
static void darken_DispatchTable(DispatchTable *dt) {
	for (size_t i = 0; i < dt->cnt; i++) darken_DispatchEntry(&(dt->at[i]));
}

// How to init a vtable, then:

void init_VTable(VTable *vt, String *type_name) {
	vt->type_name = type_name;
	vt->neg = UNSET_VAL;
	initDispatchTable(&vt->cmp);
	initDispatchTable(&vt->add);
	initDispatchTable(&vt->sub);
	initDispatchTable(&vt->mul);
	initDispatchTable(&vt->div);
	initDispatchTable(&vt->pow);
}

// Run-time needs a vector of VTables.

DEFINE_VECTOR_CODE(VMap, VTable)
DEFINE_VECTOR_ALLOC(VMap, VTable)

static void darken_VTable(VTable *vt) {
	darken_in_place(&vt->type_name);
	darkenValue(&vt->neg);
	darken_DispatchTable(&vt->cmp);
	darken_DispatchTable(&vt->add);
	darken_DispatchTable(&vt->sub);
	darken_DispatchTable(&vt->mul);
	darken_DispatchTable(&vt->div);
	darken_DispatchTable(&vt->pow);
}

static void dispose_VTable(VTable *vt) {
	freeDispatchTable(&vt->cmp);
	freeDispatchTable(&vt->add);
	freeDispatchTable(&vt->sub);
	freeDispatchTable(&vt->mul);
	freeDispatchTable(&vt->div);
	freeDispatchTable(&vt->pow);
}

// In concept, each new type gets a vtable entry.

VMap vmap;

static void grey_the_vmap() {
	for (size_t i = 0; i < vmap.cnt; i++) darken_VTable(&vmap.at[i]);
}

void init_dispatch() {
	initVMap(&vmap);
	gc_install_roots(grey_the_vmap);
}

void dispose_dispatch() {
	gc_forget_roots(grey_the_vmap);
	for (size_t i = 0; i < vmap.cnt; i++) dispose_VTable(&vmap.at[i]);
}
