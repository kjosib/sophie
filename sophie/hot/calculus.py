"""
Part of the abstract-interpretation based type-checker.
These bits represent the data over which the type-checker operates.
To understand better, start by reading the "High-Order Type Checking"
section at https://sophie.readthedocs.io/en/latest/mechanics.html

This file is enumerates all kinds of types, which include first-order types like:
	Type Variables (i.e. known-unknowns)
	Nominal types (which refer back to symbols, and do by definition have exactly however many arguments as the symbol)
	Arrow types (which generally have a product on the left)
	Product types (which are generally found on the left side of an arrow)
	Bottom (about which the algebraic laws are written at the link above)
	Error: The type that means something went off the rails.
	
and also some additional type-operators:
	FieldType: represents field-access as a function-like type.
	UnionType: represents selection points which depend on run-time data, and a related concept with list syntax.
	UDFType: Deals with user-defined functions which may be polymorphic in weird ways.
	CallSiteType: Combines an arrow-type (or UDF) with an argument to get a result.

I originally thought he type-numbering subsystem would mediate all interaction with concrete types.
Clients would call for what they mean to compose, and the subsystem would give back a type-number.
Or, given a type-number, the subsystem could return a smart object.
But then I remembered the rest of the world is only readable in terms of smart objects.
Therefore, the present design maps all type-parameters to their exemplars,
and uses type-numbering internally to make hash-checks and equality comparisons go fast.

Conveniently, type-numbering is just an equivalence classification scheme.
I can reuse the one from booze-tools.

"""
from abc import ABC, abstractmethod
from typing import Iterable
from boozetools.support.foundation import EquivalenceClassifier
from ..syntax import Nom, TypeDeclaration, UserDefinedFunction

_type_numbering_subsystem = EquivalenceClassifier()

class TypeVisitor(ABC):
	@abstractmethod
	def on_variable(self, v:"TypeVariable"): pass
	@abstractmethod
	def on_nominal(self, n:"Nominal"): pass
	@abstractmethod
	def on_field(self, n:"FieldType"): pass
	@abstractmethod
	def on_arrow(self, a:"Arrow"): pass
	@abstractmethod
	def on_product(self, p:"Product"): pass
	@abstractmethod
	def on_union(self, u:"UnionType"): pass
	@abstractmethod
	def on_udf(self, f:"UDFType"): pass
	@abstractmethod
	def on_call(self, c: "CallSiteType"): pass
	@abstractmethod
	def on_bottom(self): pass
	@abstractmethod
	def on_error_type(self): pass

class SophieType(ABC):
	"""Value objects so they can play well with the classifier"""
	def ponder(self, env:dict) -> "SophieType": pass
	@abstractmethod
	def visit(self, visitor:TypeVisitor): pass

	def __init__(self, *key):
		self._key = key
		self._hash = hash(key)
		self.number = _type_numbering_subsystem.classify(self)
	def __hash__(self): return self._hash
	def __eq__(self, other: "SophieType"): return type(self) is type(other) and self._key == other._key
	def exemplar(self) -> "SophieType": return _type_numbering_subsystem.exemplars[self.number]

class TypeVariable(SophieType):
	"""Did I say value-object? Not for type variables! These have identity."""
	def __init__(self):
		super().__init__(len(_type_numbering_subsystem.catalog))
	def visit(self, visitor:TypeVisitor): return visitor.on_variable(self)

class Nominal(SophieType):
	""" Either a record directly, or a variant-type. Details are in the symbol table. """
	# NB: The arguments here are actual arguments, not formal parameters.
	#     The corresponding formal parameters are listed in the symbol,
	#     itself being either a SubTypeSpec or a TypeDecl
	def __init__(self, dfn: TypeDeclaration, params: Iterable[SophieType]):
		assert dfn.is_nominal()
		self.dfn = dfn
		self.params = tuple(p.exemplar() for p in params)
		super().__init__(self.dfn, *(p.number for p in self.params))
	def visit(self, visitor:TypeVisitor): return visitor.on_nominal(self)

class Product(SophieType):
	def __init__(self, fields: Iterable[SophieType]):
		self.fields = tuple(p.exemplar() for p in fields)
		super().__init__(*(p.number for p in self.fields))
	def visit(self, visitor:TypeVisitor): return visitor.on_product(self)
	
class Arrow(SophieType):
	def __init__(self, arg: SophieType, res: SophieType):
		self.arg, self.res = arg.exemplar(), res.exemplar()
		super().__init__(self.arg, self.res)
	def visit(self, visitor:TypeVisitor): return visitor.on_arrow(self)

class UDFType(SophieType):
	def visit(self, visitor:TypeVisitor): return visitor.on_udf(self)

class TopLevelFunctionType(UDFType):
	# Comes from looking up a function defined in the outermost scope.
	# Such functions need not concern themselves with environmental types in nonlocal parameters.
	def __init__(self, fn:UserDefinedFunction):
		assert isinstance(fn, UserDefinedFunction)
		self.fn = fn
		super().__init__(fn)

class NestedFunctionType(UDFType):
	# Comes from looking up a nested function.
	# Evaluating the type of such a beast /may/ involve looking in the static environment.
	# Please note: One day I hope to use a compiler pass to
	def __init__(self, fn:UserDefinedFunction, static_link:dict):
		assert isinstance(fn, UserDefinedFunction)
		assert isinstance(static_link, dict)
		self.fn = fn
		# NB: The uniqueness notion here is excessive, but there's a plan to deal with that.
		#     Whatever instantiates a nested function must enter it in the static scope without duplication.
		#     Performance hacking may make for an even better cache than that.
		super().__init__(object())

class UnionType(SophieType):
	def __init__(self, elements: Iterable[SophieType]):
		self.elements = set(p.exemplar() for p in elements)
		super().__init__(*sorted(e.number for e in self.elements))
	def visit(self, visitor:TypeVisitor): return visitor.on_union(self)

class FieldType(SophieType):
	def __init__(self, subject: SophieType, field_name: Nom):
		self._subject = subject
		self._field_name = field_name
		super().__init__(subject, field_name.text)
	def visit(self, visitor:TypeVisitor): return visitor.on_field(self)

class CallSiteType(SophieType):
	def __init__(self, arrow:SophieType, arg:SophieType):
		self._arrow = arrow.exemplar()
		self._arg = arg.exemplar()
		super().__init__(self._arrow, self._arg)
	def visit(self, visitor:TypeVisitor): return visitor.on_call(self)


class _Bottom(SophieType):
	def visit(self, visitor:TypeVisitor): return visitor.on_bottom()

BOTTOM = _Bottom(None)

class _Error(SophieType):
	# I'll probably end up adding relevant facts to the constructor.
	def visit(self, visitor:TypeVisitor): return visitor.on_error_type()

ERROR = _Error(None)

###################
#
#  Some few built-in concrete types:


