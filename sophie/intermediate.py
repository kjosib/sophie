"""
This is currently just some messing around. 

Probably assign every module a name consisting of minimal distinctive prefix.
Then give every function and constructor a mangled name based on its module and any surrounding scopes.
In the process, may as well work out the static depth of every function.
	- There's the textual static depth, and then there's the minimal static depth.
	- Type-checker may contribute to minimal static depth because it's based on the DependencyPass.
It will soon enough be necessary to solve an FFI for basic things.
The static-depth information will be useful for look-up operations.
	- local parameters emit an instruction with an offset from BP.
	- For outer parameters, I'm going to attempt closure captive a'la CLOX.
	- Globals can look up by name. The VM P-ASM may eventually precompute the hash lookup. 
	- locally-nested functions: The *code* is a global; the *closure* presumably becomes a local variable.
	- peers and uncles presumably equate to non-local (outer) variables.

"""

from typing import Iterable
from boozetools.support.foundation import Visitor
from . import syntax, ontology
from .resolution import RoadMap

class TooComplicated(Exception):
	pass

INSTRUCTION_FOR = {
	'PowerOf': 'POW',
	'Mul': 'MUL',
	'FloatDiv': 'DIV',
	'IntDiv': 'IDIV',
	'FloatMod': 'MOD',
	'IntMod': 'IMOD',
	'Add': 'ADD',
	'Sub': 'SUB',
	'EQ': 'EQ',
	'NE': 'EQ NOT',
	'LT': 'LT',
	'LE': 'GT NOT',
	'GT': 'GT',
	'GE': 'LT NOT',
	True: 'TRUE',
	False: 'FALSE',
	"Negative" : "NEG",
	"LogicalNot" : "NOT",
}

def emit(x): print(x, end=" ")
def quote(x):
	assert '"' not in x
	return '"'+x+'"'

class Context:
	"""
	Why do I not attempt to re-use the existing stacking mechanism here?
	Because I'm solving a slightly different problem.
	I intend an in-order tree-walk passing these around *not only* as a breadcrumb trail,
	but also as a way to address non-locals.
	
	Escape analysis could perhaps do slightly better with static pointers,
	but this works regardless and it's consistent. And allegedly plenty fast, too.
		
	There is a small gotcha: Functions may captive their peers. To avoid ordering problems,
	allocate the closures first and then fill in their captive linkages.
	Sophie never sees an incompletely-initialized closure.
	"""
	
	indent = ""
	def nl(self):
		print()
		print("", end=self.indent)

	def declare(self, symbol:ontology.Symbol):
		raise NotImplementedError(type(self))

	def capture(self, symbol: ontology.Symbol) -> bool:
		raise NotImplementedError(type(self))
	
	def load(self, symbol:ontology.Symbol):
		raise NotImplementedError(type(self))

	def emit_captured(self, captives:Iterable[ontology.Symbol]):
		raise NotImplementedError(type(self))


class RootContext(Context):
	pass

class ModuleContext(Context):
	def __init__(self, root:RootContext):
		self._root = root

	def declare(self, symbol:ontology.Symbol):
		pass

	def capture(self, symbol: ontology.Symbol):
		return False

	def load(self, symbol:ontology.Symbol):
		emit("GLOBAL")
		emit(quote(symbol.nom.text))

	def emit_captured(self, captives:Iterable[ontology.Symbol]):
		assert not captives
		emit(0)

