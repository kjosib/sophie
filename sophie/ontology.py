from typing import Optional, Mapping, Union
from boozetools.support.symtab import NameSpace

class SyntaxNode:
	""" Marker class for things that can have a corresponding type? """
	def head(self) -> slice:
		""" Indicate which bit of code this node represents. """
		raise NotImplementedError(type(self))

class Term:
	""" It's a term re-writing system to compute types. """
	rank = 0   # Rank for all structural types.
	def __init__(self, free:frozenset["TypeVariable"]):
		self.free = free
	def instantiate(self, gamma:dict): raise NotImplementedError(type(self))
	def rewrite(self, gamma:Mapping): raise NotImplementedError

class TypeVariable(Term):
	_counter = 0   # Each is distinct; there is thus no such thing as capture.
	def __init__(self):
		super().__init__(frozenset((self,)))
		self.nr = TypeVariable._counter
		TypeVariable._counter += 1
	def __repr__(self): return "<%s>"%self.nr
	def rewrite(self, gamma:Mapping): return gamma.get(self, self)
	def instantiate(self, gamma:dict):
		if self not in gamma:
			gamma[self] = TypeVariable()
		return gamma[self]

class PrimitiveType(Term):
	""" Presumably add clerical details here. """
	def __init__(self, name):
		super().__init__(frozenset())
		self.name = name
	def __repr__(self): return "<%s>"%self.name
	def rewrite(self, gamma:Mapping): return self
	def has_value_domain(self): return False  # .. HACK ..
	def instantiate(self, gamma:dict): return self

DEFINITION = Union[SyntaxNode, PrimitiveType]

class SymbolTableEntry:
	typ: Optional[Term]   # From the DefineNamedTypes pass
	quantifiers: tuple[TypeVariable, ...]  # From the WordDefiner pass
	echelon: int  # From the DefineNamedTypes pass
	def __init__(self, key, dfn:DEFINITION, typ):
		self.key = key
		self.dfn = dfn
		self.typ = typ
	def __str__(self):
		return "<Sym %s :%s : %s>"%(self.key, self.dfn, self.typ)

NS = NameSpace[SymbolTableEntry]
