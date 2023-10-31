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
	"LogicalAnd" : "JF",
	"LogicalOr" : "JT",
}

def emit(*xs):
	print(*xs, end=" ")
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
			emit("GLOBAL", quote(symbol.nom.text))
		self.push()

	def constant(self, value):
		if isinstance(value, bool):
			emit(INSTRUCTION_FOR[value])
		else:
			emit("CONST")
			if isinstance(value, str):
				emit(quote(value))
			elif isinstance(value, (int, float)):
				emit(value)
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
	
	def cases(self, nr_cases):
		emit("CASE")
		return [self.emit_hole() for _ in range(nr_cases)]
	
	def emit_hole(self):
		label = LABEL_QUEUE.pop()
		emit("hole", label)
		LABEL_MAP[label] = (self, self._depth)
		return label
	
	def come_from(self, label):
		(source, depth) = LABEL_MAP.pop(label)
		assert source is self, "Improper Come-From"
		self.reset(depth)
		emit("come_from", label)
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

		emit("|", len(self._captives))
		self._outer.emit_captured(list(self._captives)) # Preserving insertion order
		
	def emit_captured(self, captives: list[ontology.Symbol]):
		for sym in captives:
			if sym in self._local:
				emit("L", self._local[sym])
			else:
				emit(self._captives[sym])
	
	def display(self):
		assert self._depth == 1, self.depth()
		emit("DISPLAY")
		self.pop()
	
	def ascend_to(self, depth:int):
		assert self._depth >= depth
		if self._depth > depth:
			emit("ASCEND", self._depth - depth)
			self.reset(depth)


def write_record(names:Iterable[str], nom:ontology.Nom, tag:int):
	emit("(")
	for name in names:
		emit(name)
	close_structure(nom, tag)

def write_enum(nom:ontology.Nom, tag:int):
	write_record((), nom, tag)

def write_tagged_value(nom:ontology.Nom, tag:int):
	emit("(", "*")
	close_structure(nom, tag)

def close_structure(nom:ontology.Nom, tag:int):
	emit(tag)
	emit(quote(nom.text))
	emit(")")
	print()


class Translation(Visitor):
	def __init__(self):
		self._tag_map = {}  # For compiling type-cases.  
	
	def visit_RoadMap(self, roadmap:RoadMap):
		# Write all types:
		self.write_records(roadmap.preamble.types)
		for module in roadmap.each_module:
			self.write_records(module.types)
		
		# Write all functions:
		root = RootContext()
		self.write_functions(roadmap.preamble.outer_functions, root)
		for module in roadmap.each_module:
			self.write_functions(module.outer_functions, root)
		
		# Write all begin-expressions:
		context = Context(root)
		self.visit_Module(roadmap.preamble, context)
		for module in roadmap.each_module:
			self.visit_Module(module, context)
	
	def visit_Module(self, module:syntax.Module, context:Context):
		for expr in module.main:
			self.write_begin_expression(expr, context)

	def write_records(self, types):
		for t in types:
			self.visit(t)

	def visit_TypeAlias(self, t): pass
	def visit_Interface(self, t): pass
	
	@staticmethod
	def visit_Record(r:syntax.Record):
		write_record(r.spec.field_names(), r.nom, 0)
		
	def visit_Variant(self, variant:syntax.Variant):
		for tag, st in enumerate(variant.subtypes):
			self._tag_map[variant, st.nom.key()] = tag
			if isinstance(st.body, syntax.RecordSpec):
				write_record(st.body.field_names(), st.nom, tag)
			elif st.body is None:
				write_enum(st.nom, tag)
			else:
				write_tagged_value(st.nom, tag)

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
	
	def visit_ShortCutExp(self, it: syntax.ShortCutExp, context:Context, tail:bool):
		self.visit(it.lhs, context, False)
		label = context.jump(INSTRUCTION_FOR[it.glyph])
		context.pop()
		self.visit(it.rhs, context, False)
		context.come_from(label)
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
		
		if tail:
			context.come_from(label_else)
			self.visit(cond.else_part, context, True)
		
		else:
			assert context.depth() == depth + 1
			after = context.jump("JMP")
			context.come_from(label_else)
			emit("POP")
			context.pop()
			self.visit(cond.else_part, context, False)
			context.come_from(after)

	def visit_MatchExpr(self, mx:syntax.MatchExpr, context:Context, tail:bool):
		context.alias(mx.subject)
		self.visit(mx.subject.expr, context, False)
		depth = context.depth()
		nr_cases = len(mx.variant.subtypes)
		cases = context.cases(nr_cases)
		after = []
		for alt in mx.alternatives:
			tag = self._tag_map[mx.variant, alt.nom.key()]
			context.come_from(cases[tag])
			cases[tag] = None
			self.write_functions(alt.where, context)
			self.visit(alt.sub_expr, context, tail)
			if not tail:
				context.ascend_to(depth)
				after.append(context.jump("JMP"))
		if mx.otherwise is not None:
			for tag, label in enumerate(cases):
				if label is not None:
					context.come_from(label)
			self.visit(mx.otherwise, context, tail)
			if not tail:
				context.ascend_to(depth)
		for label in after:
			context.come_from(label)
		pass
	
	def visit_FieldReference(self, fr:syntax.FieldReference, context:Context, tail:bool):
		self.visit(fr.lhs, context, False)
		emit("FIELD")
		emit(quote(fr.field_name.key()))
		post(tail)

	def visit_ExplicitList(self, el:syntax.ExplicitList, context:Context, tail:bool):
		emit("NIL")
		context.push()
		for item in reversed(el.elts):
			self.visit(item, context, False)
			emit("SNOC")
			context.pop()
		post(tail)
