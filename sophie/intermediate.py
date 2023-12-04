"""
This is still a work in progress. 

The concept here is to emit text which the VM can read as a (low-ish level) language.
This is mostly a tree-walk (beginning in class Translation, method visit_RoadMap)
but there is some cleverness to support tail-call elimination and the thunks that
implement lazy evaluation.

You can invoke this code on a Sophie program using the -x command-line flag to the main
Sophie interpreter. That still subjects your program to all normal syntax and type checks,
but if it passes, then emit corresponding heaps of VM code on standard output.

Major current holes:

1. No support for module name-spacing yet.
2. No support for actor-model stuff yet.

"""

from typing import Iterable, Optional
from boozetools.support.foundation import Visitor
from . import syntax, ontology
from .resolution import RoadMap

class TooComplicated(Exception):
	pass

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
def quote(x):
	assert isinstance(x, str), x
	assert '"' not in x
	return '"'+x+'"'

LABEL_QUEUE = list(reversed(range(4096)))
LABEL_MAP = {}

MANGLED = {}

class VMScope:
	""" Corresponds roughly to the Scope and/or Function structures in the VM. """
	
	indent = ""
	_prefix:str
	
	def __init__(self, prefix:str):
		self._prefix = prefix
	
	def nl(self):
		print()
		print("", end=self.indent)

	def capture(self, symbol: ontology.Symbol) -> bool:
		raise NotImplementedError(type(self))

	def emit_captured(self, captives: list[Optional[ontology.Symbol]]):
		raise NotImplementedError(type(self))

	def declare(self, symbol: ontology.Symbol):
		MANGLED[symbol] = self._prefix + symbol.nom.text

class VMGlobalScope(VMScope):
	""" Mainly a null-object that encloses a nest of scopes without itself being enclosed. """
	
	def capture(self, symbol: ontology.Symbol) -> bool:
		return False

	def emit_captured(self, captives: list[ontology.Symbol]):
		for sym in captives:
			assert sym is None
			emit("*")

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
		super().declare(symbol)
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
		emit("come_from", label)
		(source, depth) = LABEL_MAP.pop(label)
		assert source is self, "Improper Come-From"
		if self._depth is None:
			self._depth = depth
		else:
			assert self._depth == depth, "Inconsistent Come-From %d != %d"%(self._depth, depth)
		LABEL_QUEUE.append(label)

	def emit_preamble(self, fn:syntax.UserFunction):
		emit(len(fn.params))
		emit(quote(MANGLED[fn]))
		for param in fn.params:
			self.declare(param)

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
	
	def emit_call(self, tail, arity):
		if tail:
			self.emit_exec()
		else:
			emit("CALL")
			self._depth -= arity
	
	def emit_pop(self):
		emit("POP")
		self._pop()

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
	def emit_field(key):
		emit("FIELD", quote(key))
	
	def emit_ALU(self, glyph):
		opcode, stack_effect = BINARY_INSTRUCTION[glyph]
		emit(opcode)
		self._depth += stack_effect
	
	def make_thunk(self, xlat, expr):
		# Implicitly makes a THUNK instruction in the containing function.
		self._thunk_count += 1
		emit("[")
		inner = VMFunctionScope(self, str(self._thunk_count) + "_", is_thunk=True)
		xlat.tail_call(expr, inner)
		inner.emit_epilogue()
		emit("]")
		self._push()

def write_record(names:Iterable[str], symbol:ontology.Symbol, tag:int):
	emit("(")
	for name in names:
		emit(name)
	close_structure(symbol, tag)

def write_enum(symbol:ontology.Symbol, tag:int):
	write_record((), symbol, tag)

def write_tagged_value(symbol:ontology.Symbol, tag:int):
	emit("(", "*")
	close_structure(symbol, tag)

def close_structure(symbol:ontology.Symbol, tag:int):
	emit(tag)
	emit(quote(MANGLED[symbol]))
	emit(")")
	print()

def symbol_harbors_thunks(sym:ontology.Symbol):
	if isinstance(sym, syntax.FormalParameter): return True
	if isinstance(sym, syntax.UserFunction) and not sym.params: return True

def handles_tails(expr: syntax.Expr):
	return isinstance(expr, (syntax.Call, syntax.ShortCutExp, syntax.Cond, syntax.MatchExpr))

def is_eager(expr: syntax.Expr):
	"""Basically, loads that are guaranteed not to be a thunk. So match-subjects mainly..."""
	if isinstance(expr, syntax.Lookup):
		return not symbol_harbors_thunks(expr.ref.dfn)

def each_piece(roadmap:RoadMap):
	yield VMGlobalScope(""), roadmap.preamble
	for index, module in enumerate(roadmap.each_module):
		yield VMGlobalScope(str(index+1) + ":"), module

