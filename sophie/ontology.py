from boozetools.support.symtab import NameSpace

class Nom:
	""" Representing the occurrence of a name anywhere. """
	_slice: slice  # Empty-slice means pre-defined term.
	def __init__(self, text, a_slice): self.text, self._slice = text, a_slice or slice(0,0)
	def head(self) -> slice: return self._slice
	def __repr__(self): return "<Name %r>" % self.text
	def key(self): return self.text

class Term:
	""" A term re-writing system computes types. """
	def rewrite(self, delta: dict):
		""" Trivial re-write during the manifest phase. """
		raise NotImplementedError(type(self))
	def pull_rabbit(self, gamma:dict):
		""" Non-trivial re-write after a round of inference. """
	def fresh(self, gamma: dict): raise NotImplementedError(type(self))
	def phylum(self): raise NotImplementedError(type(self))
	def render(self, gamma: dict, delta) -> str:
		""" Return a string representation of the term. """
		raise NotImplementedError(type(self))
	def poll(self, seen:set):
		""" Find all the type-variables used in the term. """
		raise NotImplementedError(type(self))

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
	typ: Term  # fill in variously.
	static_depth: int  # fill during StaticDepthPass.
	def __repr__(self): return self.nom.text
	def head(self): return self.nom.head()
	def has_value_domain(self) -> bool: raise NotImplementedError(type(self))

class Expr:
	def head(self) -> slice:
		""" Indicate which bit of code this node represents. """
		raise NotImplementedError(type(self))

class Reference(Expr):
	nom:Nom
	dfn:Symbol   # Should happen during WordResolver pass.

class TypeExpr(Expr):
	pass

class ValExpr(Expr):
	pass

NS = NameSpace[Symbol]

class MatchProxy(Symbol):
	""" Within a match-case, a name must reach a different symbol with the particular subtype """
	def __init__(self, nom:Nom):
		self.nom = nom
	def has_value_domain(self) -> bool: return True
