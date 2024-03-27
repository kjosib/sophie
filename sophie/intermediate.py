"""
This is *still* a work in progress.

The concept here is to emit text which the VM can read as a (low-ish level) language.
This is mostly a tree-walk (beginning in class Translation, method visit_RoadMap)
but there is some cleverness to support tail-call elimination and the thunks that
implement lazy evaluation.

You can invoke this code on a Sophie program using the -x command-line flag to the main
Sophie interpreter. That still subjects your program to all normal syntax and type checks,
but if that passes, then you get corresponding VM intermediate code on standard output.
"""

from typing import Iterable, Optional, Sequence
from boozetools.support.foundation import Visitor
from . import syntax, ontology, primitive
from .resolution import RoadMap

class TooComplicated(Exception):
	pass

OPERATOR_DIRECTIVE = {
	("-", 1): ".neg",
	("+", 2): ".add",
	("-", 2): ".sub",
	("*", 2): ".mul",
	("/", 2): ".div",
	("^", 2): ".pow",
	("DIV", 2): ".idiv",
	("MOD", 2): ".mod",
	("<=>", 2): ".cmp",
}

BINARY_INSTRUCTION = {
	# glyph : (opcode, stack-effect)
	'^': ("POW", -1),
	'*': ("MUL", -1),
	'/': ("DIV", -1),
	'DIV': ("IDIV", -1),
	'MOD': ("MOD", -1),
	'+': ("ADD", -1),
	'-': ("SUB", -1),
	'==': ("EQ", -1),
	'!=': ("EQ NOT", -1),
	'<': ("LT", -1),
	'<=': ("GT NOT", -1),
	'>': ("GT", -1),
	'>=': ("LT NOT", -1),
	'<=>': ("CMP", -1),
	True: ("TRUE", 1),
	False: ("FALSE", 1),
}
UNARY_INSTRUCTION = {
	"-": "NEG",
	"NOT": "NOT",
}

SHORTCUTS = {
	"AND" : False,
	"OR" : True,
}

def emit(*xs):
	print(*xs, end=" ")
def newline(indent=""):
	print("\n", end=indent)
def quote(x):
	assert isinstance(x, str), x
	assert '"' not in x
	return '"'+x+'"'

LABEL_QUEUE = list(reversed(range(4096)))
LABEL_MAP = {}

MANGLED = {}
def _mangle_name(prefix:str, symbol:ontology.Symbol):
	assert symbol not in MANGLED
	MANGLED[symbol] = prefix + symbol.nom.key()

def _mangle_user_operator(op: syntax.UserOperator):
	assert op not in MANGLED
	MANGLED[op] = op.nom.key() + '|'.join(MANGLED[t] for t in op.dispatch_vector())

class VMScope:
	""" Corresponds roughly to the Scope and/or Function structures in the VM. """
	
	indent = ""
	_prefix:str
	
	def __init__(self, prefix:str):
		self._prefix = prefix
	
	def nl(self): newline(self.indent)

	def capture(self, symbol: ontology.Symbol) -> bool:
		raise NotImplementedError(type(self))

	def emit_captured(self, captives: list[Optional[ontology.Symbol]]):
		raise NotImplementedError(type(self))

	def member_number(self, field:str):
		raise NotImplementedError(type(self))
	
	def mangle_names(self, syms:Iterable[ontology.Symbol]):
		for symbol in syms:
			if isinstance(symbol, syntax.UserOperator): _mangle_user_operator(symbol)
			else: _mangle_name(self._prefix, symbol)

	def declare(self, symbol: ontology.Symbol):
		raise NotImplementedError(type(self))
	
	def declare_several(self, symbols: Iterable[ontology.Symbol]):
		for sym in symbols:
			self.declare(sym)

	def write_one_function(self, fn: syntax.UserFunction):
		inner = VMFunctionScope(self, fn.nom.text, is_thunk=not fn.params)
		inner.emit_preamble(fn.params, MANGLED[fn])
		for param in fn.params:
			if param.is_strict:
				inner.make_strict(param)
		inner.write_inner_functions(fn.where)
		TAIL.visit(fn.expr, inner)
		inner.emit_epilogue()

class VMGlobalScope(VMScope):
	""" Mainly a null-object that encloses a nest of scopes without itself being enclosed. """
	
	def capture(self, symbol: ontology.Symbol) -> bool:
		return False

	def emit_captured(self, captives: list[ontology.Symbol]):
		for sym in captives:
			assert sym is None
			emit("*")

	def write_begin_expressions(self, module: syntax.Module):
		inner = VMFunctionScope(self, "[BEGIN]", is_thunk=True)
		for index, expr in enumerate(module.main):
			inner.nl()
			FORCE.visit(expr, inner)
			inner.display()
	
	def write_outer_functions(self, fns:list[syntax.UserFunction]):
		self.mangle_names(fns)
		for fn in fns:
			self.nl()
			if isinstance(fn, syntax.UserOperator):
				emit(OPERATOR_DIRECTIVE[fn.nom.key(), len(fn.params)])
				for token in fn.dispatch_vector():
					emit(quote(MANGLED[token]))
			else:
				emit(".fn")
			self.write_one_function(fn)
	
	def declare(self, symbol: ontology.Symbol):
		pass
	
	def write_actors(self, agent_definitions:list[syntax.UserAgent]):
		for dfn in agent_definitions:
			last = dfn.behaviors[-1]
			inner = VMActorScope(self, dfn)
			for b in dfn.behaviors:
				inner.write_one_behavior(b)
				emit(".end" if b is last else ";")
			self.nl()
		pass

class VMActorScope(VMScope):
	""" Specialized scope for the behaviors of an actor-definition """
	def __init__(self, outer:VMScope, dfn:syntax.UserAgent):
		super().__init__(outer._prefix + dfn.nom.text + ":")
		self._outer = outer
		self.indent = outer.indent+"  "
		emit(".actor", *dfn.field_names(), quote(MANGLED[dfn]))
		self._field_map = {field:i for i,field in enumerate(dfn.field_names())}

	def capture(self, symbol: ontology.Symbol) -> bool:
		return False

	def emit_captured(self, captives: list[ontology.Symbol]):
		assert not captives
	
	def member_number(self, field: str):
		return self._field_map[field]

	def write_one_behavior(self, b:syntax.Behavior):
		# The way this works is similar to a function.
		# However, there's a special "self" object implicitly the first parameter.
		# Also, access to self-dot-foo will use actor-specific instructions.
		inner = VMFunctionScope(self, b.nom.text, is_thunk=False)
		inner.emit_preamble([ontology.SELF] + b.params, b.nom.text)
		LAST.visit(b.expr, inner)
		inner.emit_epilogue()

