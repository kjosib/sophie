/*

Garbage Collected Memory Allocation for Sophie VM

For an explanation of what's going on here,
see https://sophie.readthedocs.io/en/latest/tech/gc.html

*/

#include "common.h"

#ifdef DEBUG_STRESS_GC
#define TOO_BIG 64
#define INITIAL_ARENA_SIZE (3*TOO_BIG)
#define GC_BALANCE 3

#else
#define TOO_BIG 512
#define INITIAL_ARENA_SIZE (32*TOO_BIG)
#define GC_BALANCE 7
#endif // DEBUG_STRESS_GC


typedef struct {
	byte *begin;
	byte *end;
} Arena;

typedef struct LOB LOB;

struct LOB {
    // Extra header for large objects. Tricolor invariant is explained above.
    LOB *next;  // Linked list of all objects
    LOB *mark;  // Linked list of marked objects.
};

typedef struct Tour Tour;
struct Tour {
    Tour *next;
    Verb verb;
};




static Arena to_space = { NULL, NULL };
static Arena from_space = { NULL, NULL };

static byte *next_ptr = NULL;

static LOB *all_lobs = NULL;
static LOB *grey_lobs = NULL;
static LOB sentinel = { NULL, NULL };

static Tour *root_sets = NULL;

static void collect_garbage();
static void free_white_lobs();



static LOB *lob_from_gc(GC *gc) { return ((LOB*)(gc)) - 1; }

static inline bool ptr_in_arena(void *ptr, Arena arena) {
    return arena.begin <= (byte*)ptr && (byte*)ptr < arena.end;
}

static size_t aligned(size_t size) {
	return (size + 7) & (~7);
}

static size_t allotment_for(size_t size) {
	return aligned(max(sizeof(GC), size));
}


static GC *small_alloc(size_t size) {
    size_t allotment = allotment_for(size);
    if (next_ptr + allotment >= to_space.end) collect_garbage();
    GC *gc = (GC*)next_ptr;
    next_ptr += allotment;
    assert(next_ptr <= to_space.end);
    return gc;
}

GC *large_alloc(size_t size) {
    LOB *lob = malloc(sizeof(LOB) + size);
    if (lob == NULL) crashAndBurn("Out of memory");
    else {
        lob->next = all_lobs;
        all_lobs = lob;
        lob->mark = NULL;
        return (GC *)(&lob[1]);
    }
}

void *gc_allocate(GC_Kind *kind, size_t size) {
#ifdef _DEBUG
    if (!size) crashAndBurn("Zero-sized heap-objects should be impossible.");
#endif // _DEBUG
    GC *gc = (size > TOO_BIG) ? large_alloc(size) : small_alloc(size);
    gc->kind = kind;
	return gc;
}

static void newArena(size_t size) {
	to_space.begin = next_ptr = malloc(size);
    if (to_space.begin == NULL) crashAndBurn("Out of memory");
    to_space.end = to_space.begin + size;
}

void init_gc() {
    newArena(INITIAL_ARENA_SIZE);
}

static size_t gc_size(GC *gc) { return allotment_for(gc->kind->size(gc)); }
static void break_heart(GC *gc) { gc->ptr = next_ptr; }
static bool is_broken_heart(GC *gc) { return ptr_in_arena(gc->ptr, to_space); }
static void *follow_heart(GC *gc) { return gc->ptr; }

static GC *evacuate(GC *gc) {
    size_t size = gc_size(gc);
    void *grey_copy = next_ptr;
    memcpy(grey_copy, gc, size);
    break_heart(gc);
    next_ptr += size;
    return grey_copy;
}

static void darken_lob(GC *gc) {
    LOB *lob = lob_from_gc(gc);
    if (!lob->mark) {
        lob->mark = grey_lobs;
        grey_lobs = lob;
    }
}

void *darken(void *gc) {
    if (gc == NULL) return NULL;
    if (ptr_in_arena(gc, to_space)) return gc;
    else if (ptr_in_arena(gc, from_space)) {
        if (is_broken_heart(gc)) return follow_heart(gc);
        else return evacuate(gc);
    }
    else {
        darken_lob(gc);
        return gc;
    }
}

static void grey_the_roots() {
    Tour *tour = root_sets;
    while (tour) {
        tour->verb();
        tour = tour->next;
    }
}

void gc_install_roots(Verb verb) {
    Tour *tour = malloc(sizeof(Tour));
    if (tour == NULL) crashAndBurn("null tour");
    else {
        *tour = (Tour){ .next = root_sets, .verb = verb };
        root_sets = tour;
    }
}

static void blacken(GC *gc) { gc->kind->blacken(gc); }

static bool is_white(GC *gc) {
    // NB: For the sake of simplicity, null pointers are off limits here.
    // Also for simplicity, this considers broken-hearts as not reached.
    // (They're handled in a separate part anyway.)
    if (ptr_in_arena(gc, to_space)) return false;
    if (ptr_in_arena(gc, from_space)) return true;
    // Otherwise it must be a LOB:
    return !(lob_from_gc(gc)->mark);
}

static void sweep_weak_table(Table *table) {
    // Right now this means clean out unmarked strings from the string pool.
    for (size_t index = 0; index < table->cap; index++) {
        String *key = table->at[index].key;
        if (key == NULL) continue;
        if (ptr_in_arena(key, from_space)) {
            if (is_broken_heart((GC*)key)) {
                table->at[index].key = follow_heart((GC*)key);
            }
            else {
                tableDelete(table, key);
            }
        }
        else if (!lob_from_gc(&key->header)->mark) {
            tableDelete(table, key);
        }
    }
}

static void collect_garbage() {
#ifdef DEBUG_ANNOUNCE_GC
    printf("\nCollecting! ");
#endif
    size_t old_capacity = to_space.end - to_space.begin;
    size_t new_capacity = old_capacity * 2;
    from_space = to_space;
    newArena(new_capacity);
    grey_lobs = &sentinel;
    byte *grey_ptr = to_space.begin;
    grey_the_roots();
    for (;;) {
        while (grey_ptr < next_ptr) {
            blacken((GC *)grey_ptr);
            grey_ptr += gc_size((GC *)grey_ptr);
        }
        if (grey_lobs == &sentinel) break;
        else {
            LOB *lob = grey_lobs;
            grey_lobs = lob->mark;
            blacken((GC*)(lob + 1));
        }
    }
    size_t used = next_ptr - to_space.begin;
#ifdef DEBUG_ANNOUNCE_GC
    printf("Scavenged %d of %d bytes.\n", (int)(old_capacity - used), (int)(old_capacity));
#endif
#ifdef DEBUG_STRESS_GC
    size_t max_capacity = used + TOO_BIG;  // Trigger very frequent collections
#else
    size_t max_capacity = max( GC_BALANCE * used, INITIAL_ARENA_SIZE );
#endif // DEBUG_STRESS_GC
    if (new_capacity > max_capacity) {
        to_space.end = to_space.begin + max_capacity;
    }
    sweep_weak_table(&vm.strings);
    free(from_space.begin);
    free_white_lobs();
}

static void free_white_lobs() {
    LOB **prior = &all_lobs;
    LOB *lob = all_lobs;
    while (lob != NULL) {
        LOB *next = lob->next;
        if (lob->mark) {
            lob->mark = NULL;
            prior = &lob->next;
        }
        else {
            *prior = lob->next;
            free(lob);
        }
        lob = next;
    }
}

