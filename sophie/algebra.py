from typing import Optional, Sequence
from .ontology import SophieType

class Arrow(SophieType):
	def __init__(self, argument: SophieType, reply: SophieType):
		self.argument, self.reply = argument, reply
	
	def for_expression_context(self, stem):
		pass


class DuckType(SophieType):
	""" Inferred composite with inferred fields. Yes, static duck-typing is a thing. """
	def __init__(self, fields:dict[str:SophieType]):
		self.fields = fields
	
	def for_expression_context(self, stem):
		assert False


class ProductType(SophieType):
	""" Type consisting of a tuple of values; commonly found at function call sites. """
	def __init__(self, fields: Sequence[SophieType]):
		self.fields = fields
	
	def for_expression_context(self, stem):
		assert False


class RecordType(SophieType):
	""" Declared fixed set of named fields. """
	def __init__(self, fields:dict[str:SophieType]):
		self.fields = fields
		self._product = ProductType(list(fields.values()))
	
	def for_expression_context(self, stem):
		return self._product

class JustNil(SophieType):
	"""The type of a lexical nil. Intersection with a variant is that variant's own nil case."""
	
	def intersect(self, other: "SophieType"):
		if isinstance(other, JustNil):
			return self
		if isinstance(other, SumType):
			return other.cases.get(None)
		
	def for_expression_context(self, stem):
		assert False

just_nil = JustNil()


class TypeVariable(SophieType):
	def __init__(self, text: str):
		self.text = text


class Constructor(SophieType):
	def __init__(self, symbol:str, argument:Optional[SophieType], params:Sequence[TypeVariable], extends:Optional["SumType"]):
		assert isinstance(symbol, str)
		assert argument is None or isinstance(argument, SophieType)
		self.symbol = symbol
		self.argument = argument
		self.params = params
		self.extends = extends
		
	def for_expression_context(self, stem):
		if self.argument is None:
			instance = self
		else:
			argument = self.argument.for_expression_context(stem)
			reply = self
			instance = Arrow(argument, reply)
		if self.params:
			instance = Bind(instance, {p:SophieType(stem) for p in self.params})
		return instance

class SumType(SophieType):
	cases: dict[Optional[str]:"Constructor|NilCase"]
	
	def __init__(self, name:str):
		self.atom = PrimitiveType(name)
		self.cases = {}

	def for_expression_context(self, stem):
		pass


class NilCase(SophieType):
	def __init__(self, extends:SumType):
		self.extends = extends
		extends.cases[None] = self
		
	def for_expression_context(self, stem):
		assert False, "These things have no names, and so can't be looked up."


class Bind(SophieType):
	def __init__(self, instance:SophieType, binding:dict[TypeVariable:SophieType]):
		self.instance = instance
		self.binding = binding
		