class VMFunctionScope(VMScope):
	""" Encapsulates VM mechanics around the stack, parameters, closure capture, jumps, etc. """
	
	_captives : dict[Optional[ontology.Symbol], int]
	
	def __init__(self, outer:VMScope, infix:str, is_thunk:bool):
		super().__init__(outer._prefix + infix + ":")
		self._outer = outer
		self.indent = outer.indent+"  "
		self._thunk_count = 0
		self._local = {}
		self._children = []
		self._captives = {}
		self._depth = 0
		if is_thunk:
			# In position zero...
			self._captives[None] = 0
	
	def depth(self): return self._depth
	def _pop(self):
		self._depth -= 1
	def _push(self):
		self._depth += 1

	def declare(self, symbol: ontology.Symbol):
		self.alias(symbol)
		self._push()
	
	def alias(self, symbol: ontology.Symbol):
		"""
		Establishes where in the call-frame to look for a symbol.
		Call this just before pushing that symbol's value on the stack.
		
		It may seem odd to have the symbol's frame offset known before its value has been constructed.
		That's not a problem: The resolver has already validated all references to all symbols.
		"""
		assert symbol not in self._local
		self._local[symbol] = self._depth
		
	def enter_gensym(self):
		self._push()
		name = _gensym()
		inner = VMFunctionScope(self, name, is_thunk=False)
		inner.nl()
		emit("{", 0, quote(name))
		return inner

	def load(self, symbol: ontology.Symbol):
		if symbol in self._local:
			frame_offset = self._local[symbol]
			assert frame_offset < self._depth
			emit("LOCAL", frame_offset)
		elif self.capture(symbol):
			emit("CAPTIVE", self._captives[symbol])
		else:
			emit("GLOBAL", quote(MANGLED[symbol]))
		self._push()

	def constant(self, value):
		if isinstance(value, bool):
			self.emit_ALU(value)
		else:
			emit("CONST")
			if isinstance(value, str):
				emit(quote(value))
			elif isinstance(value, (int, float)):
				emit(value)
			else:
				assert False
		self._push()

	def capture(self, symbol: ontology.Symbol) -> bool:
		if symbol in self._local or symbol in self._captives:
			return True
		elif self._outer.capture(symbol):
			self._captives[symbol] = len(self._captives)
			return True
		
	def jump_if(self, when:bool):
		emit("JT" if when else "JF")
		label = self.emit_hole()
		self._pop()
		return label
		
	def jump_always(self):
		emit("JMP")
		label = self.emit_hole()
		self._depth = None
		return label
	
	def cases(self, nr_cases) -> list:
		emit("CASE")
		return [self.emit_hole() for _ in range(nr_cases)]
	
	def emit_hole(self):
		assert self._depth is not None
		label = LABEL_QUEUE.pop()
		emit("hole", label)
		LABEL_MAP[label] = (self, self._depth)
		return label
	
	def come_from(self, label):
		if label is None: return
		emit("come_from", label)
		(source, depth) = LABEL_MAP.pop(label)
		assert source is self, "Improper Come-From"
		if self._depth is None:
			self._depth = depth
		else:
			assert self._depth == depth, "Inconsistent Come-From %d != %d"%(self._depth, depth)
		LABEL_QUEUE.append(label)

	def emit_preamble(self, params:Sequence[syntax.FormalParameter], name:str):
		emit(len(params))
		emit(quote(name))
		self.declare_several(params)

	def make_strict(self, param):
		emit("STRICT", self._local[param])
	
	def emit_epilogue(self):
		# Consists of right brace, maximum number of locally-used stack slots,
		# number of captures, and information about each capture.
		if len(self._captives) > 255: raise TooComplicated("More than 255 captures in one function")

		emit("|", len(self._captives))
		self._outer.emit_captured(list(self._captives)) # Preserving insertion order
		
	def emit_captured(self, captives: list[ontology.Symbol]):
		for sym in captives:
			if sym in self._local:
				emit("L", self._local[sym])
			elif sym is None:
				emit("*")
			else:
				emit(self._captives[sym])
	
	def display(self):
		assert self._depth == 1, self.depth()
		emit("DISPLAY")
		self._pop()
	
	def ascend_to(self, depth:int):
		assert self._depth >= depth
		if self._depth > depth:
			emit("ASCEND", self._depth - depth)
			self._depth = depth
	
	def emit_call(self, arity):
		emit("CALL")
		self._depth -= arity
	
	def emit_pop(self):
		emit("POP")
		self._pop()
	
	def emit_drop(self, how_many:int):
		assert how_many >= 0
		if self._depth is not None:
			if how_many == 1:
				self.emit_pop()
			elif how_many > 1:
				emit("DROP", how_many)
				self._depth -= how_many

	def emit_perform(self):
		emit("PERFORM")
		self._pop()

	def emit_skip(self):
		emit("SKIP")
		self._push()

	def emit_return(self):
		emit("RETURN")
		self._depth = None

	def emit_force_return(self):
		emit("FORCE_RETURN")
		self._depth = None

	def emit_exec(self):
		emit("EXEC")
		self._depth = None

	def emit_perform_exec(self):
		emit("PERFORM_EXEC")
		self._depth = None

	def emit_nil(self):
		emit("NIL")
		self._push()
	
	def emit_snoc(self):
		emit("SNOC")
		self._pop()
	
	def emit_panic(self):
		emit("PANIC")
		self._depth = None

	@staticmethod
	def emit_read_field(key):
		emit("FIELD", quote(key))
	
	def emit_ALU(self, glyph):
		opcode, stack_effect = BINARY_INSTRUCTION[glyph]
		emit(opcode)
		self._depth += stack_effect
	
	def make_thunk(self, expr):
		# Implicitly makes a THUNK instruction in the containing function.
		self._thunk_count += 1
		emit("[")
		inner = VMFunctionScope(self, str(self._thunk_count) + "_", is_thunk=True)
		TAIL.visit(expr, inner)
		inner.emit_epilogue()
		emit("]")
		self._push()
	
	def emit_assign_member(self, field: str):
		emit("ASSIGN", self.member_number(field))
		self._depth -= 2

	def emit_read_member(self, field: str):
		emit("MEMBER", self.member_number(field))
		
	def member_number(self, field: str):
		return self._outer.member_number(field)

	def write_inner_functions(self, fns):
		if not fns: return
		self.mangle_names(fns)
		self.declare_several(fns)
		emit("{")
		self.nl()
		last = fns[-1]
		for fn in fns:
			self.write_one_function(fn)
			emit("}" if fn is last else ";")
			self.nl()

