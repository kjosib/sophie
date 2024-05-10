#pragma once
#ifdef _WIN32
#pragma warning(disable : 4996)  /* Stop irrelevant warning about fopen on MS compilers */
#endif


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

#include "debug.h"

typedef union {
	uint64_t bits;
	double number;
	void *hex;  // This case only exists to make the debugger provide a hexadecimal read-out.
} Value;

#define byte uint8_t
#define BYTE_CARDINALITY 256

#define DEFINE_VECTOR_TYPE(kind, type) \
	typedef struct { size_t cnt; size_t cap; type *at; } kind; \
	void init   ## kind(kind* vec); \
	void free   ## kind(kind* vec); \
	void resize ## kind(kind* vec, size_t cap); \
	size_t  append ## kind(kind* vec, type item); \
	size_t  alloc ## kind(kind* vec);

__declspec(noreturn) void crashAndBurn(const char *why, ...);


/* gc.h */

typedef void (*Verb)();
typedef void (*Method)(void *item);
typedef size_t (*SizeMethod)(void *item); // Return the size of the payload.
typedef Value(*Apply)(); // Expects self at TOS.
typedef int (*TypeIndexFn)(void *item); // Return the type-index of the payload.

typedef struct {
	Method display;
	Method deeply;
	Method blacken;
	SizeMethod size;
	TypeIndexFn type_index;
	Apply apply;     // Arguments on the stack.
	Method finalize; // Must not gc_allocate; gets called mid-collection.
	char *name;
} GC_Kind;

typedef union GC GC;

union GC {
	GC_Kind *kind;
	void *ptr;
	GC *fwd;
};

void init_gc();
void gc_install_roots(Verb verb);
void gc_forget_roots(Verb verb);

void *gc_allocate(GC_Kind *kind, size_t size);

void collect_garbage();
void darkenValue(Value *value);

/*
There is a software write-barrier:
After an object is first initialized,
the mutator must call gc_mutate for all further mutation.
*/
void gc_mutate(Value *dst, Value value);

GC *darken(GC *gc);
static inline void darken_in_place(void **gc) {
	// Suitable specifically for undecorated pointers, not packed values.
	*gc = darken((GC*)(*gc));
}
// gc_move_journal is suitable only for arrays, not hash-tables.
void gc_move_journal(void *start, void *stop, void *new_start);
void gc_forget_journal_portion(void *start, void *stop);
#if USE_FINALIZERS
void gc_please_finalize(GC *item);
#endif

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

#define DEFINE_VECTOR_ALLOC(Kind, type) \
  size_t alloc ## Kind (Kind *vec) { if (vec->cap <= vec->cnt) resize ## Kind (vec, GROW(vec->cap)); vec->cnt++; return vec->cnt - 1; }

void *reallocate(void *pointer, size_t newSize);

/* value.h */

#define NUMBER_FORMAT "%.17g"

#define SHIFT(x) x ## 000000000000

#define BOX_BITS SHIFT(0x7ff4)
#define TAG_BITS SHIFT(0x800b)  // The regex [7F]FF[4567CDEF] encompasses the usable value tags.
#define SIGN_BIT SHIFT(0x8000)
#define PAYLOAD_BITS (SHIFT(0x1)-1)
#define IS_NUMBER(v) (((v).bits & BOX_BITS) != BOX_BITS)  // Meaning "double-precision"
#define INDICATOR(v) ((v).bits & SHIFT(0xffff))
#define IND_UNSET    BOX_BITS       // Not the same as Sophie's nil.
#define IND_RUNE     SHIFT(0x7ff5)  // Overload for characters, booleans, etc.
#define IND_ENUM     SHIFT(0x7ff6)  // Contains a vtable index for magic.
#define IND_PTR      SHIFT(0x7ff7)  // Non-collectable opaque pointer.
#define IND_GC       SHIFT(0xfff4)  // Pointer to Garbage-Collected Heap for this and subsequent tags.
#define IND_CLOSURE  SHIFT(0xfff5)  // Pointer to callable; helps with VM to avoid indirections.
#define IND_THUNK    SHIFT(0xfff6)  // As long as the VM is recursive, it must check for these.
#define IND_NATIVE   SHIFT(0xfff7)  // Because why not?
#define IND_GLOBAL   SHIFT(0xfffd)  // Global reference; used only during compiling.

#define IS_UNSET(value)   ((value).bits == IND_UNSET)
#define IS_RUNE(value)    (INDICATOR(value) == IND_RUNE)
#define IS_ENUM(value)    (INDICATOR(value) == IND_ENUM)
#define IS_PTR(value)     (INDICATOR(value) == IND_PTR)
#define IS_GC_ABLE(value) (((value).bits & IND_GC) == IND_GC)
#define IS_CLOSURE(value) (INDICATOR(value) == IND_CLOSURE)
#define IS_THUNK(value)   (INDICATOR(value) == IND_THUNK)
#define IS_NATIVE(value)   (INDICATOR(value) == IND_NATIVE)
#define IS_GLOBAL(value)  (INDICATOR(value) == IND_GLOBAL)

