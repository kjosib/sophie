#include "common.h"

typedef struct {
	Message **buffer;
	size_t capacity, front, gap;
} CircularBuffer;

/*
The invariant around a circular buffer is:

.front is the index of the element at the head of the queue, if there is one.
.gap is the index of the next slot to insert into.

Neither may equal the capacity.

If these two are equal, the queue is empty.
So, if inserting an element *would* make the two equal, it's time for a larger buffer.

This means there's always a gap of at least one, which means we can't have a zero-capacity queue.

*/

#define INITIAL_CAPACITY 64

static CircularBuffer mq;

static grey_the_message_queue() {
	// There are three cases: Empty, contiguous, and gapped.
	if (mq.gap < mq.front) {
		// Gapped case:
		for (size_t i = 0; i < mq.gap; i++) darken_in_place(&mq.buffer[i]);
		for (size_t i = mq.front; i < mq.capacity; i++) darken_in_place(&mq.buffer[i]);
	}
	else {
		// Contiguous case:
		for (size_t i = mq.front; i < mq.gap; i++) darken_in_place(&mq.buffer[i]);
		// That also works for the Empty case,
		// because the for-loop has zero iterations.

		// It would not work if a queue reallocation had triggered a collection,
		// but I don't think the queue should be in collectable memory anyway.
	}
}

static size_t room_for(size_t nr_message_pointers) { return nr_message_pointers * sizeof(Message *); }

void init_actor_model() {
	mq.buffer = malloc(room_for(INITIAL_CAPACITY));
	if (mq.buffer == NULL) crashAndBurn("could not allocate initial message queue");
	mq.capacity = INITIAL_CAPACITY;
	mq.front = mq.gap = 0;
	gc_install_roots(grey_the_message_queue);
}

static void grow_the_queue() {
	assert(mq.gap == mq.front);
	size_t nr_shifting = mq.capacity - mq.front;
	mq.front += mq.capacity;
	mq.capacity = 2 * mq.capacity;
	Message **new_buffer = realloc(mq.buffer, room_for(mq.capacity));
	if (new_buffer == NULL) crashAndBurn("could not grow message queue");
	mq.buffer = new_buffer;  // Looks redundant. Stops compiler warning.
	memmove(&mq.buffer[mq.front], &mq.buffer[mq.gap], room_for(nr_shifting));
}

static size_t ahead(size_t index) {
	// Works because capacity is a power of two;
	// Nice because code is small and non-branching.
	return (index + 1) & (mq.capacity - 1);
}

void enqueue_message_from_top_of_stack() {
	mq.buffer[mq.gap] = AS_MESSAGE(pop());
	mq.gap = ahead(mq.gap);
	if (mq.gap == mq.front) grow_the_queue();
}

Message *dequeue_message() {
	// Return NULL if none, perhaps?
	if (mq.front == mq.gap) return NULL;
	else {
		Message *next = mq.buffer[mq.front];
		mq.front = ahead(mq.front);
		return next;
	}
}



static void display_actor_dfn(ActorDef *dfn) {
	printf("<ActDfn: %s>", dfn->name->text);
}

static void blacken_actor_dfn(ActorDef *dfn) { 
	darken_in_place(&dfn->name);
	darkenTable(&dfn->msg_handler);
}

static size_t size_actor_dfn(ActorDef *dfn) { return sizeof(ActorDef); }

static GC_Kind KIND_ActorDef = {
	.display = display_actor_dfn,
	.deeply = display_actor_dfn,
	.blacken = blacken_actor_dfn,
	.size = size_actor_dfn,
};

void define_actor(byte nr_fields) {
	// Pops the name of the actor definition.
	// Returns new actor definition on the VM stack.
	ActorDef *dfn = gc_allocate(&KIND_ActorDef, sizeof(ActorDef));
	dfn->nr_fields = nr_fields;
	dfn->name = AS_STRING(pop());
	initTable(&dfn->msg_handler);
	populate_field_offset_table(&dfn->field_offset, nr_fields);
	push(GC_VAL(dfn));
}

void display_actor_tpl(ActorTemplate *tpl) {
	printf("<ActTpl: %s>", tpl->actor_dfn->name->text);
}

static void blacken_actor_tpl(ActorTemplate *tpl) {
	darken_in_place(&tpl->actor_dfn);
	darkenValues(tpl->fields, tpl->actor_dfn->nr_fields);
}

static size_t size_actor_tpl(ActorTemplate *tpl) {
	return sizeof(ActorTemplate) + tpl->actor_dfn->nr_fields * sizeof(Value);
}


static GC_Kind KIND_ActorTpl = {
	.display = display_actor_tpl,
	.deeply = display_actor_tpl,
	.blacken = blacken_actor_tpl,
	.size = size_actor_tpl,
};

void make_template_from_dfn() {
	size_t nr_fields = AS_ACTOR_DFN(TOP)->nr_fields;
	size_t payload_size = nr_fields * sizeof(Value);
	ActorTemplate *tpl = gc_allocate(&KIND_ActorTpl, sizeof(ActorTemplate) + payload_size);
	tpl->actor_dfn = AS_ACTOR_DFN(pop());
	memcpy(&tpl->fields, vm.stackTop - nr_fields, payload_size);
	vm.stackTop -= nr_fields;
	push(GC_VAL(tpl));
}


void display_actor(Actor *actor) {
	printf("<Actor: %s>", actor->actor_dfn->name->text);
}

static void blacken_actor(Actor *actor) {
	darken_in_place(&actor->actor_dfn);
	darkenValues(actor->fields, actor->actor_dfn->nr_fields);
}

static size_t size_actor(Actor *actor) {
	return sizeof(Actor) + actor->actor_dfn->nr_fields * sizeof(Value);
}

static GC_Kind KIND_Actor = {
	.display = display_actor,
	.deeply = display_actor,
	.blacken = blacken_actor,
	.size = size_actor,
};

void make_actor_from_template() {
	size_t nr_fields = AS_ACTOR_TPL(TOP)->actor_dfn->nr_fields;
	size_t payload_size = nr_fields * sizeof(Value);
	Actor *actor = gc_allocate(&KIND_Actor, sizeof(Actor) + payload_size);
	actor->actor_dfn = AS_ACTOR_TPL(TOP)->actor_dfn;
	memcpy(&actor->fields, &AS_ACTOR_TPL(TOP)->fields, payload_size);
	TOP = GC_VAL(actor);
}