_do_count = 0
def _gensym():
	global _do_count
	_do_count += 1
	return "do:"+str(_do_count)

def write_vtable(symbol):
	emit(".vtable")
	emit(quote(MANGLED[symbol]))
	newline()


def write_record(names:Iterable[str], symbol:ontology.Symbol):
	emit(".data")
	for name in names:
		emit(name)
	emit(quote(MANGLED[symbol]))
	emit(".end")
	newline()

def write_enum(symbol:ontology.Symbol):
	write_record((), symbol)

def write_tagged_value(symbol:ontology.Symbol):
	write_record(["*"], symbol)

def symbol_harbors_thunks(sym:ontology.Symbol):
	if isinstance(sym, syntax.FormalParameter): return not sym.is_strict
	if isinstance(sym, syntax.UserFunction) and not sym.params: return True

def handles_tails(expr: syntax.Expr):
	return isinstance(expr, (syntax.Call, syntax.ShortCutExp, syntax.Cond, syntax.MatchExpr))

def is_eager(expr: syntax.ValExpr):
	"""Basically, loads that are guaranteed not to be a thunk. So match-subjects mainly..."""
	if isinstance(expr, syntax.Lookup):
		return not symbol_harbors_thunks(expr.ref.dfn)

def each_piece(roadmap:RoadMap):
	yield VMGlobalScope(""), roadmap.preamble
	for index, module in enumerate(roadmap.each_module):
		yield VMGlobalScope(str(index+1) + ":"), module

TYPE_CASE_INDEX = {}

class Context(Visitor):
	"""
	The best way to compile something can depend on context.
	Rather than pass a ton of flags around,
	it's polymorphism to the rescue!

	(This may merit reconsideration for a pure-functional approach.)
	"""
	
	def call(self, scope: VMFunctionScope, arity:int):
		""" Called at the end of a call. """
		raise NotImplementedError(type(self))

	@staticmethod
	def visit_Absurdity(_: syntax.Absurdity, scope: VMFunctionScope):
		scope.emit_panic()

class LazyContext(Context):
	@staticmethod
	def visit_FieldReference(fr: syntax.FieldReference, scope: VMFunctionScope):
		if fr.is_volatile or is_eager(fr.lhs): FORCE.visit(fr, scope)
		else: scope.make_thunk(fr)
	
	@staticmethod
	def _thunk_it(expr:syntax.ValExpr, scope: VMFunctionScope):
		if expr.is_volatile: FORCE.visit(expr, scope)
		scope.make_thunk(expr)
	
	visit_Call = _thunk_it
	visit_BinExp = _thunk_it
	visit_UnaryExp = _thunk_it
	visit_ShortCutExp = _thunk_it
	visit_Cond = _thunk_it
	visit_MatchExpr = _thunk_it
	visit_AsTask = _thunk_it
	visit_BindMethod = _thunk_it
	
	@staticmethod
	def visit_Lookup(expr:syntax.Lookup, scope:VMFunctionScope):
		# This often turns out to be a thunk that must not be forced right away.
		sym = expr.ref.dfn
		scope.load(sym)

	@staticmethod
	def _force_it(expr:syntax.ValExpr, scope: VMFunctionScope):
		FORCE.visit(expr, scope)
	
	visit_Literal = _force_it
	visit_LambdaForm = _force_it
	visit_ExplicitList = _force_it

def _delay(expr:syntax.ValExpr, scope: VMFunctionScope):
	strict = expr.is_volatile  # There could be more reasons later, e.g. stricture analysis
	(FORCE if strict else DELAY).visit(expr, scope)

