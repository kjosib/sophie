#include <stdarg.h>
#include <math.h>
#include <time.h>
#include "common.h"
#include "opcodes.h"

#define CLOSURE (vm.trace->closure)


VM vm;

static void grey_the_vm_roots() {
	// Grey the value stack
	darkenValues(vm.stack, vm.stackTop - vm.stack);
	// Grey the globals
	// Grey the call frame stack
	if (vm.trace) {
		for (Trace *trace = vm.traces; trace <= vm.trace; trace++) {
			darken_in_place(&trace->closure);
		}
	}
	// Grey the known special cases.
	darkenValue(&vm.cons);
	darkenValue(&vm.nil);
	darkenValue(&vm.maybe_this);
	darkenValue(&vm.maybe_nope);
}


static void resetStack() {
	vm.stackTop = vm.stack;
	vm.trace = vm.traces-1;
}

void vm_init() {
	resetStack();
	string_table_init(&vm.strings, 64);
	vm.cons = vm.nil = vm.maybe_this = vm.maybe_nope = UNSET_VAL;
	gc_install_roots(grey_the_vm_roots);
	init_dispatch();
}

void vm_capture_preamble_specials() {  // ( globals -- globals )
	vm.cons = table_get_from_C("cons");
	vm.nil = table_get_from_C("nil");
	vm.maybe_this = table_get_from_C("this");
	vm.maybe_nope = table_get_from_C("nope");
	vm.less = table_get_from_C("less");
	vm.same = table_get_from_C("same");
	vm.more = table_get_from_C("more");
}

void vm_dispose() {
	dispose_dispatch();
	gc_forget_roots(grey_the_vm_roots);
}

static void displaySomeValues(Value *first, size_t count) {
	for (size_t index = 0; index < count; index++) {
		printf("[");
		printValue(first[index]);
		printf("] ");
	}
}

static void displayStack(Value *base) {
	printf(" %s         ", CLOSURE->function->name->text);
	displaySomeValues(vm.stack, (base - vm.stack));
	printf("--|BASE|-- ");
	displaySomeValues(base, (vm.stackTop - base));
	printf("-|TOP|- ( ");
	displaySomeValues(CLOSURE->captives, CLOSURE->function->nr_captures);
	printf(")\n");
}


__declspec(noreturn) static void runtimeError(byte *vpc, Value *base, const char *format, ...) {
	va_list args;
	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);
	fputs("\n", stderr);
	displayStack(base);
	Function *function = CLOSURE->function;
	size_t offset = vpc - function->chunk.code.at - 1;
	int line = findLine(&function->chunk, offset);
	vm_panic("a runtime error in line %d", line);
}

__declspec(noreturn) void vm_panic(const char *format, ...) {
	va_list args;
	va_start(args, format);
	fputs("\n\n\n-----------\n", stderr);
	for (Trace *frame = vm.traces; frame <= vm.trace; frame++) {
		fprintf(stderr, "in %s\n", frame->closure->function->name->text);
	}
	fputs("\n***\n ***\n  ***   ***   Died of ", stderr);
	vfprintf(stderr, format, args);
	fputs(".\n\n", stderr);
	exit(99);
}

static void capture_closure(Closure *closure, Value *base) {
	// Precondition: *closure points to a fresh Closure object with no captures.
	Function *fn = closure->function;
	int index = 0;
	if (fn->fn_type == TYPE_MEMOIZED) index++;
	for (; index < fn->nr_captures; index++) {
		Capture capture = fn->captures[index];
		Value *capture_base = capture.is_local ? base : CLOSURE->captives;
		closure->captives[index] = capture_base[capture.offset];
	}
	// Postcondition: Captures have been copied per directives in *closure's function.
}

static double knuth_mod(double numerator, double denominator) {
	double r = fmod(numerator, denominator);
	bool C_is_wrong = (numerator < 0) != (denominator < 0);
	return C_is_wrong ? r + denominator : r;
}

void perform() {
	while (!IS_UNSET(TOP)) {
		push(apply());
	}
	pop();
}

static int type_index_for_value(Value v) {
	// There are five interesting cases:
	// Enums, Runes, Numbers, Strings, and Records.
	// The last two types are up to the GC kind to work out.
	// See also install_builtin_vtables in assembler.c.
	switch (INDICATOR(v)) {
	case IND_ENUM: return AS_ENUM_VT_IDX(v);
	case IND_RUNE: return TX_RUNE;
	case IND_GC: return AS_GC(v)->kind->type_index(AS_GC(v));
	default: return TX_NUMBER;
	}
}

