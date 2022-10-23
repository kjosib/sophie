"""
The set of parse-nodes in simple form.
The parser calls these constructors with subordinate semantic-values in a bottom-up tree transduction.
The constructors must organize the information so later algorithms can traverse and access this stuff easily.
So, the resulting data structures will toss out much of the original linear structure,
to replace it with such internal linkages as seem proper for analyzing and translating the program.
"""
import abc
from typing import NamedTuple, Optional, Any, Callable
import operator
from boozetools.parsing.interface import SemanticError
from boozetools.support.symtab import NameSpace
from .preamble import static_root

def expect(desire, error, *tokens):
	if not desire:
		raise SemanticError(error, *tokens)

def nil_type_summand(a_slice): return Token("NIL", a_slice), None

class Expr(abc.ABC):
	pass

class Token(NamedTuple):
	# This is the generic semantic-value type the scanner yields for all nontrivial tokens.
	text: str
	slice: slice
	
	def __str__(self):
		return "<Token %r>"%self.text

class TypeDecl(NamedTuple):
	name: Token
	params: Optional[list]
	body: Any

class Parameter(NamedTuple):
	name: Token
	type_expr: Any

def param_inferred(name):
	return Parameter(name, None)

class Signature(NamedTuple):
	name: Token
	params: Optional[list[Parameter]]
	return_type: Optional[object]

class Function:
	def __init__(self, signature: Signature, expr:Expr, where: Optional["WhereClause"]):
		self.signature, self.expr = signature, expr
		self.namespace = NameSpace(place=self)
		self.sub_fns = {}
		for param in signature.params or ():
			self.namespace[param.name.text] = param
		if where is not None:
			desire = where.end_name.text == signature.name.text
			expect(desire, "Mismatched where-clause end needs to match", signature.name, where.end_name)
			for fn in where.sub_fns:
				key = fn.signature.name.text
				self.namespace[key] = fn
				self.sub_fns[key] = fn
			
class WhereClause(NamedTuple):
	sub_fns: list[Function]
	end_name: Token
	
class Module:
	def __init__(self, exports:Optional[list], imports:Optional[list], types:Optional[list[TypeDecl]], functions:Optional[list[Function]], main:Expr):
		self.exports = exports
		self.imports = imports
		self.namespace = NameSpace(place=self, parent=static_root)
		self.main = main
		for td in types or ():
			self.namespace[td.name.text] = td
		for fn in functions or ():
			self.namespace[fn.signature.name.text] = fn
			fn.namespace.parent = self.namespace  # Hack? Or not?

class Literal(Expr):
	def __init__(self, value:Any, slice:slice):
		self.value, self.slice = value, slice
	def __str__(self):
		return "<Literal %r>"%self.value

class FieldReference(Expr):
	def __init__(self, lhs:Expr, field_name:Token):
		self.lhs, self.field_name = lhs, field_name
	def __str__(self):
		return "(%s.%s)"%(self.lhs,self.field_name.text)

class BinExp(Expr):
	def __init__(self, op:Callable, lhs:Expr, rhs:Expr):
		self.op, self.lhs, self.rhs = op, lhs, rhs

def _be(op): return lambda a, b: BinExp(op, a, b)

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
		self.elts = elts