class Translation(Visitor):
	def __init__(self):
		self._tag_map = {}  # For compiling type-cases.  
	
	def visit_RoadMap(self, roadmap:RoadMap):
		# Write all types:
		for scope, module in each_piece(roadmap):
			self.write_records(module.types, scope)
		
		# Write all functions (including FFI):
		for scope, module in each_piece(roadmap):
			self.mangle_foreign_symbols(module.foreign)
			self.write_functions(module.outer_functions, scope)
			self.write_ffi_init(module.foreign)
		
		# Write all begin-expressions:
		for scope, module in each_piece(roadmap):
			inner = VMFunctionScope(scope, "[BEGIN]", is_thunk=True)
			self.visit_Module(module, inner)
	
	def visit_Module(self, module:syntax.Module, scope:VMFunctionScope):
		for index, expr in enumerate(module.main):
			self.write_begin_expression(expr, scope)

	def write_records(self, types, scope:VMGlobalScope):
		for t in types:
			self.visit(t, scope)

	def visit_TypeAlias(self, t, scope:VMGlobalScope): pass
	def visit_Interface(self, t, scope:VMGlobalScope): pass
	
	@staticmethod
	def visit_Record(r:syntax.Record, scope:VMGlobalScope):
		scope.declare(r)
		write_record(r.spec.field_names(), r, 0)
		
	def visit_Variant(self, variant:syntax.Variant, scope:VMGlobalScope):
		for tag, st in enumerate(variant.subtypes):
			scope.declare(st)
			self._tag_map[variant, st.nom.key()] = tag
			if isinstance(st.body, syntax.RecordSpec):
				write_record(st.body.field_names(), st, tag)
			elif st.body is None:
				write_enum(st, tag)
			else:
				write_tagged_value(st, tag)

	@staticmethod
	def mangle_foreign_symbols(foreign:list[syntax.ImportForeign]):
		for fi in foreign:
			for group in fi.groups:
				for symbol in group.symbols:
					MANGLED[symbol] = symbol.nom.text
		pass
	
	@staticmethod
	def write_ffi_init(foreign:list[syntax.ImportForeign]):
		for fi in foreign:
			if fi.linkage is not None:
				emit("!")
				emit(quote(fi.source.value))
				for ref in fi.linkage:
					emit(quote(MANGLED[ref.dfn]))
				emit(";")
	
	def write_functions(self, fns, outer:VMScope):
		if not fns: return
		for fn in fns:
			outer.declare(fn)
		emit("{")
		last = fns[-1]
		for fn in fns:
			self.write_one_function(fn, outer)
			emit("}" if fn is last else ";")
		outer.nl()

	def write_one_function(self, fn:syntax.UserFunction, outer:VMScope):
		inner = VMFunctionScope(outer, fn.nom.text, is_thunk=not fn.params)
		inner.nl()
		inner.emit_preamble(fn)
		self.write_functions(fn.where, inner)
		self.tail_call(fn.expr, inner)
		inner.emit_epilogue()
	
	def delay(self, expr:syntax.Expr, scope:VMFunctionScope):
		"""
		Similar policy (for now) to the version in the simple evaluator:
		Literals and references/look-ups do not get thunked.
		However, the latter may already refer to a thunk in certain cases.
		"""
		if isinstance(expr, syntax.Literal):
			scope.constant(expr.value)
		elif isinstance(expr, syntax.Lookup):
			scope.load(expr.ref.dfn)
		elif isinstance(expr, syntax.FieldReference) and is_eager(expr.lhs):
			self.force(expr.lhs, scope)
			scope.emit_field(expr.field_name.key())
		elif isinstance(expr, syntax.ExplicitList):
			self.visit_ExplicitList(expr, scope)
		else:
			scope.make_thunk(self, expr)
	
	def force(self, expr:syntax.Expr, scope:VMFunctionScope):
		"""
		Respond to the fact that params and fields may harbor thunks.
		"""
		if isinstance(expr, syntax.Literal):
			scope.constant(expr.value)
		elif isinstance(expr, syntax.Lookup):
			sym = expr.ref.dfn
			scope.load(sym)
			if symbol_harbors_thunks(sym):
				emit("FORCE")
		elif handles_tails(expr):
			self.visit(expr, scope, False)
		else:
			self.visit(expr, scope)
	
	def tail_call(self, expr:syntax.Expr, scope:VMFunctionScope):
		if isinstance(expr, syntax.Literal):
			scope.constant(expr.value)
			scope.emit_return()
		elif isinstance(expr, syntax.Lookup):
			sym = expr.ref.dfn
			scope.load(sym)
			if symbol_harbors_thunks(sym):
				scope.emit_force_return()
			else:
				scope.emit_return()
		elif handles_tails(expr):
			self.visit(expr, scope, True)
		else:
			self.visit(expr, scope)
			scope.emit_return()

	def write_begin_expression(self, expr:syntax.Expr, scope:VMFunctionScope):
		scope.nl()
		self.force(expr, scope)
		scope.display()
	
	def visit_BinExp(self, it: syntax.BinExp, scope:VMFunctionScope):
		self.force(it.lhs, scope)
		self.force(it.rhs, scope)
		scope.emit_ALU(it.op.text)
	
	def visit_ShortCutExp(self, it: syntax.ShortCutExp, scope:VMFunctionScope, tail:bool):
		self.force(it.lhs, scope)
		satisfied = SHORTCUTS[it.op.text]
		label = scope.jump_if(satisfied)
		if tail:
			self.tail_call(it.rhs, scope)
			scope.come_from(label)
			scope.emit_return()
		else:
			self.force(it.rhs, scope)
			scope.come_from(label)
	
	def visit_UnaryExp(self, ux:syntax.UnaryExp, scope:VMFunctionScope):
		self.force(ux.arg, scope)
		emit(UNARY_INSTRUCTION[ux.op.text])  # No change to stack depth

	def visit_Call(self, call:syntax.Call, scope:VMFunctionScope, tail:bool):
		for arg in call.args:
			self.delay(arg, scope)
		self.force(call.fn_exp, scope)
		scope.emit_call(tail, len(call.args))
	
	def visit_Cond(self, cond:syntax.Cond, scope:VMFunctionScope, tail:bool):
		self.force(cond.if_part, scope)
		label_else = scope.jump_if(False)
		if tail:
			self.tail_call(cond.then_part, scope)
			scope.come_from(label_else)
			self.tail_call(cond.else_part, scope)
		else:
			self.force(cond.then_part, scope)
			after = scope.jump_always()
			scope.come_from(label_else)
			scope.emit_pop()
			self.force(cond.else_part, scope)
			scope.come_from(after)

	def visit_MatchExpr(self, mx:syntax.MatchExpr, scope:VMFunctionScope, tail:bool):
		scope.alias(mx.subject)
		self.force(mx.subject.expr, scope)
		depth = scope.depth()
		nr_cases = len(mx.variant.subtypes)
		cases = scope.cases(nr_cases)
		after = []
		for alt in mx.alternatives:
			tag = self._tag_map[mx.variant, alt.nom.key()]
			scope.come_from(cases[tag])
			cases[tag] = None
			self.write_functions(alt.where, scope)
			if tail:
				self.tail_call(alt.sub_expr, scope)
			else:
				self.force(alt.sub_expr, scope)
				scope.ascend_to(depth)
				after.append(scope.jump_always())
		if mx.otherwise is not None:
			for tag, label in enumerate(cases):
				if label is not None:
					scope.come_from(label)
			if tail:
				self.tail_call(mx.otherwise, scope)
			else:
				self.force(mx.otherwise, scope)
				scope.ascend_to(depth)
		for label in after:
			scope.come_from(label)
		pass
	
	def visit_FieldReference(self, fr:syntax.FieldReference, scope:VMFunctionScope):
		self.force(fr.lhs, scope)
		scope.emit_field(fr.field_name.key())
		emit("FORCE")
		
	def visit_ExplicitList(self, el:syntax.ExplicitList, scope:VMFunctionScope):
		scope.emit_nil()
		for item in reversed(el.elts):
			self.delay(item, scope)
			scope.emit_snoc()

	@staticmethod
	def visit_Absurdity(_:syntax.Absurdity, scope:VMFunctionScope):
		scope.emit_panic()
	
	def visit_BindMethod(self, expr:syntax.BindMethod, scope:VMFunctionScope):
		self.force(expr.receiver, scope)
		emit("BIND", quote(expr.method_name.key()))

	def visit_DoBlock(self, do:syntax.DoBlock, outer:VMFunctionScope):
		inner = VMFunctionScope(outer, "do", is_thunk=False)
		inner.nl()
		emit('{ 0 "do"')
		depth = inner.depth()
		for step in do.steps:
			self.force(step, inner)
			inner.emit_perform()
			assert inner.depth() == depth
		inner.emit_return()
		inner.emit_epilogue()
		emit("}")
	
	def visit_AsTask(self, task:syntax.AsTask, scope:VMFunctionScope):
		self.force(task.sub, scope)
		emit("TASK")
	
	@staticmethod
	def visit_Skip(_:syntax.Skip, scope:VMFunctionScope):
		scope.emit_skip()