def _prepare_arguments_for_call(call: syntax.Call, scope: VMFunctionScope):
	# If the thing we're calling is syntactically:
	#     a function by name, then find and respect its strictness declarations.
	#     a bound method, then evaluate all arguments eagerly.
	#     anything else, then delay everything and rely on the calling convention.
	# There's probably a way to break this out into a pass of its own, but meh.
	
	if isinstance(call.fn_exp, syntax.Lookup):
		sym = call.fn_exp.ref.dfn
		if isinstance(sym, syntax.UserFunction):
			for param, arg in zip(sym.params, call.args):
				if param.is_strict:
					FORCE.visit(arg, scope)
				else:
					_delay(arg, scope)
			return
	if isinstance(call.fn_exp, syntax.BindMethod):
		for arg in call.args: FORCE.visit(arg, scope)
		return
	for arg in call.args: _delay(arg, scope)

class EagerContext(Context):
	"""
	The best way to compile something can depend on context.
	Rather than pass a ton of flags around,
	it's polymorphism to the rescue!
	
	(This may merit reconsideration for a pure-functional approach.)
	"""
	def visit_Call(self, call: syntax.Call, scope: VMFunctionScope):
		_prepare_arguments_for_call(call, scope)
		FORCE.visit(call.fn_exp, scope)
		self.call(scope, len(call.args))
	
	def visit_MatchExpr(self, mx:syntax.MatchExpr, scope:VMFunctionScope):
		scope.alias(mx.subject)
		FORCE.visit(mx.subject.expr, scope)
		depth = scope.depth()
		nr_cases = len(mx.variant.subtypes)
		cases = scope.cases(nr_cases)
		after = []
		for alt in mx.alternatives:
			tag = TYPE_CASE_INDEX[alt.dfn]
			scope.come_from(cases[tag])
			cases[tag] = None
			scope.write_inner_functions(alt.where)
			self.visit(alt.sub_expr, scope)
			after.append(self.sequel(scope, depth, True))
		if mx.otherwise is not None:
			for tag, label in enumerate(cases):
				if label is not None:
					scope.come_from(label)
			self.visit(mx.otherwise, scope)
			self.sequel(scope, depth, False)
		for label in after:
			scope.come_from(label)
		pass
	
	@staticmethod
	def sequel(scope:VMFunctionScope, depth:int, more:bool):
		""" Called at the end of a consequence. """
		raise NotImplementedError()

	def visit_UnaryExp(self, ux:syntax.UnaryExp, scope:VMFunctionScope):
		FORCE.visit(ux.arg, scope)
		emit(UNARY_INSTRUCTION[ux.op.text])  # No change to stack depth
		self.answer(scope)

	def visit_ShortCutExp(self, it: syntax.ShortCutExp, scope: VMFunctionScope):
		FORCE.visit(it.lhs, scope)
		satisfied = SHORTCUTS[it.op.text]
		label = scope.jump_if(satisfied)
		self.visit(it.rhs, scope)
		scope.come_from(label)
		self.answer(scope)
		
	@staticmethod
	def answer(scope: VMFunctionScope):
		""" Answer is on stack; now what? """
		raise NotImplementedError()
	
	def visit_Literal(self, expr: syntax.Literal, scope: VMFunctionScope):
		scope.constant(expr.value)
		self.answer(scope)
	
	@staticmethod
	def visit_LambdaForm(lf:syntax.LambdaForm, scope: VMFunctionScope):
		# Two steps:
		# 1. Emit the function.
		scope.mangle_names([lf.function])
		scope.declare(lf.function)
		emit("{")
		scope.write_one_function(lf.function)
		emit("}")
		# 2. Emit the code to load that function onto the stack.
		scope.load(lf.function)
		
	def visit_FieldReference(self, fr: syntax.FieldReference, scope: VMFunctionScope):
		FORCE.visit(fr.lhs, scope)
		if syntax.is_self_reference(fr.lhs):
			scope.emit_read_member(fr.field_name.key())
		else:
			scope.emit_read_field(fr.field_name.key())
			emit("FORCE")
		self.answer(scope)
	
	def visit_ExplicitList(self, el:syntax.ExplicitList, scope:VMFunctionScope):
		scope.emit_nil()
		for item in reversed(el.elts):
			_delay(item, scope)
			scope.emit_snoc()
		self.answer(scope)
	
	def visit_BindMethod(self, expr:syntax.BindMethod, scope:VMFunctionScope):
		FORCE.visit(expr.receiver, scope)
		emit("BIND", quote(expr.method_name.key()))
		self.answer(scope)


class FunctionContext(EagerContext):

	def visit_DoBlock(self, do:syntax.DoBlock, outer:VMFunctionScope):
		inner = outer.enter_gensym()
		LAST.visit(do, inner)
		inner.emit_epilogue()
		emit("}")
		self.answer(outer)
	
	def visit_AsTask(self, task:syntax.AsTask, scope:VMFunctionScope):
		FORCE.visit(task.sub, scope)
		emit("TASK")
		self.answer(scope)
	
	def visit_Skip(self, _:syntax.Skip, scope:VMFunctionScope):
		scope.emit_skip()
		self.answer(scope)

		
class ForceContext(FunctionContext):
	@staticmethod
	def visit_Lookup(expr:syntax.Lookup, scope:VMFunctionScope):
		sym = expr.ref.dfn
		scope.load(sym)
		if symbol_harbors_thunks(sym):
			emit("FORCE")
	
	def call(self, scope: VMFunctionScope, arity:int):
		scope.emit_call(arity)
	
	@staticmethod
	def sequel(scope:VMFunctionScope, depth:int, more:bool):
		scope.ascend_to(depth)
		if more:
			return scope.jump_always()
	
	@staticmethod
	def visit_BinExp(it: syntax.BinExp, scope:VMFunctionScope):
		FORCE.visit(it.lhs, scope)
		FORCE.visit(it.rhs, scope)
		scope.emit_ALU(it.op.text)

	@staticmethod
	def answer(scope: VMFunctionScope):
		""" Just leave the answer on the stack. """
		pass

	@staticmethod
	def visit_Cond(cond:syntax.Cond, scope:VMFunctionScope):
		FORCE.visit(cond.if_part, scope)
		label_else = scope.jump_if(False)
		FORCE.visit(cond.then_part, scope)
		after = scope.jump_always()
		scope.come_from(label_else)
		scope.emit_pop()
		FORCE.visit(cond.else_part, scope)
		scope.come_from(after)

class TailContext(FunctionContext):
	@staticmethod
	def visit_Lookup(expr:syntax.Lookup, scope:VMFunctionScope):
		sym = expr.ref.dfn
		scope.load(sym)
		if symbol_harbors_thunks(sym):
			scope.emit_force_return()
		else:
			scope.emit_return()
	
	def call(self, scope: VMFunctionScope, arity:int):
		scope.emit_exec()
	
	@staticmethod
	def sequel(scope:VMFunctionScope, depth:int, more:bool):
		pass
	
	@staticmethod
	def visit_BinExp(it: syntax.BinExp, scope:VMFunctionScope):
		FORCE.visit(it.lhs, scope)
		FORCE.visit(it.rhs, scope)
		if it.op.text == "<=>":
			emit("TAIL_CMP")
		else:
			scope.emit_ALU(it.op.text)
			scope.emit_return()

	@staticmethod
	def answer(scope:VMFunctionScope):
		""" Have answer on stack; time to return it. """
		scope.emit_return()

	@staticmethod
	def visit_Cond(cond:syntax.Cond, scope:VMFunctionScope):
		FORCE.visit(cond.if_part, scope)
		label_else = scope.jump_if(False)
		TAIL.visit(cond.then_part, scope)
		scope.come_from(label_else)
		TAIL.visit(cond.else_part, scope)


