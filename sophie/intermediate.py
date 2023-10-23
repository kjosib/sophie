"""
This part is currently a work in progress. 

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

def emit(x):
	print(x, end=" ")
def quote(x):
	assert '"' not in x
	return '"'+x+'"'
def post(tail):
	if tail:
		emit("RETURN")


LABEL_QUEUE = list(reversed(range(4096)))
LABEL_MAP = {}


class BaseContext:
	"""
	Why do I not attempt to re-use the existing stacking mechanism here?
	Because I'm solving a slightly different problem.
	I intend an in-order tree-walk passing these around *not only* as a breadcrumb trail,
	but also as a way to address non-locals.
	
	Escape analysis could perhaps do slightly better with static pointers,
	but this works regardless and it's consistent. And allegedly plenty fast, too.
		
	There is a small gotcha: Functions may capture their peers. To avoid ordering problems,
	allocate the closures first and then fill in their captive linkages.
	Sophie never sees an incompletely-initialized closure.
	"""
	
	indent = ""
	def nl(self):
		print()
		print("", end=self.indent)

	def capture(self, symbol: ontology.Symbol) -> bool:
		raise NotImplementedError(type(self))

	def emit_captured(self, captives: list[ontology.Symbol]):
		raise NotImplementedError(type(self))

	def declare(self, symbol: ontology.Symbol):
		raise NotImplementedError(type(self))

class RootContext(BaseContext):
	def capture(self, symbol: ontology.Symbol) -> bool:
		return False

	def emit_captured(self, captives: list[ontology.Symbol]):
		assert not captives

	def declare(self, symbol: ontology.Symbol):
		return

class Context(BaseContext):
	def __init__(self, outer:BaseContext):
		self._outer = outer
		self.indent = outer.indent+"  "
		self._local = {}
		self._children = []
		self._captives = {}
		self._depth = 0
	
	def depth(self): return self._depth
	def reset(self, depth): self._depth = depth
	def pop(self): self._depth -= 1
	def push(self): self._depth += 1
	
	def declare(self, symbol: ontology.Symbol):
		self.alias(symbol)
		self.push()
	
	def alias(self, symbol: ontology.Symbol):
		assert symbol not in self._local
		self._local[symbol] = self._depth
		
	def load(self, symbol: ontology.Symbol):
		if symbol in self._local:
			emit("LOCAL")
			emit(self._local[symbol])
		elif self.capture(symbol):
			emit("CAPTIVE")
			emit(self._captives[symbol])
		else:
			emit("GLOBAL")
			emit(quote(symbol.nom.text))
		self.push()

	def constant(self, value):
		emit("CONST")
		if isinstance(value, str):
			emit(quote(value))
		elif isinstance(value, (int, float)):
			emit(value)
		elif isinstance(value, bool):
			emit(INSTRUCTION_FOR[value])
		else:
			assert False
		self.push()

	def capture(self, symbol: ontology.Symbol) -> bool:
		if symbol in self._local or symbol in self._captives:
			return True
		elif self._outer.capture(symbol):
			self._captives[symbol] = len(self._captives)
			return True
		
	def jump(self, ins):
		emit(ins)
		return self.emit_hole()
	
	def emit_hole(self):
		label = LABEL_QUEUE.pop()
		emit("hole")
		emit(label)
		LABEL_MAP[label] = (self, self._depth)
		return label
	
	def come_from(self, label):
		(source, depth) = LABEL_MAP.pop(label)
		assert source is self, "Improper Come-From"
		self.reset(depth)
		emit("come_from")
		emit(label)
		LABEL_QUEUE.append(label)

	def emit_preamble(self, fn:syntax.UserFunction):
		# Emit number of parameters
		emit(len(fn.params))
		# Emit fully-qualified name
		emit(quote(fn.nom.text))
		for param in fn.params:
			self.declare(param)

	def emit_epilogue(self):
		# Consists of right brace, maximum number of locally-used stack slots,
		# number of captures, and information about each capture.
		if len(self._captives) > 255: raise TooComplicated("More than 255 captures in one function")

		emit("|")
		emit(len(self._captives))
		self._outer.emit_captured(list(self._captives)) # Preserving insertion order
		
	def emit_captured(self, captives: list[ontology.Symbol]):
		for sym in captives:
			if sym in self._local:
				emit("L")
				emit(self._local[sym])
			else:
				emit(self._captives[sym])
	
	def display(self):
		assert self._depth == 1, self.depth()
		emit("DISPLAY")
		self.pop()


class Translation(Visitor):
	def visit_RoadMap(self, roadmap:RoadMap):
		context = RootContext()
		for module in roadmap.each_module:
			self.visit_Module(module, context)
	
	def visit_Module(self, module:syntax.Module, root:RootContext):
		self.write_functions(module.outer_functions, root)
		context = Context(root)
		for expr in module.main:
			self.write_begin_expression(expr, context)

	def write_functions(self, fns, outer:BaseContext):
		if not fns: return
		for fn in fns:
			outer.declare(fn)
		emit("{")
		last = fns[-1]
		for fn in fns:
			self.write_one_function(fn, Context(outer))
			emit("}" if fn is last else ";")
		outer.nl()


	def write_one_function(self, fn, inner:Context):
		inner.nl()
		inner.emit_preamble(fn)
		self.write_functions(fn.where, inner)
		self.visit(fn.expr, inner, True)
		inner.emit_epilogue()

	def write_begin_expression(self, expr, context:Context):
		context.nl()
		self.visit(expr, context, False)
		context.display()
	
	def visit_Lookup(self, lu:syntax.Lookup, context:Context, tail:bool):
		self.visit(lu.ref, context, tail)

	@staticmethod
	def visit_PlainReference(ref:syntax.PlainReference, context:Context, tail:bool):
		sym = ref.dfn
		context.load(sym)
		if isinstance(sym, syntax.UserFunction):
			if not sym.params:
				emit("EXEC" if tail else "CALL")
		post(tail)

	def visit_BinExp(self, it: syntax.BinExp, context:Context, tail:bool):
		self.visit(it.lhs, context, False)
		self.visit(it.rhs, context, False)
		emit(INSTRUCTION_FOR[it.glyph])
		context.pop()
		post(tail)
	
	def visit_UnaryExp(self, ux:syntax.UnaryExp, context:Context, tail:bool):
		self.visit(ux.arg, context, False)
		emit(INSTRUCTION_FOR[ux.glyph])
		post(tail)

	@staticmethod
	def visit_Literal(l:syntax.Literal, context:Context, tail:bool):
		context.constant(l.value)
		post(tail)

	def visit_Call(self, call:syntax.Call, context:Context, tail:bool):
		# Order of operations here is meaningless because it must be pure.
		# Sort of.
		depth = context.depth()
		for arg in call.args:
			self.visit(arg, context, False)
		self.visit(call.fn_exp, context, False)
		if tail:
			emit("EXEC")
		else:
			emit("CALL")
			context.reset(depth)
			context.push()

	def visit_Cond(self, cond:syntax.Cond, context:Context, tail:bool):
		# This is super-simplistic for now.
		# It just has to work, not be hyper-optimized.
		depth = context.depth()
		self.visit(cond.if_part, context, False)
		assert context.depth() == depth+1
		
		label_else = context.jump("JF")
		context.pop()
		
		self.visit(cond.then_part, context, tail)
		assert context.depth() == depth + 1
		
		if tail:
			context.come_from(label_else)
			self.visit(cond.else_part, context, True)
		
		else:
			after = context.jump("JMP")
			context.come_from(label_else)
			emit("POP")
			context.pop()
			self.visit(cond.else_part, context, False)
			context.come_from(after)