#define PACK(indic, datum) ((Value){.bits = indic | ((uint64_t)(datum))})

#define AS_BOOL(value)    ((bool)PAYLOAD(value))
#define AS_RUNE(value)    ((int32_t)PAYLOAD(value))
#define AS_NUMBER(value)  ((value).number)
#define PAYLOAD(value)    ((value).bits & PAYLOAD_BITS)
#define AS_ENUM_TAG(value)    ((int)PAYLOAD(value) & 0xFF)
#define AS_ENUM_VT_IDX(value)    ((int)PAYLOAD(value) >> 8)
#define AS_PTR(value)     ((void *)PAYLOAD(value))
#define AS_GC(value)      ((GC *)PAYLOAD(value))

#define UNSET_VAL	        PACK(IND_UNSET, 0)
#define RUNE_VAL(value)     PACK(IND_RUNE, ((int32_t)(value)))	
#define BOOL_VAL(value)     PACK(IND_ENUM, ((bool)(value)))
#define NUMBER_VAL(value)   ((Value){.number=value})
#define ENUM_VAL(vt_idx, tag)     PACK(IND_ENUM, ((vt_idx)<<8|(tag)))
#define PTR_VAL(object)     PACK(IND_PTR, object)
#define GC_VAL(object)      PACK(IND_GC, object)
#define CLOSURE_VAL(object) PACK(IND_CLOSURE, object)
#define THUNK_VAL(object)   PACK(IND_THUNK, object)
#define NATIVE_VAL(object)  PACK(IND_NATIVE, object)
#define GLOBAL_VAL(object)  PACK(IND_GLOBAL, object)

typedef struct {
	size_t cnt;
	size_t cap;
	Value *at;
	// size_t id;
} ValueArray;
void initValueArray(ValueArray *vec);
void freeValueArray(ValueArray *vec);
size_t appendValueArray(ValueArray *vec);  // ( value -- )

void print_simply(Value value);
void printValue(Value value);
void printValueDeeply(Value value);
void printObject(GC *item);
void printObjectDeeply(GC *item);

void darkenValues(Value *at, size_t count);
void darkenValueArray(ValueArray *vec);

char *valKind(Value value);


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

/* string.h */

typedef struct {
	GC header;
	uint32_t hash;
	size_t length;
	char text[];
} String;

uint32_t hashString(const char *key, size_t length);
#define WRAP(index, capacity) ( (index) & ( (capacity) -1 ) )

String *new_String(size_t length);
void intern_String();  // ( string -- string )
void import_C_string(const char *chars, size_t length);  // ( -- string )
void push_C_string(const char *name);

#define AS_STRING(it) ((String *)PAYLOAD(it))
bool is_string(void *item);

typedef struct {
	size_t capacity;
	size_t population;
	size_t threshold;
	Value *at;
} StringTable;

void string_table_init(StringTable *table, size_t capacity);
void string_table_free(StringTable *table);

/* table.h */

typedef struct {
	Value key;
	Value value;
} Entry;

extern GC_Kind KIND_Table;

typedef struct {
	GC header;
	size_t capacity;
	size_t population;
	Entry at[];
} Table;

#define AS_TABLE(v) ((Table*)PAYLOAD(v))

Table *new_table(size_t capacity);

Value tableGet(Value tableValue, String *key);
void tableSet();  // ( value key table -- table )
Value table_get_from_C(const char *text);  // ( Table -- Table )
void table_set_from_C(char *text, Value value);  // ( table -- table )
void tableDump(Table *table);
void make_field_offset_table(int nr_fields);  // ( Name ... -- Table )

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

#define AS_CLOSURE(value) ((Closure *)PAYLOAD(value))
#define AS_FN(value) ((Function *)PAYLOAD(value))

bool is_function(Value value);

extern GC_Kind KIND_Closure, KIND_Snapped;

#define SNAP_RESULT(thunk_ptr) (thunk_ptr->captives[0])
#define DID_SNAP(value) (&KIND_Snapped == AS_GC(value)->kind)

/* record.h */

typedef struct {
	GC header;
	String *name;
	Value field_offset;
	int vt_idx;
	byte tag;
	byte nr_fields;
} Constructor;

typedef struct {
	GC header;
	Constructor *constructor;
	Value fields[];
} Record;


Value construct_record();
void make_constructor(int vt_idx, int tag, int nr_fields);  // ( field_table name -- constructor )

#define AS_CTOR(value) ((Constructor*)PAYLOAD(value))
#define AS_RECORD(value) ((Record*)PAYLOAD(value))

extern GC_Kind KIND_Record;

static inline bool is_record(Value value) {
	return (INDICATOR(value) == IND_GC) && (&KIND_Record == AS_GC(value)->kind);
}


/* dispatch.h */

