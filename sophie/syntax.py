"""
The set of parse-nodes in simple form.
The parser calls these constructors with subordinate semantic-values in a bottom-up tree transduction.
These constructors may add a touch of organization.
Class-level type annotations make peace with pycharm wherever later passes add fields.
"""

import abc
from typing import NamedTuple, Optional, Any, Callable
import operator
from boozetools.parsing.interface import SemanticError
from boozetools.support.symtab import NameSpace


class Token(NamedTuple):
	# The generic semantic-value type the scanner yields for all nontrivial tokens.
	text: str
	slice: slice
	
	def __str__(self):
		return "<Token %r>"%self.text

class MismatchedBookendsError(SemanticError):
	# The one semantic error we catch early enough to interrupt the parse.
	# It's early warning that things have gotten out of whack.
	def __init__(self, head:slice, coda:slice):
		super().__init__(head, coda)

def _bookend(head:Token, coda:Token):
	if head.text != coda.text:
		raise MismatchedBookendsError(head.slice, coda.slice)

class ProductType(NamedTuple):
	factors: list
	
	def fields(self):
		return [f.name.text for f in self.factors]

class TypeSummand:
	tag_ordinal: int
	def __init__(self, name:Token, body:Optional[ProductType]):
		self.name, self.body = name, body
	
def nil_type_summand(a_slice):
	return TypeSummand(Token("NIL", a_slice), None)

class UnionType:
	def __init__(self, alternatives:list[TypeSummand]):
		self.alternatives = alternatives
		for tag_ordinal, t in enumerate(alternatives):
			t.tag_ordinal = tag_ordinal

class ArrowType(NamedTuple):
	lhs: Any
	rhs: Any

class TypeCall(NamedTuple):
	name: Token
	params: list

class TypeDecl:
	namespace: NameSpace
	def __init__(self, name:Token, params:Optional[list], body:Any):
		self.name, self.params, self.body = name, params, body

class Parameter(NamedTuple):
	name: Token
	type_expr: Any

def param_inferred(name):
	return Parameter(name, None)

class Signature(NamedTuple):
	name: Token
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
	end_name: Token

	
class Module:
	namespace: NameSpace
	constructors: dict[str:]
	def __init__(self, exports:Optional[list], imports:Optional[list], types:Optional[list[TypeDecl]], functions:Optional[list[Function]], main:list[Expr]):
		self.exports = exports or ()
		self.imports = imports or ()
		self.types = types or ()
		self.functions = functions or ()
		self.main = main


class Literal(Expr):
	def __init__(self, value:Any, slice:slice):
		self.value, self.slice = value, slice
	def __str__(self):
		return "<Literal %r>"%self.value

class Lookup(Expr):
	def __init__(self, name:Token):
		self.name = name

class FieldReference(Expr):
	def __init__(self, lhs:Expr, field_name:Token):
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

class Comprehension(Expr):
	def __init__(self, selection, binding, projection):
		self.selection, self.binding, self.projection = selection, binding, projection

class ExplicitList(Expr):
	def __init__(self, elts:list[Expr]):
		for e in elts:
			assert isinstance(e, Expr), e
		self.elts = elts
