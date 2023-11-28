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

static int arity_of_message(Message *msg) {
	// Accepts a GC-able parameter but doesn't call anything and therefore can't allocate.
	Value callable = msg->callable;
	switch (callable.type) {
	case VAL_CLOSURE:
		return AS_CLOSURE(callable)->function->arity;
	case VAL_NATIVE:
		return AS_NATIVE(callable)->arity;
	default:
		crashAndBurn("bogus callable (%s) in bound method", valKind[callable.type]);
	}
}

void enqueue_message(Value message) {
	assert(IS_MESSAGE(message) || IS_BOUND(message));
#ifdef DEBUG_TRACE_QUEUE
	printf("< Enqueue: (%d)\n", arity_of_message(AS_MESSAGE(message)));
#endif // DEBUG_TRACE_QUEUE
	mq.buffer[mq.gap] = AS_MESSAGE(message);
	mq.gap = ahead(mq.gap);
	if (mq.gap == mq.front) grow_the_queue();
}

static bool is_queue_empty() {
	return mq.front == mq.gap;
}

static Message *dequeue_message() {
	assert(!is_queue_empty());
	Message *next = mq.buffer[mq.front];
	mq.front = ahead(mq.front);
	return next;
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

void display_bound(Message *msg) { printf("<bound method>"); }

void blacken_bound(Message *msg) { darken_in_place(&msg->self); darkenValue(&msg->callable); }

size_t size_bound(Message *msg) { return sizeof(Message); }

static GC_Kind KIND_bound = {
	.display = display_bound,
	.deeply = display_bound,
	.blacken = blacken_bound,
	.size = size_bound,
};

void bind_method() {
	Message *bound = gc_allocate(&KIND_bound, sizeof(Message));
	bound->self = AS_ACTOR(SND);
	bound->callable = TOP;
	SND = BOUND_VAL(bound);
	pop();
}

void bind_task_from_closure() {
	// Convert a closure to a bound method
	assert(IS_CLOSURE(TOP));
	Message *bound = gc_allocate(&KIND_bound, sizeof(Message));
	bound->self = NULL;
	bound->callable = TOP;
	TOP = BOUND_VAL(bound);
}

void display_message(Message *msg) { printf("<message>"); }

void blacken_message(Message *msg) {
	blacken_bound(msg);
	darkenValues(msg->payload, arity_of_message(msg));
}

size_t size_message(Message *msg) {
	int arity = arity_of_message(msg);
	return sizeof(Message) + arity * sizeof(Value);
}

static GC_Kind KIND_message = {
	.display = display_message,
	.deeply = display_message,
	.blacken = blacken_message,
	.size = size_message,
};


static void force_stack_slots(Value *start, Value *stop) {
	// This is somewhat a half-measure, because ideally messages should contain no thunks at any depth.
	// But for the moment it will have to serve.
	for (Value *p = start; p < stop; p++) *p = force(*p);
}

void apply_bound_method() {
	assert(IS_BOUND(TOP));
	int arity = arity_of_message(AS_MESSAGE(TOP));
	force_stack_slots(&TOP - arity, &TOP);
	Message *msg = gc_allocate(&KIND_message, sizeof(Message) + arity * sizeof(Value));
	Message *bound = AS_MESSAGE(pop());
	msg->self = bound->self;
	msg->callable = bound->callable;
	memcpy(msg->payload, vm.stackTop - arity, arity * sizeof(Value));
	vm.stackTop -= arity;
	push(MESSAGE_VAL(msg));
}

static void run_one_message(Message *msg) {
#ifdef DEBUG_TRACE_QUEUE
	printf("> Dequeue (%d)\n", arity_of_message(msg));
#endif // DEBUG_TRACE_QUEUE
	Value *base = vm.stackTop;
	if (msg->self != NULL) push(GC_VAL(msg->self));
	int arity = arity_of_message(msg);
	memcpy(vm.stackTop, msg->payload, arity * sizeof(Value));
	vm.stackTop += arity;
	switch (msg->callable.type) {
	case VAL_CLOSURE:
	{
		Value action = run(AS_CLOSURE(msg->callable));
		perform(action);
		break;
	}
	case VAL_NATIVE:
	{
		Native *native = AS_NATIVE(msg->callable);
		native->function(base);
		break;
	}
	default:
		crashAndBurn("Bad message callable");
	}
	vm.stackTop = base;
#ifdef DEBUG_TRACE_QUEUE
	printf("  <--->\n");
#endif // DEBUG_TRACE_QUEUE
}

void drain_the_queue() {
	while (!is_queue_empty()) run_one_message(dequeue_message());
}
