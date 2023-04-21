"""
Type Domain Expressions:
The syntax of the high order typer
"""

from typing import Iterable
from ..ontology import Nom, Symbol, Reference
from .concrete import ConcreteType, Nominal

class TDX:
	""" Type-Domain Expression """

class Constant(TDX):
	def __init__(self, term: ConcreteType):
		assert isinstance(term, ConcreteType)
		self.term = term
	def __str__(self):
		return str(self.term)

class GlobalSymbol(TDX):
	def __init__(self, sym:Symbol):
		assert isinstance(sym, Symbol)
		self.sym = sym
	def __str__(self):
		return repr(self.sym)

class StackSymbol(TDX):
	def __init__(self, sym:Symbol, hops:int):
		assert isinstance(sym, Symbol)
		assert isinstance(hops, int)
		self.sym = sym
		self.hops = hops
	def __str__(self):
		return repr(self.sym)

class FieldType(TDX):
	def __init__(self, subject: TDX, field_name: Nom):
		self.subject, self.field_name = subject, field_name
	def __str__(self):
		return "%s.%s" % (self.subject, self.field_name.text)

class MatchType(TDX):
	def __init__(self, subject, ):
		pass

class Apply(TDX):
	def __init__(self, argument: TDX, operation: TDX):
		assert isinstance(argument, TDX)
		assert isinstance(operation, TDX)
		self.argument, self.operation = argument, operation
	def __str__(self):
		return "ap(%s,%s)" % (self.argument, self.operation)

class Operator(TDX):
	# This object is sort of like an arrow, but the arms are potentially yet to be evaluated.
	def __init__(self, parameter: TDX, result: TDX):
		self.parameter, self.result = parameter, result
	def __str__(self):
		return "[ %s *-> %s ]" % (self.parameter, self.result)

class Union(TDX):
	def __init__(self, args: Iterable[TDX]):
		self.args = tuple(args)
	def __str__(self):
		return "or(%s)" % (','.join(map(str, self.args)))

class ProductType(TDX):
	def __init__(self, args: Iterable[TDX]):
		self.args = tuple(args)
	def __str__(self):
		return "pr(%s)" % (','.join(map(str, self.args)))

class Syntactic(TDX):
	def __init__(self, nominal: Nominal, args: Iterable[TDX]):
		self.nominal = nominal
		self.args = tuple(args)
	def __str__(self):
		return "%s[%s]" % (self.nominal.dfn.nom.text, ','.join(map(str, self.args)))