typedef enum {
	BOP_ADD,
	BOP_SUB,
	BOP_MUL,
	BOP_DIV,
	BOP_IDIV,
	BOP_POW,
	BOP_MOD,
	BOP_CMP,

	NR_BOPS,
} BopType;

// Some type-index numbers for primitive types:
#define TX_FLAG 0
#define TX_RUNE 1
#define TX_NUMBER 2
#define TX_STRING 3
// See also install_builtin_vtables() in assembler.c.

typedef struct {
	int type_index;
	Value callable;
} DispatchEntry;

DEFINE_VECTOR_TYPE(DispatchTable, DispatchEntry)

typedef struct {
	String *type_name; // Probably handy for debugging.
	Value neg;  // Single dispatch, so this is fine.
	DispatchTable dt[NR_BOPS];
} VTable;

void init_VTable(VTable *vt, String *type_name);

DEFINE_VECTOR_TYPE(VMap, VTable)

extern VMap vmap;

void init_dispatch();
void dispose_dispatch();
void install_binop(BopType bop, int lhs_tx, int rhs_tx);
Value find_dispatch(DispatchTable *dt, int type_index);

/* actor.h */

extern GC_Kind KIND_Message, KIND_BoundMethod, KIND_ActorDfn;

typedef struct {
	GC header;
	String *name;
	Value field_offset;
	Value msg_handler;
	byte nr_fields;
} ActorDfn;

typedef struct {
	GC header;
	ActorDfn *actor_dfn;
	Value fields[];
} ActorTemplate;

typedef struct {
	// This looks very similar to a Record and/or an ActorTemplate.
	// But those are coincidental and ephemeral similarities.
	GC header;
	ActorDfn *actor_dfn;
	Value fields[];
} Actor;

typedef struct {
	GC header;
	// It might be useful to capture the sender's source location as
	// a clue in case an actor panics while responding to a message.
	Value method;
	Value payload[];
} Message;


void init_actor_model();
void enqueue_message(Value message);

void define_actor();  // ( field_names... name -- ActorDfn )
void install_method();  // ( ActorDfn Method Name -- ActorDfn )
Value make_template_from_dfn();  // ( args... dfn -- ) tpl
void make_actor_from_template();  // ( tpl -- actor )
void bind_task_from_closure();  // ( closure -- message )
void bind_method_by_name();  // ( actor message_name -- bound_method )
void drain_the_queue();

#define AS_ACTOR_DFN(value) ((ActorDfn*)PAYLOAD(value))
#define AS_ACTOR_TPL(value) ((ActorTemplate*)PAYLOAD(value))
#define AS_ACTOR(value) ((Actor*)PAYLOAD(value))
#define AS_MESSAGE(value) ((Message*)PAYLOAD(value))

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
	StringTable strings;
	Value cons;
	Value nil;
	Value maybe_this;
	Value maybe_nope;
	Value less;
	Value same;
	Value more;
} VM;


extern VM vm;

void vm_init();
void vm_dispose();

Value force(Value value);
Value vm_run();
void perform();

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

#define INDEX(x) (vm.stackTop[-(x)])
#define TOP INDEX(1)
#define SND INDEX(2)
#define THD INDEX(3)

static inline Value apply() { return AS_GC(TOP)->kind->apply(); }

static inline void merge(Value v) { pop(); TOP = v; }

// Now some FORTH-style stack operators because keeping pointers
// anywhere else is dangerous because allocation moves things around.

static inline void swap() { Value v = TOP; TOP = SND; SND = v; }  // ( a b -- b a )
static inline void dup() { push(TOP); }  // ( a -- a a )
static inline void over() { push(SND); }  // ( a b -- a b a )

static inline void snoc() { swap(); push(vm.cons); push(construct_record()); }

void defineGlobal();  // ( value name -- )

void vm_capture_preamble_specials();
__declspec(noreturn) void vm_panic(const char *format, ...);

/* native.h */

extern GC_Kind KIND_Native;

typedef Value(*NativeFn)(Value *args);

typedef struct {
	GC header;
	byte arity;
	NativeFn function;
	String *name;
} Native;

#define AS_NATIVE(value) ((Native *)PAYLOAD(value))

void install_native_functions();
void create_native_function(const char *name, byte arity, NativeFn function);  // ( -- )
void create_native_method(const char *name, byte arity, NativeFn function);  // ( ActorDfn -- ActorDfn )

// Macro for easier list-enumeration.
#define FIELD(arg, nr) (AS_RECORD(arg)->fields[nr])
#define LIST_HEAD(arg) force(FIELD(arg, 0))
#define LIST_TAIL(arg) FIELD(arg, 1)
#define FOR_LIST(arg) for (;arg = force(arg),!IS_ENUM(arg);arg = LIST_TAIL(arg))

/* ffi.h */

void ffi_prepare_modules();
NativeFn ffi_find_module(char *key);

/* game.h */

Value game_sophie_init(Value *args);
