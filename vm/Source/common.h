#pragma once

/*

Note on naming style:

The identifiers may look inconsistent. Some are camelCase; others are snake_case.
But there is something of a pattern. Code written on Wednesdays -- no, that's not it.
Functions completely, or nearly, cribbed from Nystrom's book start out in camel case.
And for the first brief while, I kept that for consistency.

However, I find snake_case easier to read and write. So the newer stuff mostly uses it.
Eventually I might enforce a consistent style. But for now, there are bigger fish to fry.

*/

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum { // written to match the standard preamble's order type
	LESS = 0,
	SAME = 1,
	MORE = 2,
} TotalOrder;

#ifdef _DEBUG
//#define DEBUG_PRINT_GLOBALS
//#define DEBUG_PRINT_CODE
//#define DEBUG_TRACE_EXECUTION
//#define DEBUG_TRACE_QUEUE
//#define DEBUG_STRESS_GC
//#define DEBUG_ANNOUNCE_GC
#define RECLAIM_CHUNKS 1
#else
#define RECLAIM_CHUNKS 0
#endif // _DEBUG

#define byte uint8_t
#define BYTE_CARDINALITY 256

#define DEFINE_VECTOR_TYPE(kind, type) \
	typedef struct { size_t cnt; size_t cap; type *at; } kind; \
	void init   ## kind(kind* vec); \
	void free   ## kind(kind* vec); \
	void resize ## kind(kind* vec, size_t cap); \
	size_t  append ## kind(kind* vec, type item);

__declspec(noreturn) void crashAndBurn(const char *why, ...);


/* gc.h */

typedef void (*Verb)();
typedef void (*Method)(void *item);
typedef size_t (*SizeMethod)(void *item); // Return the size of the payload.

typedef struct {
	Method display;
	Method deeply;
	Method blacken;
	SizeMethod size;
	Verb compare;  // ( a b -- TotalOrder )
	Method finalize; // Must not gc_allocate; gets called mid-collection.
} GC_Kind;

typedef union {
	GC_Kind *kind;
	void *ptr;
} GC;

void init_gc();
void gc_install_roots(Verb verb);
void gc_forget_roots(Verb verb);

void *gc_allocate(GC_Kind *kind, size_t size);
void *darken(void *gc);
static inline void darken_in_place(void **gc) { *gc = darken(*gc); }
void gc_must_finalize(GC *item);

/* memory.h */

#define ALLOCATE(type, count) (type*)reallocate(NULL, sizeof(type) * (count))
#define FREE(type, pointer) reallocate(pointer, 0)
#define FREE_ARRAY(type, pointer) reallocate(pointer, 0)

#define GROW(cap) ((cap) < 8 ? 8 : (cap) * 2)

#define DEFINE_VECTOR_CODE(Kind, type) \
	void init   ## Kind (Kind *vec)            { vec->cnt = vec->cap = 0; vec->at = NULL; } \
	void free   ## Kind (Kind *vec)            { FREE_ARRAY(type, vec->at); init ## Kind (vec); } \
	void resize ## Kind (Kind *vec, size_t cap){ vec->at = (type*)reallocate(vec->at, sizeof(type) * cap); vec->cap = cap; }

#define DEFINE_VECTOR_APPEND(Kind, type) \
  size_t append ## Kind (Kind *vec, type item) { if (vec->cap <= vec->cnt) resize ## Kind (vec, GROW(vec->cap)); vec->at[vec->cnt++] = item; return vec->cnt - 1; }

void *reallocate(void *pointer, size_t newSize);

/* value.h */

#define NUMBER_FORMAT "%.17g"

typedef enum {
	VAL_NIL,     // Not the same as Sophie's nil.
	VAL_BOOL,    // Don't really need, as ENUM serves.
	VAL_NUMBER,  // Meaning "double-precision"
	VAL_ENUM,    // Overload for runes
	VAL_PTR,     // Non-collectable opaque pointer.
	VAL_GC,      // Pointer to Garbage-Collected Heap for this and subsequent tags.
	VAL_THUNK,   // Pointer to thunk; helps with VM to avoid indirections.
	VAL_CLOSURE, // And why not exploit the tags to full effect?
	VAL_NATIVE,
	VAL_CTOR,
	VAL_BOUND,
	VAL_MESSAGE,
	VAL_FN,      // Not-closed function. Found in constant tables.
	VAL_GLOBAL,  // Global reference; used only during compiling.
} ValueType;


typedef struct {
	ValueType type;
	union {
		bool boolean;
		double number;
		int tag;
		void *ptr;
		GC *gc;
	} as;
} Value;


#define IS_NIL(value)     ((value).type == VAL_NIL)
#define IS_BOOL(value)    ((value).type == VAL_BOOL)
#define IS_NUMBER(value)  ((value).type == VAL_NUMBER)
#define IS_ENUM(value)    ((value).type == VAL_ENUM)
#define IS_GC_ABLE(value) ((value).type >= VAL_GC)
#define IS_THUNK(value)   ((value).type == VAL_THUNK)
#define IS_CLOSURE(value) ((value).type == VAL_CLOSURE)
#define IS_NATIVE(value)  ((value).type == VAL_NATIVE)
#define IS_CTOR(value)    ((value).type == VAL_CTOR)
#define IS_BOUND(value)   ((value).type == VAL_BOUND)
#define IS_MESSAGE(value) ((value).type == VAL_MESSAGE)
#define IS_FN(value)      ((value).type == VAL_FN)
#define IS_GLOBAL(value)  ((value).type == VAL_GLOBAL)

#define AS_BOOL(value)    ((value).as.boolean)
#define AS_NUMBER(value)  ((value).as.number)
#define AS_ENUM(value)    ((value).as.tag)
#define AS_PTR(value)     ((value).as.ptr)
#define AS_GC(value)      ((value).as.gc)

#define NIL_VAL	            ((Value){VAL_NIL, {.number = 0}})
#define BOOL_VAL(value)     ((Value){VAL_BOOL, {.boolean = value}})
#define NUMBER_VAL(value)   ((Value){VAL_NUMBER, {.number = value}})
#define ENUM_VAL(value)     ((Value){VAL_ENUM, {.tag = value}})
#define PTR_VAL(object)     ((Value){VAL_PTR, {.ptr = object}})
#define GC_VAL(object)      ((Value){VAL_GC, {.ptr = object}})
#define CLOSURE_VAL(object) ((Value){VAL_CLOSURE, {.ptr = object}})
#define THUNK_VAL(object)   ((Value){VAL_THUNK, {.ptr = object}})
#define NATIVE_VAL(object)  ((Value){VAL_NATIVE, {.ptr = object}})
#define CTOR_VAL(object)    ((Value){VAL_CTOR, {.ptr = object}})
#define BOUND_VAL(object)   ((Value){VAL_BOUND, {.ptr = object}})
#define MESSAGE_VAL(object) ((Value){VAL_MESSAGE, {.ptr = object}})
#define FN_VAL(object)      ((Value){VAL_FN, {.ptr = object}})
#define GLOBAL_VAL(object)  ((Value){VAL_GLOBAL, {.ptr = object}})

DEFINE_VECTOR_TYPE(ValueArray, Value)

void printValue(Value value);
void printValueDeeply(Value value);

void darkenValues(Value *at, size_t count);
void darkenValueArray(ValueArray *vec);

extern char *valKind[];

/* chunk.h */

typedef struct {
	size_t start;
	int line;
} Bound;

DEFINE_VECTOR_TYPE(Code, byte)
DEFINE_VECTOR_TYPE(Lines, Bound)

typedef struct {
	Code code;
	ValueArray constants;
	Lines lines;
} Chunk;

void initChunk(Chunk *chunk);
void freeChunk(Chunk *chunk);
void setLine(Chunk *chunk, int line);
int findLine(Chunk *chunk, size_t offset);

static inline void darkenChunk(Chunk *chunk) { darkenValueArray(&chunk->constants); }

/* debug.h */

void disassembleChunk(Chunk *chunk, const char *name);
int disassembleInstruction(Chunk *chunk, int offset);

/* object.h */

typedef struct {
	GC header;
	uint32_t hash;
	size_t length;
	char text[];
} String;

uint32_t hashString(const char *key, size_t length);
String *new_String(size_t length);
String *intern_String(String *string);
String *import_C_string(const char *chars, size_t length);
void push_C_string(const char *name);
void printObject(GC *item);
void printObjectDeeply(GC *item);

#define AS_STRING(it) ((String *)AS_PTR(it))
bool is_string(void *item);

/* table.h */

typedef struct {
	String *key;
	Value value;
} Entry;

DEFINE_VECTOR_TYPE(Table, Entry)

Value tableGet(Table *table, String *key);
bool tableSet(Table *table, String *key, Value value);
Value table_get_from_C(Table *table, const char *text);
void table_set_from_C(Table *table, char *text, Value value);
void tableAddAll(Table *from, Table *to);
Entry *tableFindString(Table *table, const char *chars, size_t length, uint32_t hash);
bool tableDelete(Table *table, String *key);
void darkenTable(Table *table);
void tableDump(Table *table);
void populate_field_offset_table(Table *table, int nr_fields);

/* function.h */

typedef enum {
	TYPE_FUNCTION,
	TYPE_MEMOIZED,
	TYPE_SCRIPT,
} FunctionType;

typedef struct {
	byte is_local;
	byte offset;
} Capture;

typedef struct  {
	// Keep child-functions as objects in the constant table.
	GC header;
	String *name;
	byte arity;
	byte nr_captures;
	byte fn_type;
	bool visited;
	Chunk chunk;
	Capture captures[];
} Function;


typedef struct {
	GC header;
	Function *function;
	Value captives[];
} Closure;

void close_function(Value *stack_slot);
Function *newFunction(FunctionType fn_type, Chunk *chunk, byte arity, byte nr_captures);

String *name_of_function(Function *function);

#define AS_CLOSURE(value) ((Closure *)AS_PTR(value))
#define AS_FN(value) ((Function *)AS_PTR(value))


extern GC_Kind KIND_snapped;

#define SNAP_RESULT(thunk_ptr) (thunk_ptr->captives[0])
#define DID_SNAP(thunk_ptr) (SNAP_RESULT(thunk_ptr).type != VAL_NIL)

static inline void darkenValue(Value *value) {
	if (IS_THUNK(*value) && DID_SNAP(AS_CLOSURE(*value))) {
		*value = SNAP_RESULT(AS_CLOSURE(*value));
	}
	if (IS_GC_ABLE(*value)) {
		darken_in_place(&value->as.ptr);
	}
}

/* record.h */

typedef struct {
	GC header;
	String *name;
	Table field_offset;
	byte tag;
	byte nr_fields;
} Constructor;

typedef struct {
	GC header;
	Constructor *constructor;
	Value fields[];
} Record;


Record *construct_record();
void make_constructor(int tag, int nr_fields);  // ( field_name ... ctor_name -- ctor )
void apply_constructor();

#define AS_CTOR(value) ((Constructor*)AS_PTR(value))
#define AS_RECORD(value) ((Record*)AS_PTR(value))

extern GC_Kind KIND_Constructor;
extern GC_Kind KIND_Record;

static inline bool is_record(Value value) {
	return (value.type == VAL_GC) && (&KIND_Record == AS_GC(value)->kind);
}

/* actor.h */

typedef struct {
	GC header;
	String *name;
	Table field_offset;
	Table msg_handler;
	byte nr_fields;
} ActorDef;

typedef struct {
	GC header;
	ActorDef *actor_dfn;
	Value fields[];
} ActorTemplate;

typedef struct {
	// This looks very similar to a Record and/or an ActorTemplate.
	// But those are coincidental and ephemeral similarities.
	GC header;
	ActorDef *actor_dfn;
	Value fields[];
} Actor;

