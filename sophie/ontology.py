from typing import Sequence
from boozetools.support.symtab import NameSpace

class Nom:
	""" Representing the occurrence of a name anywhere. """
	_slice: slice  # Empty-slice means pre-defined term.
	def __init__(self, text, a_slice): self.text, self._slice = text, a_slice or slice(0,0)
	def head(self) -> slice: return self._slice
	def __repr__(self): return "<Name %r>" % self.text
	def key(self): return self.text

class Symbol:
	"""
	Any named defined thing that may be found in some name-space.
	Thus, functions, parameters, types, subtypes, that sort of thing.
	It's not a syntax node by itself, but it is likely to contain them.
	It's more of a semantic node.
	In practice there's bound to be a strong correspondence,
	but there can also be built-in or imported symbols.
	"""
	nom: Nom  # fill in during parsing.
	static_depth: int  # fill during StaticDepthPass.
	def __init__(self, nom:Nom): self.nom = nom
	def __repr__(self):
		return "{%s:%s|%s}" % (self.nom.text, type(self).__name__, getattr(self,"static_depth", "?"))
	def __str__(self): return self.nom.text
	def head(self) -> slice: return self.nom.head()
	def has_value_domain(self) -> bool: raise NotImplementedError(type(self))

NS = NameSpace[Symbol]

class Term(Symbol):
	def has_value_domain(self): return True

class Expr:
	def head(self) -> slice:
		""" Indicate which bit of code this node represents. """
		raise NotImplementedError(type(self))

class Reference(Expr):
	nom:Nom
	dfn:Symbol   # Should happen during WordResolver pass.
	def __init__(self, nom:Nom): self.nom = nom

