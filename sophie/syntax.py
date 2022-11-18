"""
The set of parse-nodes in simple form.
The parser calls these constructors with subordinate semantic-values in a bottom-up tree transduction.
These constructors may add a touch of organization.
Class-level type annotations make peace with pycharm wherever later passes add fields.
"""

import abc
from typing import NamedTuple, Optional, Any, Union, Sequence
from boozetools.parsing.interface import SemanticError
from boozetools.support.symtab import NameSpace
from .primitive import ops
from .ontology import SymbolTableEntry, Cell, SyntaxNode

class Name(SyntaxNode):
	entry: SymbolTableEntry  # The name-resolution pass fills this in.
	def __init__(self, text, slice):
		self.text, self.slice = text, slice
	
	def head(self) -> slice: return self.slice
	
	def __str__(self):
		return "<Name %r>"%self.text
	
	def tag(self):
		return self.text

class NilToken(SyntaxNode):
	def __init__(self, a_slice):
		self.text = "NIL"
		self.slice = a_slice

	def head(self) -> slice: return self.slice
	
	def __str__(self):
		return "NIL"
	
	@staticmethod
	def tag():
		return None

Key = Union[Name, NilToken]

class MismatchedBookendsError(SemanticError):
	# The one semantic error we catch early enough to interrupt the parse.
	# It's early warning that things have gotten out of whack.
	def __init__(self, head:slice, coda:slice):
		super().__init__(head, coda)

def _bookend(head:Name, coda:Name):
	if head.text != coda.text:
		raise MismatchedBookendsError(head.slice, coda.slice)

class RecordType:
	def __init__(self, fields:list["Parameter"]):
		self.fields = fields
	
	def field_names(self):
		return [f.name.text for f in self.fields]

class TypeSummand:
	tag_ordinal: int
	def __init__(self, tag:Key, body:Optional[Any]):
		self.tag, self.body = tag, body
		assert not (body and self.is_nil())
	def is_nil(self):
		return isinstance(self.tag, NilToken)
	
def nil_type(a_slice):
	return TypeSummand(NilToken(a_slice), None)

def ordinal_type(name:Name):
	return TypeSummand(name, None)

class VariantType:
	def __init__(self, alternatives:list[TypeSummand]):
		self.alternatives = alternatives

class ArrowType(NamedTuple):
	lhs: Sequence[Any]
	rhs: Any

def short_arrow_type(lhs, rhs):
	return ArrowType([lhs], rhs)

class TypeCall(SyntaxNode):
	def __init__(self, name:Name, arguments:Sequence):
		self.name, self.arguments = name, arguments
	
	def head(self) -> slice:
		return self.name.head()


def plain_type(name:Name):
	return TypeCall(name, ())

class TypeDecl:
	namespace: NameSpace
	def __init__(self, name:Name, params:Optional[list[Name]], body:Any):
		self.name, self.body = name, body
		self.parameters = params or ()

class Parameter(NamedTuple):
	name: Name
	type_expr: Any

def param_inferred(name):
	return Parameter(name, None)

class TypeVariable:
	""" For writing out the parametric polymorphism in a function's signature. """
	def __init__(self, name):
		self.name = name

class Signature:
	expr_type: Cell

class FunctionSignature(Signature):
	def __init__(self, params: list[Parameter], return_type: Optional[Any]):
		self.params = params
		self.return_type = return_type
	
class ExpressionSignature(Signature):
	def __init__(self, name: Name):
		self.name = name

class AbsentSignature(Signature):
	pass

class Expr(SyntaxNode):
	pass

class Function:
	namespace: NameSpace
	sub_fns: dict[str:"Function"]  # for simple evaluator
	def __init__(self, name: Name, signature: Signature, expr:Expr, where: Optional["WhereClause"]):
		self.name = name
		self.signature = signature
		self.expr = expr
		if where:
			_bookend(name, where.end_name)
			self.where = where.sub_fns
		else:
			self.where = ()

class WhereClause(NamedTuple):
	sub_fns: list[Function]
	end_name: Name
	
