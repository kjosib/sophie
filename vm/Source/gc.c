/*

Garbage Collected Memory Allocation for Sophie VM

For an explanation of what's going on here,
see https://sophie.readthedocs.io/en/latest/tech/gc.html

*/

#include "common.h"

#define NURSERY_DIVISOR 2

#ifdef DEBUG_STRESS_GC
#define LOB_THRESHOLD 128
#define SMALLEST_NURSERY 256
#define INITIAL_ARENA_SIZE (3*SMALLEST_NURSERY)
#define GC_BALANCE 2
#define JOURNAL_SIZE 100

#else
#define LOB_THRESHOLD 512
#define SMALLEST_NURSERY 8192
#define INITIAL_ARENA_SIZE (8*SMALLEST_NURSERY)
#define GC_BALANCE 7
#define JOURNAL_SIZE 1024
#endif // DEBUG_STRESS_GC

static_assert(SMALLEST_NURSERY > LOB_THRESHOLD, "That gap will be a problem.");

char *sigil = "HEAP ITEM";

typedef struct LOB LOB;

struct LOB {
	// Extra header for large objects. Tricolor invariant is explained above.
	LOB *next;  // Linked list of all objects
	LOB *mark;  // Linked list of marked objects.
	unsigned int generation;  // zero for nursery, one for young survivors, etc.
};
static LOB *grey_lobs = NULL;
static LOB sentinel = { NULL, NULL };
static LOB *lob_from_gc(GC *gc) { return ((LOB*)(gc)) - 1; }


typedef struct RootsNode RootsNode;
struct RootsNode {
	RootsNode *next;
	Verb verb;
};
static RootsNode *root_sets = NULL;


typedef struct {
	byte *begin;
	byte *next;
	byte *end;
	LOB *lobs;
	unsigned int generation;  // zero for nursery, one for young survivors, etc.
} Arena;

static inline bool ptr_in_arena(void *ptr, Arena *arena) {
	// As things stand, this is overcautious around LOBs.
	// Ideally there would be some sort of index from memory page to generation.
	// That's unlikely to be a problem in practice for some time, though.
	return arena->begin <= (byte*)ptr && (byte*)ptr < arena->next;
}



static Arena nursery, to_space, from_space;



static void free_white_lobs();



static Value *journal[JOURNAL_SIZE];
static size_t journal_population;

void gc_mutate(Value *dst, Value value) {
	*dst = value;
	if (IS_GC_ABLE(value) && !ptr_in_arena(dst, &nursery)) {
		journal[journal_population++] = dst;
		if (journal_population >= JOURNAL_SIZE) collect_garbage();
	}
}

static void clear_the_journal() {
	journal_population = 0;
}

static void grey_the_journal() {
	for (size_t i = 0; i < journal_population; i++) {
		darkenValue(journal[i]);
	}
	clear_the_journal();
}

void gc_move_journal(Value *start, Value *stop, Value *new_start) {
	ptrdiff_t offset = new_start - start;
	for (size_t i = 0; i < journal_population; i++) {
		if (start <= journal[i] && journal[i] < stop) {
			journal[i] += offset;
		}
	}
}

void gc_forget_journal_portion(void *start, void *stop) {
	// This helps when tables resize themselves.
	// This assumes that a given table is only referenced at most once, which is true as of 8 May 2024.

	size_t i = 0;
	while (i < journal_population) {
		if (start <= (void *)journal[i] && (void *)journal[i] < stop) {
			journal[i] = journal[--journal_population];
		} else {
			i++;
		}
	}
}


static size_t aligned(size_t size) {
	return (size + 7) & (~7);
}

static size_t allotment_for(size_t size) {
	return aligned(max(sizeof(GC), size));
}


static GC *small_alloc(size_t size) {
	size_t allotment = allotment_for(size);
	assert(allotment < SMALLEST_NURSERY);
	if (nursery.next + allotment >= nursery.end) collect_garbage();
	GC *gc = (GC*)nursery.next;
	nursery.next += allotment;
	assert(nursery.next <= nursery.end);
	return gc;
}

GC *large_alloc(size_t size) {
	LOB *lob = malloc(sizeof(LOB) + size);
	if (lob == NULL) crashAndBurn("Out of memory");
	else {
		lob->next = nursery.lobs;
		nursery.lobs = lob;
		lob->mark = NULL;
		lob->generation = 0;
		return (GC *)(&lob[1]);
	}
}


void *gc_allocate(GC_Kind *kind, size_t size) {
#ifdef _DEBUG
	if (!size) crashAndBurn("Zero-sized heap-objects should be impossible.");
#endif // _DEBUG
	GC *gc = (size >= LOB_THRESHOLD) ? large_alloc(size) : small_alloc(size);
	gc->kind = kind;
	return gc;
}

static void new_arena(size_t size) {
	byte *space = malloc(size);
	if (space == NULL) crashAndBurn("Out of memory");
	else {
		to_space = (Arena) {
			.begin = space,
			.next = space,
			.end = space + size,
			.lobs = NULL,
			.generation = 1,
		};
	}
}

static void place_nursery() {
	size_t available = (to_space.end - to_space.next);
	size_t portion = (available / NURSERY_DIVISOR) & ~7;
	size_t nursery_size = max(portion, SMALLEST_NURSERY);
	nursery = (Arena){
		.begin = to_space.end - nursery_size,
		.next = to_space.end - nursery_size,
		.end = to_space.end,
		.lobs = NULL,
		.generation = 0,
	};
}

void init_gc() {
#if USE_FINALIZERS
	initResourceArray(&resources);
#endif
	new_arena(INITIAL_ARENA_SIZE);
	place_nursery();
	clear_the_journal();
}

static size_t gc_size(GC *gc) { return allotment_for(gc->kind->size(gc)); }
static void break_heart(GC *gc) { gc->ptr = to_space.next; }
static bool is_broken_heart(GC *gc) { return ptr_in_arena(gc->ptr, &to_space); }
static GC *follow_heart(GC *gc) { return gc->ptr; }

static GC *evacuate(GC *gc) {
	size_t size = gc_size(gc);
	void *grey_copy = to_space.next;
	memcpy(grey_copy, gc, size);
	break_heart(gc);
	to_space.next += size;
	return grey_copy;
}

static inline bool is_lob_white(LOB *lob) { return (!lob->mark) && (lob->generation <= from_space.generation); }

static void darken_lob(GC *gc) {
	LOB *lob = lob_from_gc(gc);
	if (is_lob_white(lob)) {
		lob->mark = grey_lobs;
		grey_lobs = lob;
	}
}

GC *darken(GC *gc) {
	if (ptr_in_arena(gc, &from_space)) {
		if (is_broken_heart(gc)) {
			return follow_heart(gc);
		}
		else {
			return evacuate(gc);
		}
	}
	else if (ptr_in_arena(gc, &to_space)) return gc;
	else {
		darken_lob(gc);
		return gc;
	}
}

static void grey_the_roots() {
	RootsNode *tour = root_sets;
	while (tour) {
		tour->verb();
		tour = tour->next;
	}
}

void gc_install_roots(Verb verb) {
	RootsNode *tour = malloc(sizeof(RootsNode));
	if (tour == NULL) crashAndBurn("null tour");
	else {
		*tour = (RootsNode){ .next = root_sets, .verb = verb };
		root_sets = tour;
	}
}

void gc_forget_roots(Verb verb) {
	// Deletion in-place from a linked list.
	RootsNode **cursor = &root_sets;
	while (*cursor) {
		if ((*cursor)->verb == verb) {
			RootsNode *victim = *cursor;
			*cursor = (*cursor)->next;
			free(victim);
		}
		else cursor = &((*cursor)->next);
	}
}

static void blacken(GC *gc) { gc->kind->blacken(gc); }

static void sweep_weak_table(StringTable *table) {
	// Right now this means clean out unmarked strings from the string pool.
	// Incidentally, a weakness in the current design is that the string table never shrinks.
	// A program could have a phase that generates a lot of temporary strings,
	// and then another phase that doesn't need them anymore. It must still scan the whole array.
	// It might be nice to have a separate string table for each generation.
	// This might slow down interning strings. Another option is to card-mark the table.
	// This would mean not scanning so hard when there's relatively little string activity.
	// These cards would indicate the youngest generation of any string in a segment.
	// That only makes sense once generations happen, though.
	// At present, every generation is the youngest.
	for (size_t index = 0; index < table->capacity; index++) {
		if (IS_GC_ABLE(table->at[index])) {
			GC *gc = AS_GC(table->at[index]);
			if (ptr_in_arena(gc, &from_space)) {
				if (is_broken_heart(gc)) {
					table->at[index] = GC_VAL(follow_heart(gc));
				}
				else {
					table->at[index] = UNSET_VAL;
				}
			}
			else if (ptr_in_arena(gc, &to_space)) {}
			else if (is_lob_white(lob_from_gc(gc))) {
				table->at[index] = UNSET_VAL;
			}
		}
	}
}

#if USE_FINALIZERS
DEFINE_VECTOR_TYPE(ResourceArray, GC *)
DEFINE_VECTOR_CODE(ResourceArray, GC *)
DEFINE_VECTOR_APPEND(ResourceArray, GC *)

static ResourceArray resources;

void gc_please_finalize(GC *item) {
	assert(item->kind->finalize != NULL);
	appendResourceArray(&resources, item);
}