typedef struct {
	GC header;
	// It might be useful to capture the sender's source location as
	// a clue in case an actor panics while responding to a message.
	Actor *self;
	Value callable;
	Value payload[];
} Message;


void init_actor_model();
void enqueue_message(Value message);

void define_actor(byte nr_fields);  // ( field_names... name -- dfn )
void make_template_from_dfn();  // ( args... dfn -- tpl )
void make_actor_from_template();  // ( tpl -- actor )
void bind_task_from_closure();  // ( closure -- message )
void bind_method_by_name();  // ( actor message_name -- bound_method )
void apply_bound_method();  // ( args... bound_method -- message )
void drain_the_queue();

#define AS_ACTOR_DFN(value) ((ActorDef*)AS_PTR(value))
#define AS_ACTOR_TPL(value) ((ActorTemplate*)AS_PTR(value))
#define AS_ACTOR(value) ((Actor*)AS_PTR(value))
#define AS_MESSAGE(value) ((Message*)AS_PTR(value))

bool is_actor_dfn(Value v);
bool is_actor_tpl(Value v);
bool is_actor(Value v);

/* vm.h */

#define FRAMES_MAX 64
#define STACK_MAX (FRAMES_MAX * BYTE_CARDINALITY)


static inline uint16_t word_at(const char *ch) {
	uint16_t *ptr = (uint16_t *)(ch);
	return *ptr;
}

typedef struct {
	Closure *closure;  // Need this for grabbing captures
} Trace;

typedef struct {
	Trace traces[FRAMES_MAX + 1];
	Trace *trace;
	Value stack[STACK_MAX];
	Value *stackTop;
	Table strings;
	Value cons;
	Value nil;
	Value maybe_this;
	Value maybe_nope;
} VM;


extern VM vm;

void vm_init();
void vm_dispose();

Value force(Value value);
Value run(Closure *closure);
void perform(Value action);

static inline void push(Value value) {
	assert(vm.stackTop < &vm.stack[STACK_MAX]);
	*vm.stackTop = value;
	vm.stackTop++;
}

static inline Value pop() {
	vm.stackTop--;
	assert(vm.stackTop >= vm.stack);
	return *vm.stackTop;
}

#define TOP (vm.stackTop[-1])
#define SND (vm.stackTop[-2])

static inline void merge(Value v) { pop(); TOP = v; }

// Now some FORTH-style stack operators because keeping pointers
// anywhere else is dangerous because allocation moves things around.

static inline void swap() { Value v = TOP; TOP = SND; SND = v; }  // ( a b -- b a )
static inline void dup() { push(TOP); }  // ( a -- a a )
static inline void over() { push(SND); }  // ( a b -- a b a )

void defineGlobal();  // ( value name -- )

void vm_capture_preamble_specials(Table *globals);
__declspec(noreturn) void vm_panic(const char *format, ...);

// Force whatever object is at top-of-stack recursively until it reaches no thunks.
// Handy for FFI things, but beware of limited stack depth.
void force_deeply();

/* native.h */

typedef Value(*NativeFn)(Value *args);

typedef struct {
	GC header;
	byte arity;
	NativeFn function;
	String *name;
} Native;

#define AS_NATIVE(value) ((Native *)AS_PTR(value))

void install_native_functions();
void create_native_function(const char *name, byte arity, NativeFn function);  // ( -- )
void create_native_method(const char *name, byte arity, NativeFn function);  // ( ActorDfn -- ActorDfn )

// Macro for easier list-enumeration.
#define FOR_LIST(arg) for (;arg = force(arg),!IS_ENUM(arg);arg = AS_RECORD(arg)->fields[1])
#define LIST_HEAD(arg) force(AS_RECORD(arg)->fields[0])

/* ffi.h */

void ffi_prepare_modules();
NativeFn ffi_find_module(String *key);

/* game.h */

Value game_sophie_init(Value *args);