class ProcContext(EagerContext):
	
	def call(self, scope: VMFunctionScope, arity:int):
		scope.emit_call(arity)
		self.perform(scope)

	def perform(self, scope: VMFunctionScope):
		raise NotImplementedError(type(self))

	def semicolon(self, scope: VMFunctionScope):
		raise NotImplementedError(type(self))

	def visit_DoBlock(self, do: syntax.DoBlock, scope: VMFunctionScope):
		for agent in do.agents:
			scope.alias(agent)
			FORCE.visit(agent.expr, scope)
			# At this point a template is on the stack.
			emit("CAST")
		
		depth = scope.depth()
		for step in do.steps[:-1]:
			STEP.visit(step, scope)
			assert scope.depth() == depth
		self.visit(do.steps[-1], scope)
		assert scope.depth() in (depth, None)
		scope.emit_drop(len(do.agents))

	def visit_AssignField(self, af:syntax.AssignField, scope:VMFunctionScope):
		scope.load(ontology.SELF)
		FORCE.visit(af.expr, scope)
		scope.emit_assign_member(af.nom.text)
		self.semicolon(scope)
	
	def visit_Skip(self, _:syntax.Skip, scope:VMFunctionScope):
		self.semicolon(scope)
	
class StepContext(ProcContext):
	def perform(self, scope: VMFunctionScope):
		scope.emit_perform()

	def semicolon(self, scope: VMFunctionScope):
		pass


class LastContext(ProcContext):
	""" The procedural context just before return-to-caller """
	def perform(self, scope: VMFunctionScope):
		scope.emit_perform_exec()
		
	def semicolon(self, scope: VMFunctionScope):
		scope.emit_return()

	@staticmethod
	def visit_Cond(cond:syntax.Cond, scope:VMFunctionScope):
		FORCE.visit(cond.if_part, scope)
		label_else = scope.jump_if(False)
		LAST.visit(cond.then_part, scope)
		scope.come_from(label_else)
		LAST.visit(cond.else_part, scope)


DELAY = LazyContext()
FORCE = ForceContext()
TAIL = TailContext()
STEP = StepContext()
LAST = LastContext()

def mangle_foreign_symbols(foreign:list[syntax.ImportForeign]):
	for fi in foreign:
		for group in fi.groups:
			for symbol in group.symbols:
				MANGLED[symbol] = symbol.nom.text
	pass

def write_ffi_init(foreign: list[syntax.ImportForeign]):
	for fi in foreign:
		if fi.linkage is not None:
			emit(".ffi")
			emit(quote(fi.source.value))
			for ref in fi.linkage:
				emit(quote(MANGLED[ref.dfn]))
			emit(";")


class StructureDefiner(Visitor):
	""" Just defines data structures. """
	
	def write_types(self, types, scope:VMGlobalScope):
		for t in types:
			self.visit(t, scope)

	def visit_TypeAlias(self, t, scope:VMGlobalScope): pass
	def visit_Interface(self, t, scope:VMGlobalScope): pass
	
	@staticmethod
	def visit_Record(r:syntax.Record, scope:VMGlobalScope):
		scope.mangle_names([r])
		write_vtable(r)
		write_record(r.spec.field_names(), r)
		
	@staticmethod
	def visit_Variant(variant:syntax.Variant, scope:VMGlobalScope):
		scope.mangle_names([variant])
		write_vtable(variant)
		scope.mangle_names(variant.subtypes)
		for tag, st in enumerate(variant.subtypes):
			TYPE_CASE_INDEX[st] = tag
			if isinstance(st.body, syntax.RecordSpec):
				write_record(st.body.field_names(), st)
			elif st.body is None:
				write_enum(st)
			else:
				write_tagged_value(st)

STRUCTURE = StructureDefiner()

def translate(roadmap:RoadMap):
	# Mangle the built-in types
	for name, symbol in primitive.root_namespace.local.items():
		MANGLED[symbol] = name
	
	# Write all types:
	for scope, module in each_piece(roadmap):
		STRUCTURE.write_types(module.types, scope)
		scope.mangle_names(module.agent_definitions)
		mangle_foreign_symbols(module.foreign)

	# Write all functions (including FFI):
	for scope, module in each_piece(roadmap):
		scope.write_outer_functions(module.outer_functions)
		scope.write_actors(module.agent_definitions)
		write_ffi_init(module.foreign)
	
	# Delimiter so it's possible to start a begin-expression with a do-block:
	emit(".begin")

	# Write all begin-expressions:
	for scope, module in each_piece(roadmap):
		scope.write_begin_expressions(module)
	
	# All done:
	TYPE_CASE_INDEX.clear()
	MANGLED.clear()