static void vm_double_resolve(BopType bop) {
	// Leaves the correct callable object at top-of-stack.
	VTable *vt = &vmap.at[type_index_for_value(SND)];
	DispatchTable *dt = &vt->dt[bop];
	push(find_dispatch(dt, type_index_for_value(TOP)));
	assert(IS_GC_ABLE(TOP));
}

static void vm_double_dispatch(BopType bop) {
	// Resolves the dispatch and performs the call.
	vm_double_resolve(bop);
	push(apply());
}

static Value compare_numbers(double lhs, double rhs) {
	if (lhs < rhs) return vm.less;
	if (lhs == rhs) return vm.same;
	if (lhs > rhs) return vm.more;
	// At this point, NaN is involved.
	// Arbitrarily put them all in an equivalence class above infinity.
	// This isn't what IEEE says, but it will probably be less astonishing most of the time.
	if (!isnan(lhs)) return vm.less;
	if (!isnan(rhs)) return vm.more;
	return vm.same;
}

static void vm_negate() {
	VTable *vt = &vmap.at[type_index_for_value(TOP)];
	push(vt->neg);
	assert(IS_GC_ABLE(TOP));
	push(apply());
}

#define NEXT goto dispatch
#define READ_BYTE() (*vpc++)
#define LEAP() do { vpc += word_at(vpc); } while (0)
#define SKIP_AND_POP() do { pop(); vpc += 2; } while(0)
#define YIELD(value) do { Value retval = (value); vm.stackTop = base; vm.trace--; return retval; } while (0)

static bool is_two_numbers() { return IS_NUMBER(SND) && IS_NUMBER(TOP); }

#define BIN_EXP(exp, bop) do { if (is_two_numbers()) merge(NUMBER_VAL(exp)); else vm_double_dispatch(bop); } while (0)
#define BIN_OP(op, bop) BIN_EXP(AS_NUMBER(SND) op AS_NUMBER(TOP), bop)

