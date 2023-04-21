"""
Part of the abstract-interpretation based type-checker.
These bits represent the data over which the type-checker operates.
To understand better, start by reading the "High-Order Type Checking"
section at https://sophie.readthedocs.io/en/latest/mechanics.html

This file is concerned with concrete types, which include:
	Type Variables (i.e. known-unknowns)
	Nominal types (which refer back to symbols, and do by definition have exactly however many arguments as the symbol)
	Arrow types (which generally have a product on the left)
	Product types (which are generally found on the left side of an arrow)
	Bottom (about which the algebraic laws are written at the link above)

I originally thought he type-numbering subsystem would mediate all interaction with concrete types.
Clients would call for what they mean to compose, and the subsystem would give back a type-number.
Or, given a type-number, the subsystem could return a smart object.
But then I remembered the rest of the world is only readable in terms of smart objects.
Therefore, the present design maps all type-parameters to their exemplars,
and uses type-numbering internally to make hash-checks and equality comparisons go fast.

Conveniently, type-numbering is just an equivalence classification scheme.
I can reuse the one from booze-tools.

"""
from typing import Iterable
from boozetools.support.foundation import EquivalenceClassifier
from ..ontology import Symbol

_type_numbering_subsystem = EquivalenceClassifier()

class ConcreteTypeVisitor:
	def on_variable(self, v:"TypeVariable"): pass
	def on_nominal(self, n:"Nominal"): pass
	def on_arrow(self, a:"Arrow"): pass
	def on_product(self, p:"Product"): pass
	def on_bottom(self): pass
	def on_error_type(self): pass

class ConcreteType:
	"""Value objects so they can play well with the classifier"""
	def __init__(self, *key):
		self._key = key
		self._hash = hash(key)
		self.number = _type_numbering_subsystem.classify(self)
	def __hash__(self): return self._hash
	def __eq__(self, other: "ConcreteType"): return type(self) is type(other) and self._key == other._key
	def exemplar(self) -> "ConcreteType": return _type_numbering_subsystem.exemplars[self.number]
	def visit(self, visitor:ConcreteTypeVisitor):
		""" Implement the visitor pattern... """
		raise NotImplementedError(type(self))

class TypeVariable(ConcreteType):
	"""Did I say value-object? Not for type variables! These have identity."""
	def __init__(self):
		super().__init__(len(_type_numbering_subsystem.catalog))
	def visit(self, visitor:ConcreteTypeVisitor): return visitor.on_variable(self)

class Nominal(ConcreteType):
	""" Either a record directly, or a variant-type. Details are in the symbol table. """
	def __init__(self, dfn: Symbol, params: Iterable[ConcreteType]):
		assert isinstance(dfn, Symbol)
		self.dfn = dfn
		self.params = tuple(p.exemplar() for p in params)
		super().__init__(self.dfn, *(p.number for p in self.params))
	def visit(self, visitor:ConcreteTypeVisitor): return visitor.on_nominal(self)

class Product(ConcreteType):
	def __init__(self, fields: Iterable[ConcreteType]):
		self.fields = tuple(p.exemplar() for p in fields)
		super().__init__(*(p.number for p in self.fields))
	def visit(self, visitor:ConcreteTypeVisitor): return visitor.on_product(self)
	
class Arrow(ConcreteType):
	def __init__(self, arg: ConcreteType, res: ConcreteType):
		self.arg, self.res = arg.exemplar(), res.exemplar()
		super().__init__(self.arg, self.res)
	def visit(self, visitor:ConcreteTypeVisitor): return visitor.on_arrow(self)

class _Bottom(ConcreteType):
	def visit(self, visitor:ConcreteTypeVisitor): return visitor.on_bottom()

BOTTOM = _Bottom(None)

class _Error(ConcreteType):
	# I'll probably end up adding relevant facts to the constructor.
	def visit(self, visitor:ConcreteTypeVisitor): return visitor.on_error_type()

ERROR = _Error(None)

###################
#
#  Some few built-in concrete types:


