from typing import Optional, Mapping, Union
from boozetools.support.symtab import NameSpace

class SyntaxNode:
	""" Marker class for things that can have a corresponding type? """
	def head(self) -> slice:
		""" Indicate which bit of code this node represents. """
		raise NotImplementedError(type(self))

class PrimitiveType:
	""" Presumably add clerical details here. """
	quantifiers = ()
	def __init__(self, name):
		self.name = name
	def __repr__(self): return "<%s>"%self.name
	def has_value_domain(self): return False  # .. HACK ..

DEFINITION = Union[SyntaxNode, PrimitiveType]

class SymbolTableEntry:
	def __init__(self, key, dfn:DEFINITION, typ):
		self.key = key
		self.dfn = dfn  # A function, typedecl, record, variant, tag, field, type-parameter, primitive-type, primitive-value, or primitive-function.
		self.typ = typ  # The type of the whole symbol. So, in a function, the arrow. If a typedecl, a Symbolic.
	def __str__(self):
		return "<Sym %s :%s : %s>"%(self.key, self.dfn, self.typ)

NS = NameSpace[SymbolTableEntry]

