"""
Simplest possible environment concept. Maybe.

This is the canonical list-structured search.

"""
from typing import Any
import abc

class Environment(abc.ABC):
	@abc.abstractmethod
	def resolve(self, name:str) -> Any:
		pass

class NullEnv(Environment):
	""" Effectively the built-in scope, but with nothing built in. (Yet?) """
	def resolve(self, name:str) -> Any:
		raise RuntimeError("unknown: " + repr(name))
null_env = NullEnv()

class InnerEnv(Environment):
	def __init__(self, bindings:dict[str:Any], static_link:Environment):
		self._children = children
		self._bindings = bindings
		self._static_link = static_link

