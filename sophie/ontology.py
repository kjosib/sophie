from typing import Optional

class SyntaxNode:
	""" Marker class for things that can have a corresponding type? """
	def head(self) -> slice:
		"""
		To indicate which bit of code this node represents,
		return a slice-object relative to the source text.
		"""
		raise NotImplementedError(type(self))


class SophieType:
	""" A marker ABC. """
	def arity(self):
		return 0
	
	def for_expression_context(self, stem:SyntaxNode) -> Optional["SophieType"]:
		""" Return the type-value appropriate for a value-domain look-up, or None. """
		raise NotImplementedError(type(self))



KIND_TYPE = "TYPE"
KIND_VALUE = "VALUE"

class SymbolTableEntry:
	def __init__(self, kind:str, dfn, typ=None):
		self.kind = kind
		self.dfn = dfn
		self.typ = typ

