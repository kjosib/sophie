"""
The set of parse-nodes in simple form.
The parser calls these constructors with subordinate semantic-values in a bottom-up tree transduction.
These constructors may add a touch of organization.
Class-level type annotations make peace with pycharm wherever later passes add fields.
"""
from typing import Optional, Any, Sequence, NamedTuple, Union
from boozetools.parsing.interface import SemanticError
from boozetools.support.symtab import NameSpace
from .ontology import SymbolTableEntry, SyntaxNode
from .primitive import ops

class Name(SyntaxNode):
	entry: SymbolTableEntry  # The name-resolution pass fills this in.
	
	def __init__(self, text, a_slice):
		self.text, self._slice = text, a_slice
	
	def head(self) -> slice:
		return self._slice
	
	def __repr__(self):
		return "<Name %r>" % self.text
	
	def key(self):
		return self.text


class NilToken(SyntaxNode):
	def __init__(self, a_slice):
		self.text = "NIL"
		self._slice = a_slice
	
	def head(self) -> slice:
		return self._slice
	
	def __str__(self):
		return "NIL"
	
	@staticmethod
	def key():
		return None


class Expr(SyntaxNode):
	pass


SIMPLE_TYPE = Union["TypeCall", "ArrowSpec", "ImplicitType"]


class ArrowSpec(SyntaxNode):
	lhs: Sequence["SIMPLE_TYPE"]
	rhs: Optional["SIMPLE_TYPE"]
	
	def __init__(self, lhs, rhs):
		self.lhs = lhs
		self.rhs = rhs
		

class TypeCall(SyntaxNode):
	def __init__(self, name: Name, arguments: Sequence[SIMPLE_TYPE]):
		self.name, self.arguments = name, arguments
	
	def head(self) -> slice: return self.name.head()
	def has_value_domain(self): return False


def type_name(name: Name):
	return TypeCall(name, ())


class TypeParameter(NamedTuple):
	name: Name
	
	def head(self) -> slice: return self.name.head()


class ImplicitType(SyntaxNode):
	""" Stand-in as the relevant type-expression for when the syntax doesn't bother. """


class Parameter(NamedTuple):
	name: Name
	type_expr: Optional[SIMPLE_TYPE]
	def has_value_domain(self): return True
	def head(self) -> slice: return self.name.head()
	
	def key(self): return self.name.key()


def ordinal_member(name: Name): return Parameter(name, None)


class RecordType:
	namespace: NameSpace
	def has_value_domain(self): return True

	def __init__(self, fields: list[Parameter]):
		self.fields = fields
	
	def field_names(self):
		return [f.name.text for f in self.fields]


class NilMember(NilToken): pass


class SingletonMember(NamedTuple):
	name: Name
	type_expr: Union[TypeCall, ArrowSpec]
	
	def head(self) -> slice: return self.name.head()


class VariantSpec:
	_kw: slice
	def has_value_domain(self): return False
	def __init__(self, _kw: slice, alternatives: list[Union[Parameter, NilMember]]):
		self._kw = _kw
		self.alternatives = alternatives
		self.index = {}


class TypeDecl(SyntaxNode):
	namespace: NameSpace
	name: Name
	parameters: Sequence[TypeParameter]
	body: Union[TypeCall, VariantSpec, RecordType]
	
	def __init__(self, name, parameters: Sequence[Name], body) -> None:
		self.name = name
		self.parameters = [TypeParameter(p) for p in parameters or ()]
		self.body = body
	
	def head(self) -> slice:
		return self.name.head()

	def has_value_domain(self): return self.body.has_value_domain()

class MismatchedBookendsError(SemanticError):
	# The one semantic error we catch early enough to interrupt the parse.
	# It's early warning that things have gotten out of whack.
	def __init__(self, head: slice, coda: slice):
		super().__init__(head, coda)


def _bookend(head: Name, coda: Name):
	if head.text != coda.text:
		raise MismatchedBookendsError(head.head(), coda.head())


class Function(SyntaxNode):
	# This serves as either a function in the ordinary sense, or as a (local) constant.
	# It's a constant specifically when there are no params.
	# It's local because the expr closes over local names.
	namespace: NameSpace
	sub_fns: dict[str:"Function"]  # for simple evaluator
	where: list["Function"]
	
	def __init__(
			self,
			name: Name,
			params: Sequence[Parameter],
			expr_type: Optional[SIMPLE_TYPE],
			expr: Expr,
			where: Optional["WhereClause"]
	):
		self.name = name
		self.params = params or ()
		self.expr_type = expr_type
		self.expr = expr
		if where:
			_bookend(name, where.end_name)
			self.where = where.sub_fns
		else:
			self.where = ()
	
	def head(self) -> slice: return self.name.head()
	def has_value_domain(self): return True


class WhereClause(NamedTuple):
	sub_fns: list[Function]
	end_name: Name


class NilValue(NilToken): pass


class NilPattern(NilToken): pass


class Literal(Expr):
	def __init__(self, value: Any, a_slice: slice):
		self.value, self._slice = value, a_slice
	
	def __str__(self):
		return "<Literal %r>" % self.value
	
	def head(self) -> slice:
		return self._slice


class Lookup(Expr):
	def __init__(self, name: Name):
		self.name = name
	def head(self) -> slice: return self.name.head()

class FieldReference(Expr):
	def __init__(self, lhs: Expr, field_name: Name):
		self.lhs, self.field_name = lhs, field_name
	
	def __str__(self):
		return "(%s.%s)" % (self.lhs, self.field_name.text)
	def head(self) -> slice: return self.field_name.head()


class BinExp(Expr):
	def __init__(self, glyph: str, lhs: Expr, o:slice, rhs: Expr):
		self.glyph, self.lhs, self.rhs = glyph, lhs, rhs
		self.op, self.op_typ = ops[glyph]
		self._head = o
	
	def head(self) -> slice:
		return self._head


def _be(glyph: str): return lambda a, o, b: BinExp(glyph, a, o, b)


PowerOf = _be("PowerOf")
Mul = _be("Mul")
FloatDiv = _be("FloatDiv")
FloatMod = _be("FloatMod")
IntDiv = _be("IntDiv")
IntMod = _be("IntMod")
Add = _be("Add")
Sub = _be("Sub")

EQ = _be("EQ")
NE = _be("NE")
LE = _be("LE")
LT = _be("LT")
GE = _be("GE")
GT = _be("GT")


class ShortCutExp(Expr):
	def __init__(self, glyph: str, lhs: Expr, o:slice, rhs: Expr):
		self.keep, self.op_typ = ops[glyph]
		self.lhs, self.rhs = lhs, rhs
		self._head = o
	
	def head(self) -> slice:
		return self._head


def LogicalAnd(a, o, b): return ShortCutExp("LogicalAnd", a, o, b)
def LogicalOr(a, o, b): return ShortCutExp("LogicalOr", a, o, b)


class UnaryExp(Expr):
	def __init__(self, glyph: str, o:slice, arg: Expr):
		self.glyph, self.arg = glyph, arg
		self.op, self.op_typ = ops[glyph]
		self._head = o

	def head(self) -> slice: return self._head


def Negative(o, arg): return UnaryExp("Negative", o, arg)


def LogicalNot(o, arg): return UnaryExp("LogicalNot", o, arg)


class Cond(Expr):
	_kw: slice
	def __init__(self, then_part: Expr, _kw, if_part: Expr, else_part: Expr):
		self._kw = _kw
		self.then_part, self.if_part, self.else_part = then_part, if_part, else_part
	
	def __str__(self):
		return "(%s IF %s ELSE %s)" % (self.then_part, self.if_part, self.else_part)


def CaseWhen(when_parts: list, else_part: Expr):
	for _kw, test, then in reversed(when_parts):
		else_part = Cond(then, _kw, test, else_part)
	return else_part


class Call(Expr):
	def __init__(self, fn_exp: Expr, args: list[Expr]):
		self.fn_exp, self.args = fn_exp, args
	
	def __str__(self):
		return "%s(%s)" % (self.fn_exp, ', '.join(map(str, self.args)))


def call_upon_list(fn_exp: Expr, list_arg: Expr):
	return Call(fn_exp, [list_arg])


class ExplicitList(Expr):
	def __init__(self, elts: list[Expr]):
		for e in elts:
			assert isinstance(e, Expr), e
		self.elts = elts


class SubjectWithExpr(NamedTuple):
	expr: Expr
	name: Name


class Alternative(NamedTuple):
	pattern: Union[Name, NilPattern]
	sub_expr: Expr


class MatchExpr(Expr):
	dispatch: dict[Optional[str]:Expr]
	
	def __init__(self, name: Name, alternatives: list[Alternative], otherwise: Optional[Expr]):
		self.name, self.alternatives, self.otherwise = name, alternatives, otherwise
	
	def head(self) -> slice:
		return self.name.head()


class WithExpr(Expr):
	# Represent a block-local scope for a name bound to an expression.
	def __init__(self, expr: Expr, name: Name, body: Expr):
		self.expr, self.name, self.body = expr, name, body
	def head(self) -> slice: return self.name.head()


def match_expr(subject, alternatives: list[Alternative], otherwise: Optional[Expr]):
	if isinstance(subject, Name):
		return MatchExpr(subject, alternatives, otherwise)
	else:
		assert isinstance(subject, SubjectWithExpr)
		return WithExpr(subject.expr, subject.name, MatchExpr(subject.name, alternatives, otherwise))

class Module:
	namespace: NameSpace[SymbolTableEntry]
	constructors: dict[str:]
	def __init__(self, exports:list, imports:list, types:list, functions:list, main:list):
		self.exports = exports
		self.imports = imports
		self.types = types
		self.functions = functions
		self.main = main
