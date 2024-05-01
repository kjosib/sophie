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
	// Careful: There is a message not on the stack, so no GC allocations.
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

static size_t arity_of_message(Message *msg) {
	// Accepts a GC-able parameter but doesn't call anything and therefore can't allocate.
	assert(IS_GC_ABLE(msg->method));
	switch (INDICATOR(msg->method)) {
	case IND_CLOSURE: return AS_CLOSURE(msg->method)->function->arity;
	case IND_GC: return AS_NATIVE(msg->method)->arity;
	default: crashAndBurn("Nerp!");
	}
}

void enqueue_message(Value value) {
	// Careful: The message here may not be on the stack.
	Message *msg = AS_MESSAGE(value);
#ifdef DEBUG_TRACE_QUEUE
	fputs("< Enqueue: ", stdout);
	printValue(msg->method);
	fputc('\n', stdout);
#endif // DEBUG_TRACE_QUEUE
	mq.buffer[mq.gap] = msg;
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



static void display_actor_dfn(ActorDfn *dfn) {
	printf("<ActDfn: %s>", dfn->name->text);
}

static void blacken_actor_dfn(ActorDfn *dfn) {
	darken_in_place(&dfn->name);
	darkenTable(&dfn->msg_handler);
}

static size_t size_actor_dfn(ActorDfn *dfn) { return sizeof(ActorDfn); }

static GC_Kind KIND_ActorDfn = {
	.display = display_actor_dfn,
	.deeply = display_actor_dfn,
	.blacken = blacken_actor_dfn,
	.size = size_actor_dfn,
	.apply = make_template_from_dfn,
	.name = "Actor Definition",
};

void define_actor(byte nr_fields) {
	// Pops the name of the actor definition.
	// Returns new actor definition on the VM stack.
	ActorDfn *dfn = gc_allocate(&KIND_ActorDfn, sizeof(ActorDfn));
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
	.name = "Actor Template",
};


static void force_stack_slots(Value *start, Value *stop) {
	// This is somewhat a half-measure, because ideally messages should contain no thunks at any depth.
	// But for the moment it will have to serve. And it's probably enough for making templates.
	for (Value *p = start; p < stop; p++) *p = force(*p);
}


Value make_template_from_dfn() {
	assert(is_actor_dfn(TOP));
	size_t nr_fields = AS_ACTOR_DFN(TOP)->nr_fields;
	Value *base = &TOP - nr_fields;
	assert(base >= vm.stack);
	force_stack_slots(base, &TOP);
	size_t payload_size = nr_fields * sizeof(Value);
	ActorTemplate *tpl = gc_allocate(&KIND_ActorTpl, sizeof(ActorTemplate) + payload_size);
	tpl->actor_dfn = AS_ACTOR_DFN(TOP);
	memcpy(&tpl->fields, base, payload_size);
	vm.stackTop = base;
	return GC_VAL(tpl);
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
	.name = "Actor",
};

bool is_actor_dfn(Value v) { return IS_GC_ABLE(v) && &KIND_ActorDfn == AS_GC(v)->kind; }
bool is_actor_tpl(Value v) { return IS_GC_ABLE(v) && &KIND_ActorTpl == AS_GC(v)->kind; }
bool is_actor(Value v) { return IS_GC_ABLE(v) && &KIND_Actor == AS_GC(v)->kind; }

void make_actor_from_template() {
	assert(is_actor_tpl(TOP));
	size_t nr_fields = AS_ACTOR_TPL(TOP)->actor_dfn->nr_fields;
	size_t payload_size = nr_fields * sizeof(Value);
	Actor *actor = gc_allocate(&KIND_Actor, sizeof(Actor) + payload_size);
	actor->actor_dfn = AS_ACTOR_TPL(TOP)->actor_dfn;
	memcpy(&actor->fields, &AS_ACTOR_TPL(TOP)->fields, payload_size);
	TOP = GC_VAL(actor);
}

void display_bound(Message *msg) { printf("<bound method>"); }

static void blacken_bound(Message *msg) { darkenValue(&msg->method); darkenValue(&msg->payload[0]); }
static size_t size_bound(Message *msg) { return sizeof(Message) + sizeof(Value); }

static void blacken_message(Message *msg) {
	darkenValue(&msg->method);
	darkenValues(msg->payload, arity_of_message(msg));
}

static size_t size_message(Message *msg) { return sizeof(Message) + arity_of_message(msg) * sizeof(Value); }

static Value apply_message() {
	enqueue_message(pop());
	return UNSET_VAL;
}

GC_Kind KIND_Message = {
	.blacken = blacken_message,
	.size = size_message,
	.apply = apply_message,
	.name = "Message",
};


static Value apply_bound_method() {
	size_t arity = arity_of_message(AS_MESSAGE(TOP));
	assert(arity);
	Value *base = vm.stackTop - arity;
	force_stack_slots(base, &TOP);
	Message *msg = gc_allocate(&KIND_Message, sizeof(Message) + arity * sizeof(Value));
	Message *bound = AS_MESSAGE(TOP);
	msg->method = bound->method;
	msg->payload[0] = bound->payload[0];
	memcpy(&msg->payload[1], base, (arity - 1) * sizeof(Value));
	vm.stackTop = base;
	return GC_VAL(msg);
}


GC_Kind KIND_BoundMethod = {
	// These things definitely have a receiver,
	// but no other associated arguments.
	.display = display_bound,
	.deeply = display_bound,
	.blacken = blacken_bound,
	.size = size_bound,
	.apply = apply_bound_method,
	.name = "Bound Method",
};

void bind_method_by_name() {  // ( actor message_name -- bound_method )
	assert(IS_GC_ABLE(SND));
	assert(AS_GC(SND)->kind == &KIND_Actor);
	assert(IS_GC_ABLE(TOP));
	assert(is_string(AS_GC(TOP)));
	Message *bound = gc_allocate(&KIND_BoundMethod, sizeof(Message)+sizeof(Value));
	bound->method = tableGet(&AS_ACTOR(SND)->actor_dfn->msg_handler, AS_STRING(TOP));
	bound->payload[0] = SND;
	SND = GC_VAL(bound);
	pop();
}


static void blacken_parametric(Message *msg) { darkenValue(&msg->method); }
static size_t size_parametric(Message *msg) { return sizeof(Message); }

static Value apply_parametric() {
	TOP = AS_MESSAGE(TOP)->method;
	int arity = AS_CLOSURE(TOP)->function->arity;
	Value *base = &TOP - arity;
	force_stack_slots(base, &TOP);
	Message *msg = gc_allocate(&KIND_Message, sizeof(Message) + arity * sizeof(Value));
	msg->method = TOP;
	memcpy(msg->payload, base, arity * sizeof(Value));
	vm.stackTop = base;
	return GC_VAL(msg);
}

static GC_Kind KIND_ParametricTask = {
	.blacken = blacken_parametric,
	.size = size_parametric,
	.apply = apply_parametric,
	.name = "Parametric Task",
};


void bind_task_from_closure() {
	// Convert a closure to a (possibly-parametric) task.
	// NB: In case arity == 0, then the method is a do-block, which already has procedural perspective.
	//     Otherwise, the method is a function which returns an action.
	// NB: In case messages desperately need to know their actor,
	//     this will need a replacement for KIND_Message.
	assert(IS_CLOSURE(TOP));
	Closure *closure = AS_CLOSURE(TOP);
	GC_Kind *kind = (closure->function->arity) ? &KIND_ParametricTask : &KIND_Message;
	Message *task = gc_allocate(kind, sizeof(Message));
	task->method = TOP;
	TOP = GC_VAL(task);
}


static void run_one_message(Message *msg) {
#ifdef DEBUG_TRACE_QUEUE
	printf("> Dequeue (%d)\n", (int)arity_of_message(msg));
#endif // DEBUG_TRACE_QUEUE
	Value *base = vm.stackTop;
	size_t arity = arity_of_message(msg);
	memcpy(vm.stackTop, msg->payload, arity * sizeof(Value));
	vm.stackTop += arity;
	push(msg->method);
	perform();
	vm.stackTop = base;
#ifdef DEBUG_TRACE_QUEUE
	printf("  <--->\n");
#endif // DEBUG_TRACE_QUEUE
}

void drain_the_queue() {
	while (!is_queue_empty()) run_one_message(dequeue_message());
}

void install_method() {  // ( ActorDfn Method Name -- ActorDfn )
	String *key = AS_STRING(pop());
	ActorDfn *dfn = AS_ACTOR_DFN(SND);
	bool was_new = tableSet(&dfn->msg_handler, key, pop());
	if (!was_new) crashAndBurn("already installed %s into %s", key->text, dfn->name->text);
}