class FunctionContext(Context):
	def __init__(self, outer:Context, fn:syntax.UserFunction):
		self.indent = outer.indent+"  "
		self._outer = outer
		self._arity = len(fn.params)
		self._local = {}
		self._captives = {}
		self._next_local = 0
		self._stack = []
		self._children = []
		
		for param in fn.params: self.declare(param)
		
	def emit_epilogue(self):
		# Consists of right brace, number of locals, number of other stack slots,
		# number of captures, and information about each capture.
		emit("}")
		nr_locals = 1+max(self._local.values()) if self._local else 0
		
		if nr_locals > 255: raise TooComplicated("More than 255 locals in one function")
		if len(self._captives) > 255: raise TooComplicated("More than 255 captures in one function")
		if len(self._children) > 255: raise TooComplicated("More than 255 children of one function")

		emit(nr_locals)
		self._outer.emit_captured(list(self._captives)) # Preserving insertion order
		emit(";")
		
	def emit_captured(self, captives: list[ontology.Symbol]):
		emit(len(captives))
		for sym in captives:
			if sym in self._local:
				emit("L")
				emit(self._local[sym])
			else:
				emit(self._captives[sym])
				
	def declare(self, symbol:ontology.Symbol):
		assert symbol not in self._local
		self._local[symbol] = self._next_local
		self._next_local += 1
		
	def mark(self): self._stack.append((self._next_local, self._depth))
	def restore(self): self._next_local, self._depth = self._stack.pop()
	
	def load(self, symbol:ontology.Symbol):
		if symbol in self._local:
			emit("PARAM")
			emit(self._local[symbol])
		elif self.capture(symbol):
			emit("CAPTIVE")
			emit(self._captives[symbol])
		else:
			emit("GLOBAL")
			emit(quote(symbol.nom.text))
	
	def capture(self, symbol: ontology.Symbol) -> bool:
		if symbol in self._local or symbol in self._captives:
			return True
		elif self._outer.capture(symbol):
			self._captives[symbol] = len(self._captives)
			return True
	
	def close_over(self, subs):
		emit("CLOSURE")
		emit(len(subs))
		emit(len(self._children))
		emit(self._next_local)
		self._children.extend(subs)
		for sub in subs:
			self.declare(sub)

class Translation(Visitor):
	def visit_RoadMap(self, roadmap:RoadMap):
		context = RootContext()
		for module in roadmap.each_module:
			self.visit(module, context)
	
	def visit_Module(self, module:syntax.Module, root:RootContext):
		context = ModuleContext(root)
		for fn in module.outer_functions:
			self.write_function(fn, context)
		for expr in module.main:
			self.write_begin_expression(expr, context)

	def write_function(self, fn, outer:Context):
		# Emit the preamble.
		emit("{")
		# Emit number of parameters
		emit(len(fn.params))
		# Emit fully-qualified name
		emit(quote(fn.nom.text))
		inner = FunctionContext(outer, fn)
		inner.nl()
		# Walk the function's direct children.
		for sub in fn.where:
			self.write_function(sub, inner)
		# Emit code to initialize child closures.
		if fn.where:
			inner.close_over(fn.where)
		self.visit(fn.expr, inner)
		inner.emit_epilogue()
		outer.nl()

	def write_begin_expression(self, expr, context:Context):
		context.nl()
		self.visit(expr, context)
		emit("DISPLAY")
	
	def visit_Lookup(self, lu:syntax.Lookup, context:Context):
		self.visit(lu.ref, context)

	@staticmethod
	def visit_PlainReference(ref:syntax.PlainReference, context:Context):
		context.load(ref.dfn)
		
	def visit_BinExp(self, it: syntax.BinExp, context:Context):
		self.visit(it.lhs, context)
		self.visit(it.rhs, context)
		emit(INSTRUCTION_FOR[it.glyph])
	
	def visit_UnaryExp(self, ux:syntax.UnaryExp, context:Context):
		self.visit(ux.arg, context)
		emit(INSTRUCTION_FOR[ux.glyph])

	@staticmethod
	def visit_Literal(l:syntax.Literal, _:Context):
		emit("CONST")
		if isinstance(l.value, str):
			emit(quote(l.value))
		elif isinstance(l.value, (int, float)):
			emit(l.value)
		elif isinstance(l.value, bool):
			emit(INSTRUCTION_FOR[l.value])
		else:
			assert False

	def visit_Call(self, call:syntax.Call, context:Context):
		# Order of operations here is meaningless because it must be pure.
		# Sort of.
		for arg in call.args:
			self.visit(arg, context)
		self.visit(call.fn_exp, context)
		emit("CALL")

	def visit_Cond(self, cond:syntax.Cond, context:Context):
		# This is super-simplistic for now.
		# It just has to work, not be hyper-optimized.
		self.visit(cond.if_part, context)
		emit("and")
		self.visit(cond.then_part, context)
		emit("else")
		self.visit(cond.else_part, context)
		emit("if")

