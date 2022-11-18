from typing import Any, Optional, NamedTuple, Sequence

class SyntaxNode:
	def head(self) -> slice:
		""" To indicate which bit of code this node represents, return a slice-object relative to the source text. """
		raise NotImplementedError(type(self))


class SophieType:
	""" A marker ABC. """
	def arity(self):
		return 0
	def intersect(self, other:"SophieType"):
		raise NotImplementedError(self, other)

class Cell:
	"""
	A cell is the fundamental participant in the unification algorithm.
	It may have a proxy, or it may have a value(i.e inferred type),
	or it be completely free, having neither. But it may not have both.
	In any case, it *stems* from either:
		1. some syntax expression,
		2. the signature of some function, or
		3. a built-in feature,
	and this is critical for decent error-reporting.
	"""
	_proxy : Optional["Cell"]
	value : Optional["SophieType"]
	def __init__(self, stem:Optional[SyntaxNode]):
		self.stem = stem
		if stem is not None: stem.head
		self._proxy = self
		self.value = None
	
	def blame(self):
		return slice(0,0) if self.stem is None else self.stem.head()
	
	def proxy(self) -> "Cell":
		"""
		One fundamental operation in unification is to find the earliest proxy.
		( Rather than encode age directly, I'll rely on a lexical invariant. )
		"""
		if self._proxy is self:
			return self
		else:
			# To avoid frequent long list traversals...
			p = self._proxy = self._proxy.proxy()
			return p
	
	def assign(self, value:SophieType):
		assert self._proxy is self
		assert self.value is None, self.value
		assert isinstance(value, SophieType), value
		self.value = value
		return self
	
	def become(self, other:"Cell"):
		self.value = None
		self._proxy = other


KIND_TYPE = "TYPE"
KIND_VALUE = "VALUE"

class SymbolTableEntry(NamedTuple):
	kind:str
	dfn: Any
	typ: Cell


class StructuralType(SophieType): pass


class Arrow(StructuralType):
	def __init__(self, argument: Cell, reply: Cell):
		self.argument, self.reply = argument, reply


class Onion(StructuralType):
	""" Type indicating that a data structure has one or more specifically-named fields. """
	def __init__(self, fields:dict[str:Cell]):
		self.fields = fields


class Product(StructuralType):
	""" Type consisting of a tuple of values; commonly found at function call sites. """
	def __init__(self, fields:Sequence[Cell]):
		self.fields = fields


class JustNil(StructuralType):
	"""The type of a lexical nil. Intersection with a variant is that variant's own nil case."""
	
	def intersect(self, other: "SophieType"):
		if isinstance(other, JustNil):
			return self
		if isinstance(other, Variant):
			return other.cases.get(None)

just_nil = JustNil()

class Nominal(SophieType):
	def __init__(self, name:str):
		# The core of nominal equivalence.
		self.name = name
		self.prepare()
	def prepare(self):
		pass
	
	def __str__(self):
		return "<%r %r>"%(type(self).__name__, self.name)

class AtomicType(Nominal):
	# These cannot be further analyzed in the type system.
	pass

class Record(Nominal):
	fields:dict[str:Cell]
	def prepare(self):
		self.fields = {}
	
class Variant(Nominal):
	cases:dict[Optional[str]:"TypeCase|NilCase"]
	def prepare(self):
		self.cases = {}

class TypeCase(Nominal):
	variant: Optional[Variant]
	body: Cell

class NilCase(SophieType):
	def __init__(self, variant:Variant):
		self.variant = variant
		variant.cases[None] = self

class ErrorType(SophieType):
	pass
	# def __init__(self, senior:Cell, junior:Cell):
	# 	self.stems = senior.stem, junior.stem
	# 	self.branches = senior.value, junior.value

class ExplicitParameter(SophieType):
	def __init__(self, text:str):
		self.text = text

class GenericType(SophieType):
	# -- Introduce Parameter(s) --
	# The body here can equally be a nominal or arrow type.
	def __init__(self, params:Sequence[Cell], body:Cell):
		assert len(params)
		self.params = params
		self.body = body
	def arity(self):
		return len(self.params)

class ConcreteType(SophieType):
	# -- Eliminate Parameter(s) --
	# Dual to a generic type; provides an environment for substitution.
	def __init__(self, generic:GenericType, args:Sequence[Cell]):
		assert len(args) == len(generic.params)
		self.generic = generic
		self.args = args
		
		