class Module:
	namespace: NameSpace[SymbolTableEntry]
	constructors: dict[str:]
	def __init__(self, exports:Optional[list], imports:Optional[list], types:Optional[list[TypeDecl]], functions:Optional[list[Function]], main:Optional[list[Expr]]):
		self.exports = exports or ()
		self.imports = imports or ()
		self.types = types or ()
		self.functions = functions or ()
		self.main = main or ()

class Literal(Expr):
	def __init__(self, value:Any, slice:slice):
		self.value, self.slice = value, slice
	def __str__(self):
		return "<Literal %r>"%self.value

class Lookup(Expr):
	def __init__(self, name:Name):
		self.name = name

class FieldReference(Expr):
	def __init__(self, lhs:Expr, field_name:Name):
		self.lhs, self.field_name = lhs, field_name
	def __str__(self):
		return "(%s.%s)"%(self.lhs,self.field_name.text)

class BinExp(Expr):
	def __init__(self, glyph:str, lhs:Expr, rhs:Expr):
		self.glyph, self.lhs, self.rhs = glyph, lhs, rhs
		self.op, self.op_typ = ops[glyph]

def _be(glyph:str): return lambda a, b: BinExp(glyph, a, b)

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
	def __init__(self, glyph:str, lhs:Expr, rhs:Expr):
		self.keep, self.op_typ = ops[glyph]
		self.lhs, self.rhs = lhs, rhs

def LogicalAnd(a,b): return ShortCutExp("LogicalAnd", a, b)
def LogicalOr(a,b): return ShortCutExp("LogicalOr", a, b)

class UnaryExp(Expr):
	def __init__(self, glyph:str, arg:Expr):
		self.glyph, self.arg = glyph, arg
		self.op, self.op_typ = ops[glyph]

def Negative(arg): return UnaryExp("Negative", arg)
def LogicalNot(arg): return UnaryExp("LogicalNot", arg)

class Cond(Expr):
	def __init__(self, then_part:Expr, if_part:Expr, else_part:Expr):
		self.then_part, self.if_part, self.else_part = then_part, if_part, else_part
	def __str__(self):
		return "(%s IF %s ELSE %s)"%(self.then_part, self.if_part, self.else_part)

def CaseWhen(when_parts:list, else_part:Expr):
	for case, then in reversed(when_parts):
		else_part = Cond(then, case, else_part)
	return else_part

class Call(Expr):
	def __init__(self, fn_exp:Expr, args:list[Expr]):
		self.fn_exp, self.args = fn_exp, args
	def __str__(self):
		return "%s(%s)"%(self.fn_exp, ', '.join(map(str, self.args)))
		
def call_upon_list(fn_exp:Expr, list_arg:Expr):
	return Call(fn_exp, [list_arg])

def nil_value(a_slice): return Literal(None, a_slice)

class ExplicitList(Expr):
	def __init__(self, elts:list[Expr]):
		for e in elts:
			assert isinstance(e, Expr), e
		self.elts = elts

class SubjectWithExpr(NamedTuple):
	expr: Expr
	name: Name

class Alternative(NamedTuple):
	pattern: Key
	expr: Expr

class MatchExpr(Expr):
	dispatch: dict[Optional[str]:Expr]
	def __init__(self, name:Name, alternatives:list[Alternative], otherwise:Optional[Expr]):
		self.name, self.alternatives, self.otherwise = name, alternatives, otherwise
	def head(self) -> slice:
		return self.name.head()


class WithExpr(Expr):
	# Represent a block-local scope for a name bound to an expression.
	def __init__(self, expr:Expr, name:Name, body:Expr):
		self.expr, self.name, self.body = expr, name, body

def match_expr(subject, alternatives:list[Alternative], otherwise:Optional[Expr]):
	if isinstance(subject, Name):
		return MatchExpr(subject, alternatives, otherwise)
	else:
		assert isinstance(subject, SubjectWithExpr)
		return WithExpr(subject.expr, subject.name, MatchExpr(subject.name, alternatives, otherwise))
