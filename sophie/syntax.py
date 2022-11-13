"""
The set of parse-nodes in simple form.
The parser calls these constructors with subordinate semantic-values in a bottom-up tree transduction.
These constructors may add a touch of organization.
Class-level type annotations make peace with pycharm wherever later passes add fields.

"""

import abc
from typing import NamedTuple, Optional, Any, Callable, Union
import operator
from boozetools.parsing.interface import SemanticError
from boozetools.support.symtab import NameSpace

class PrimitiveType:
	""" For the moment, a few primitive bits unavailable to the language-proper are also here. """
	pass

class Name:
	# The generic semantic-value type the scanner yields for non-reserved words.
	def __init__(self, text, slice):
		self.text, self.slice = text, slice

	def __str__(self):
		return "<Name %r>"%self.text
	
	def tag(self):
		return self.text

class NilToken:
	def __init__(self, a_slice):
		self.text = "NIL"
		self.slice = a_slice

	def __str__(self):
		return "NIL"
	
	@staticmethod
	def tag():
		return None

TypeTag = Union[Name, NilToken]

class MismatchedBookendsError(SemanticError):
	# The one semantic error we catch early enough to interrupt the parse.
	# It's early warning that things have gotten out of whack.
	def __init__(self, head:slice, coda:slice):
		super().__init__(head, coda)

def _bookend(head:Name, coda:Name):
	if head.text != coda.text:
		raise MismatchedBookendsError(head.slice, coda.slice)

class RecordType:
	def __init__(self, factors:list):
		self.factors = factors
	
	def fields(self):
		return [f.name.text for f in self.factors]

class TypeSummand:
	tag_ordinal: int
	def __init__(self, name:TypeTag, body:Optional[Any]):
		self.name, self.body = name, body
	
def nil_type(a_slice):
	return TypeSummand(NilToken(a_slice), None)

def ordinal_type(name:Name):
	return TypeSummand(name, None)

class VariantType:
	def __init__(self, alternatives:list[TypeSummand]):
		self.alternatives = alternatives
		for tag_ordinal, t in enumerate(alternatives):
			t.tag_ordinal = tag_ordinal

class ArrowType(NamedTuple):
	lhs: list[Any]
	rhs: Any

def short_arrow_type(lhs, rhs):
	return ArrowType([lhs], rhs)

class TypeCall(NamedTuple):
	name: Name
	params: list

class TypeDecl:
	namespace: NameSpace
	def __init__(self, name:Name, params:Optional[list], body:Any):
		self.name, self.params, self.body = name, params, body

class Parameter(NamedTuple):
	name: Name
	type_expr: Any

def param_inferred(name):
	return Parameter(name, None)

class Signature(NamedTuple):
	name: Name
	params: Optional[list[Parameter]]
	return_type: Optional[object]

class Expr(abc.ABC):
	pass

class Function:
	namespace: NameSpace
	sub_fns: dict[str:"Function"]  # for simple evaluator
	def __init__(self, signature: Signature, expr:Expr, where: Optional["WhereClause"]):
		self.signature, self.expr = signature, expr
		if where:
			_bookend(signature.name, where.end_name)
			self.where = where.sub_fns
		else:
			self.where = ()


class WhereClause(NamedTuple):
	sub_fns: list[Function]
	end_name: Name

	
class Module:
	namespace: NameSpace
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
	def __init__(self, op:Callable, lhs:Expr, rhs:Expr):
		self.op, self.lhs, self.rhs = op, lhs, rhs

def _be(op): return lambda a, b: BinExp(op, a, b)

PowerOf = _be(operator.pow)
Mul = _be(operator.mul)
FloatDiv = _be(operator.truediv)
FloatMod = _be(operator.mod)
IntDiv = _be(operator.ifloordiv)
IntMod = _be(operator.imod)
Add = _be(operator.add)
Sub = _be(operator.sub)

EQ = _be(operator.eq)
NE = _be(operator.ne)
LE = _be(operator.le)
LT = _be(operator.lt)
GE = _be(operator.ge)
GT = _be(operator.gt)

class ShortCutExp(Expr):
	def __init__(self, keep:bool, lhs:Expr, rhs:Expr):
		self.keep, self.lhs, self.rhs = keep, lhs, rhs

def LogicalAnd(a,b): return ShortCutExp(False, a, b)
def LogicalOr(a,b): return ShortCutExp(True, a, b)

class UnaryExp(Expr):
	def __init__(self, op:Callable, arg:Expr):
		self.op, self.arg = op, arg

def Negative(arg): return UnaryExp(operator.neg, arg)
def LogicalNot(arg): return UnaryExp(operator.not_, arg)

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
	pattern: TypeTag
	expr: Expr

class MatchExpr(Expr):
	dispatch: dict[Optional[str]:Expr]
	def __init__(self, name:Name, alternatives:list[Alternative], otherwise:Optional[Expr]):
		self.name, self.alternatives, self.otherwise = name, alternatives, otherwise

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
