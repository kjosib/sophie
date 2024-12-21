"""
These most-fundamental classes in the syntax class hierarchy
are separate from the rest to avoid various circular-import
scenarios. The concrete AST types have fields that get filled
in during the name-resolution pass, and I use type-annotations
to get help from the IDE to make sure those fields stay sane,
but in consequence these abstract base classes need to remain
separate from the rest.
"""
from typing import NamedTuple

class Phrase:
	def left(self) -> int:
		""" Return the index of the leftmost token of this phrase """
		raise NotImplementedError(type(self))
	def right(self) -> int:
		""" Return the index of the rightmost token of this phrase """
		raise NotImplementedError(type(self))
	def span(self) -> tuple[int, int]: return self.left(), self.right()

class Nom(Phrase):
	""" Representing the occurrence of a name anywhere. """
	spot: int  # zero-spot means pre-defined term.
	def __init__(self, text, spot):
		assert isinstance(text, str)
		assert isinstance(spot, int) or spot is None, type(spot)
		self.text, self.spot = text, spot or 0
	def __repr__(self): return "<Name %r>" % self.text
	def key(self): return self.text
	def left(self): return self.spot
	def right(self): return self.spot

class Symbol(Phrase):
	"""
	Any named-and-defined thing that may be found in some name-space.
	Thus, functions, parameters, types, subtypes, that sort of thing.
	"""
	nom: Nom  # fill in during parsing.

	def __init__(self, nom:Nom): self.nom = nom
	def __repr__(self): return "{%s:%s}" % (self.nom.text, type(self).__name__)
	
	# Definitions below serve if nothing better is defined per symbol-type.
	def left(self): return self.nom.left()
	def right(self): return self.nom.right()

class TypeSymbol(Symbol):
	def type_arity(self): raise NotImplementedError(type(self))

class TermSymbol(Symbol): pass

class TypeExpression(Phrase):
	def dispatch_token(self): raise NotImplementedError(type(self))

class ValueExpression(Phrase): pass


SELF = TermSymbol(Nom("SELF", None))

#######################################################################

class MemoSchedule(NamedTuple):
	# This bit helps with type-checking and likely also the run-time.
	arguments: tuple[int, ...]
	captures: tuple[TermSymbol, ...]