static void sweep_finalizers() {
	/*
	Finalizers written in Sophie would presumably be like last-messages-to-actors.
	The GC finalizer for an actor would thus darken said actor and add it to some queue.
	Then another round of blackening takes place.
	Actors that finish their "finalize" message then presumably go into a dead state,
	no longer able to receive messages. And as such, the GC can re-route zombie references
	to a special system-actor designed to ignore dead letters -- or to log them, in debug mode.
	*/
	size_t keep = 0;
	for (size_t index = 0; index < resources.cnt; index++) {
		GC *item = resources.at[index];
		if (ptr_in_arena(item, &to_space)) resources.at[keep++] = item;
		else if (ptr_in_arena(item, &from_space)) {
			if (is_broken_heart(item)) resources.at[keep++] = follow_heart(item);
			else item->kind->finalize(item);
		}
		else if (is_lob_white(lob_from_gc(item))) item->kind->finalize(item);
		else resources.at[keep++] = item;
	}
	resources.cnt = keep;
}
#endif

/* The heart of copying collection relies on to_space and from_space to be set properly in advance. */
static void cheney_scan() {
	grey_lobs = &sentinel;
	byte *grey_ptr = to_space.next;
	grey_the_journal();
	grey_the_roots();
	for (;;) {
		while (grey_ptr < to_space.next) {
			blacken((GC *)grey_ptr);
			grey_ptr += gc_size((GC *)grey_ptr);
		}
		assert(grey_ptr == to_space.next);
		if (grey_lobs == &sentinel) break;
		else {
			LOB *lob = grey_lobs;
			grey_lobs = lob->mark;
			blacken((GC*)(lob + 1));
		}
	}
#if USE_FINALIZERS
	sweep_finalizers();
#endif
	sweep_weak_table(&vm.strings);
	free_white_lobs(&from_space.lobs);
}

static bool can_perform_minor_collection() {
	size_t nursery_used = nursery.next - nursery.begin;
	byte *worst_case_scenario = to_space.next + nursery_used;
	return worst_case_scenario <= nursery.begin;
}

void collect_garbage() {
	grey_lobs = &sentinel;
	if (can_perform_minor_collection()) {
#ifdef DEBUG_ANNOUNCE_GC_MINOR
		printf("\nMinor Collection: ");
		byte *prior = to_space.next;
#endif // DEBUG_ANNOUNCE_GC_MINOR
		from_space = nursery;
		cheney_scan();
#ifdef DEBUG_ANNOUNCE_GC_MINOR
		printf("%d bytes promoted out of %d.\n", (int)(to_space.next - prior), (int)(from_space.next - from_space.begin));
#endif // DEBUG_ANNOUNCE_GC_MINOR
	}
	else {
#ifdef DEBUG_ANNOUNCE_GC_MAJOR
		printf("\nMajor Collection: ");
#endif // DEBUG_ANNOUNCE_GC_MAJOR
		clear_the_journal();
		from_space = to_space;
		from_space.next = from_space.end; // ptr_in_arena should thus consider the nursery as part of from_space.
		assert(from_space.end == nursery.end);
		size_t old_capacity = from_space.end - from_space.begin;
		size_t new_capacity = old_capacity * 2;
		new_arena(new_capacity);
		cheney_scan();
		free_white_lobs(&nursery.lobs); // Because the nursery is semantically part of from_space, but has its own separate list of LOBs.
		size_t used = to_space.next - to_space.begin;
		free(from_space.begin);
#ifdef DEBUG_STRESS_GC
		size_t max_capacity = max(GC_BALANCE * used + LOB_THRESHOLD, INITIAL_ARENA_SIZE);  // Trigger very frequent collections
#else
		size_t max_capacity = max(GC_BALANCE * used, INITIAL_ARENA_SIZE);
#endif // DEBUG_STRESS_GC
#ifdef DEBUG_ANNOUNCE_GC_MAJOR
		printf("Scavenged %d of %d into %d bytes; %d used.\n", (int)(old_capacity - used), (int)old_capacity, (int)new_capacity, (int)used);
#endif // DEBUG_ANNOUNCE_GC_MAJOR
		if (new_capacity > max_capacity) {
			to_space.end = to_space.begin + max_capacity;
		}
	}
	place_nursery();
}


static void free_white_lobs(LOB **from_lobs) {
	LOB **prior = from_lobs;
	LOB *lob = *prior;
	while (lob != NULL) {
		LOB *next = lob->next;
		if (lob->mark) {
			lob->mark = NULL;
			lob->generation = to_space.generation;
			prior = &lob->next;
		}
		else {
			*prior = lob->next;
			free(lob);
		}
		lob = next;
	}
	// Now preppend the surviving LOBs to the next-older generation's LOB list.
	*prior = to_space.lobs;
	to_space.lobs = *from_lobs;
}

void darkenValue(Value *value) {
	if (IS_THUNK(*value) && DID_SNAP(*value)) {
		*value = SNAP_RESULT(AS_CLOSURE(*value));
	}
	if (IS_GC_ABLE(*value)) {
		GC *grey = AS_GC(*value);
		GC *black = darken(grey);
		value->bits = INDICATOR(*value) | (uint64_t)black;
	}
}


