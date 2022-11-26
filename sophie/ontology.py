from boozetools.support.symtab import NameSpace

class SyntaxNode:
	""" Marker class for things that can have a corresponding type? """
	def head(self) -> slice:
		""" Indicate which bit of code this node represents. """
		raise NotImplementedError(type(self))


class SymbolTableEntry:
	def __init__(self, dfn, typ=None):
		self.dfn = dfn
		self.typ = typ
	def __str__(self):
		return "<STE %s : %s>"%(self.dfn, self.typ)

NS = NameSpace[SymbolTableEntry]