Value vm_run() {
	Closure *closure = AS_CLOSURE(pop());
	if (vm.trace == &vm.traces[FRAMES_MAX]) crashAndBurn("Max recursion depth exceeded.");
	vm.trace++;
	Value *base = vm.stackTop - closure->function->arity;
	Value *constants;
	byte *vpc;
enter:
	constants = closure->function->chunk.constants.at;
	vpc = closure->function->chunk.code.at;
	CLOSURE = closure;
	// At this point, closure becomes invalid because allocations can happen.

	assert(base >= vm.stack);  // If this fails, the script died of stack underflow.

	for (;;) {
dispatch:

#ifdef DEBUG_TRACE_EXECUTION
		printf("-----------------\n");
		displayStack(base);
		printf("%s > ", name_of_function(CLOSURE->function)->text);
		disassembleInstruction(&CLOSURE->function->chunk, (int)(vpc - CLOSURE->function->chunk.code.at));
#endif // DEBUG_TRACE_EXECUTION

		switch (READ_BYTE()) {
		case OP_PANIC:
			runtimeError(vpc, base, "PANIC instruction encountered.");
		case OP_GLOBAL:  // Fall-through to OP_CONSTANT
		case OP_CONSTANT: {
			int index = READ_BYTE();
			push(constants[index]);
			NEXT;
		}
		case OP_POP: pop(); NEXT;
		case OP_LOCAL: {
			int index = READ_BYTE();
			assert(base + index < vm.stackTop);  // Some day, let assembler.c discern max stack usage per function, and check only once.
			push(base[index]);
			NEXT;
		}

		case OP_CAPTIVE: push(CLOSURE->captives[READ_BYTE()]); NEXT;
		case OP_CLOSURE:
		{
			// Initialize a run of closures. The underlying function definitions are in the constant table.
			int constant_index = READ_BYTE();
			int nr_closures = READ_BYTE();
			Value *slot = vm.stackTop;
			memcpy(slot, constants+constant_index, sizeof(Value) * nr_closures);
			vm.stackTop += nr_closures;
			for (int index = 0; index < nr_closures; index++) close_function(&slot[index]);
			for (int index = 0; index < nr_closures; index++) capture_closure(AS_CLOSURE(slot[index]), base);
			NEXT;
		}
		case OP_THUNK: {
			push(constants[READ_BYTE()]);
			close_function(&TOP);
			capture_closure(AS_CLOSURE(TOP), base);
			NEXT;
		}
		case OP_NIL: push(vm.nil); NEXT;
		case OP_TRUE: push(BOOL_VAL(true)); NEXT;
		case OP_FALSE: push(BOOL_VAL(false)); NEXT;
		case OP_EQUAL:
			if (is_two_numbers()) merge(BOOL_VAL(AS_NUMBER(SND) == AS_NUMBER(TOP)));
			else {
				vm_double_dispatch(BOP_CMP);
				TOP = BOOL_VAL(TOP.bits == vm.same.bits);
			}
		NEXT;
		case OP_GREATER:
			if (is_two_numbers()) merge(BOOL_VAL(AS_NUMBER(SND) > AS_NUMBER(TOP)));
			else {
				vm_double_dispatch(BOP_CMP);
				TOP = BOOL_VAL(TOP.bits == vm.more.bits);
			}
		NEXT;
		case OP_LESS:
			if (is_two_numbers()) merge(BOOL_VAL(AS_NUMBER(SND) < AS_NUMBER(TOP)));
			else {
				vm_double_dispatch(BOP_CMP);
				TOP = BOOL_VAL(TOP.bits == vm.less.bits);
			}
		NEXT;
		case OP_CMP:
			if (is_two_numbers()) merge(compare_numbers(AS_NUMBER(SND), AS_NUMBER(TOP)));
			else vm_double_dispatch(BOP_CMP);
		NEXT;
		case OP_CMP_EXEC:
			if (is_two_numbers()) {
				YIELD(compare_numbers(AS_NUMBER(SND), AS_NUMBER(TOP)));
			}
			else {
				vm_double_resolve(BOP_CMP);
				goto do_exec;
			}
		case OP_POWER: BIN_EXP(pow(AS_NUMBER(SND), AS_NUMBER(TOP)), BOP_POW); NEXT;
		case OP_MULTIPLY: BIN_OP(*, BOP_MUL); NEXT;
		case OP_DIVIDE: BIN_OP(/, BOP_DIV); NEXT;
		case OP_INTDIV: BIN_EXP(floor(AS_NUMBER(SND) / AS_NUMBER(TOP)), BOP_IDIV); NEXT;
		case OP_MODULUS: BIN_EXP(knuth_mod(AS_NUMBER(SND), AS_NUMBER(TOP)), BOP_MOD); NEXT;
		case OP_ADD: BIN_OP(+, BOP_ADD); NEXT;
		case OP_SUBTRACT: BIN_OP(-, BOP_SUB); NEXT;
		case OP_NOT: TOP = BOOL_VAL(!AS_BOOL(TOP)); NEXT;
		case OP_NEGATE:
			if (IS_NUMBER(TOP)) TOP = NUMBER_VAL(-AS_NUMBER(TOP));
			else vm_negate();
			NEXT;
		case OP_CALL:
			switch (INDICATOR(TOP)) {
			case IND_GC:
			case IND_CLOSURE:
			case IND_NATIVE:
				push(apply());
				NEXT;
			default:
				printValue(TOP);
				runtimeError(vpc, base, "CALL needs a callable object; got %s.", valKind(TOP));
			}
		case OP_EXEC:
		do_exec:
			switch (INDICATOR(TOP)) {
			case IND_THUNK:
				if (DID_SNAP(TOP)) YIELD(SNAP_RESULT(AS_CLOSURE(TOP)));
				// Fall through to IND_CLOSURE:
			case IND_CLOSURE:
				closure = AS_CLOSURE(pop());
				assert(closure->header.kind == &KIND_Closure);
				int arity = closure->function->arity;
				memmove(base, vm.stackTop - arity, arity * sizeof(Value));
				vm.stackTop = base + arity;
				goto enter;
			case IND_GC:
			case IND_NATIVE:  // i.e. native function
				YIELD(apply());
			default:
				runtimeError(vpc, base, "EXEC needs a callable object; got val %s.", valKind(TOP));
			}
		case OP_FORCE_RETURN:
		{
			if (IS_THUNK(TOP)) {
				if (DID_SNAP(TOP)) {
					YIELD(SNAP_RESULT(AS_CLOSURE(TOP)));
				}
				else {
					// Treat this like an exec / tail-call, but easier since arity is zero by definition.
					closure = AS_CLOSURE(pop());
					vm.stackTop = base;
					goto enter;
				}
			}
			// else fall-through to OP_RETURN;
		}
		case OP_RETURN:
		{
			assert(! IS_THUNK(TOP));  // Return values are needed values! Don't thunk them.
			YIELD(TOP);
		}
		case OP_FORCE:
			TOP = force(TOP);
			assert(!IS_THUNK(TOP));
			NEXT;
		case OP_STRICT:
		{
			int index = READ_BYTE();
			base[index] = force(base[index]);
			NEXT;
		}
		case OP_JF:
			if (AS_BOOL(TOP)) SKIP_AND_POP();
			else LEAP();
			NEXT;
		case OP_JT:
			if (AS_BOOL(TOP)) LEAP();
			else SKIP_AND_POP();
			NEXT;
		case OP_JMP:
			LEAP();
			NEXT;
		case OP_CASE:
		{
			int tag;
			switch (INDICATOR(TOP)) {
			case IND_ENUM:
				tag = AS_ENUM_TAG(TOP);
				break;
			case IND_GC: {
				tag = AS_RECORD(TOP)->constructor->tag;
				break;
			}
			default:
				runtimeError(vpc, base, "Need a case-able object; got %s.", valKind(TOP));
			}
			vpc += 2 * tag;
			LEAP();
			NEXT;
		}
		case OP_FIELD:
		{
			assert(is_record(TOP));
			Record *record = AS_RECORD(TOP);
			Value field_offset = record->constructor->field_offset;
			int offset = AS_RUNE(tableGet(field_offset, AS_STRING(constants[READ_BYTE()])));
			TOP = record->fields[offset];
			NEXT;
		}
		case OP_SNOC:
			snoc();
			NEXT;
		case OP_BIND:
		{
			// ( actor -- bound_method )
			// Simple approach: Push the callable and then snap these into a bound message.
			push(constants[READ_BYTE()]);
			bind_method_by_name();
			NEXT;
		}
		case OP_TASK:
			bind_task_from_closure();
			NEXT;
		case OP_PERFORM:
			perform();
			NEXT;
		case OP_SKIP:
			push(UNSET_VAL);  // Something that will get treated as an empty action.
			NEXT;
		case OP_CAST:
			make_actor_from_template();
			NEXT;
		case OP_MEMBER:
		{
			assert(is_actor(*base));
			push(AS_ACTOR(*base)->fields[READ_BYTE()]);
			NEXT;
		}
		case OP_ASSIGN:
		{
			assert(is_actor(SND));
			Actor *actor = AS_ACTOR(SND);
			gc_mutate(&actor->fields[READ_BYTE()], TOP);
			vm.stackTop -= 2;
			NEXT;
		}
		case OP_DRAIN:
			drain_the_queue();
			NEXT;
		case OP_DISPLAY:
			printValueDeeply(TOP);
			fputc('\n', stdout);
			pop();
			NEXT;
		default:
			runtimeError(vpc, base, "Unrecognized instruction %d.", vpc[-1]);
		}
	}
}

#undef LEAP
#undef SKIP_AND_POP
#undef READ_BYTE
#undef NEXT

Value force(Value value) {
	if (IS_THUNK(value)) {
		if DID_SNAP(value) {
			assert(AS_CLOSURE(value)->header.kind == &KIND_Snapped);
			return SNAP_RESULT(AS_CLOSURE(value));
		}
		else {
			// Thunk has yet to be snapped.
			assert(AS_CLOSURE(value)->header.kind == &KIND_Closure);
			push(value);
			push(value);
			Value result = vm_run();
			assert(AS_CLOSURE(TOP)->header.kind == &KIND_Closure);
			gc_mutate(&SNAP_RESULT(AS_CLOSURE(TOP)), result);
			assert(AS_CLOSURE(TOP)->header.kind == &KIND_Closure);
			AS_CLOSURE(TOP)->header.kind = &KIND_Snapped;
			return SNAP_RESULT(AS_CLOSURE(pop()));
		}
	}
	else return value;
}

