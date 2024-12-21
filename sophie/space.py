"""
Sophie's notion of a name-spaces with support for nested scopes
"""

from abc import ABC, abstractmethod
from typing import Iterable, NamedTuple, Optional
from .ontology import Phrase, Nom, Symbol, TypeSymbol, TermSymbol

class AlreadyExists(KeyError): pass
class Absent(KeyError): pass

class Space[T:Symbol](ABC):
	@abstractmethod
	def __contains__(self, key: str) -> bool: pass

	@abstractmethod
	def symbol(self, key: str) -> Optional[T]: pass

	@abstractmethod
	def locate(self, key: str) -> Phrase: pass
	
	def define(self, symbol: T) -> T:
		return self.install_alias(symbol.nom, symbol)
	
	def install_alias(self, alias: Nom, symbol: T) -> T:
		return self.mount(alias.key(), alias, symbol)
	
	@abstractmethod
	def mount(self, key:str, phrase:Phrase, symbol:T) -> T: pass
	
	def child(self) -> "Chain[T]":
		return Chain(Layer(), self)
	
	def atop(self, other: "Space[T]") -> "Chain[T]":
		return Chain(self, other)


class Layer[T:Symbol](Space[T]):
	""" Lightly enhanced dictionary: It does not like duplicate keys. """
	_locate: dict[str, Phrase]
	_symbol: dict[str, T]
	
	def __init__(self):
		self._locate, self._symbol = {}, {}
		
	def __contains__(self, key: str) -> bool:
		return key in self._symbol
	
	def symbol(self, key: str) -> Optional[T]:
		return self._symbol.get(key)

	def locate(self, key: str) -> Phrase:
		return self._locate[key]
	
	def mount(self, key:str, phrase:Phrase, symbol:T) -> T:
		if key in self._locate:
			raise AlreadyExists
		else:
			self._locate[key] = phrase
			self._symbol[key] = symbol
			return symbol
	
	def each_symbol(self) -> Iterable[T]:
		return self._symbol.values()


class Chain[T:Symbol](Space[T]):
	def __init__(self, top:Space[T], rest:Space[T]):
		self.top = top
		self._rest = rest
		
	def __contains__(self, key: str) -> bool:
		return key in self.top or key in self._rest
	
	def symbol(self, key: str) -> Optional[T]:
		return self.top.symbol(key) or self._rest.symbol(key)
	
	def locate(self, key: str) -> Phrase:
		try: return self.top.locate(key)
		except KeyError: return self._rest.locate(key)
	
	def mount(self, key:str, phrase:Phrase, symbol:T) -> T:
		return self.top.mount(key, phrase, symbol)


class Scope(NamedTuple):
	types: Space[TypeSymbol]
	terms: Space[TermSymbol]

	@staticmethod
	def fresh() -> "Scope":
		return Scope(Layer(), Layer())
	
	def atop(self, other) -> "Scope":
		return Scope(self.types.atop(other.types), self.terms.atop(other.terms))

	def with_terms(self, terms:Layer[TermSymbol]) -> "Scope":
		return Scope(self.types, terms.atop(self.terms))
