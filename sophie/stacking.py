"""
These activation records were once used in both the type-checker and the evaluator.
However, at the moment, the tree-walking run-time is back to using unadorned dictionaries.
"""

from typing import Union
from pathlib import Path
from .ontology import Symbol
from .syntax import Module, ValueExpression

CRUMB = Union[Symbol, Module]

PLACE_HOLDER = object()

class Frame[T]:
	_bindings : dict[Symbol, T]
	dynamic_link : "Frame[T]"
	pc : ValueExpression = None
	breadcrumb : CRUMB = None
	
	# Bits for the type-checker:
	memo_key: tuple
	is_recursion_head: bool = False
	is_recursion_body: bool = False

	def path(self) -> Path: raise NotImplementedError(type(self))
	def trace(self, tracer): raise NotImplementedError(type(self))
	def holds(self, key:Symbol) -> bool: return key in self._bindings
	def assign(self, key:Symbol, value:T):
		self._bindings[key] = value
		return value
	def update(self, pairs): self._bindings.update(pairs)
	def fetch(self, key:Symbol) -> T: return self._bindings[key]

class RootFrame[T](Frame[T]):
	"""The runtime counterpart to primitive-root namespace"""
	def __init__(self):
		self._bindings = {}
	def trace(self, tracer): tracer.hit_bottom()

class Activation[T](Frame[T]):
	def __init__(self, dynamic_link: Frame[T], breadcrumb:CRUMB):
		self._bindings = {}
		self.dynamic_link = dynamic_link
		self.breadcrumb = breadcrumb
	
	def trace(self, tracer):
		self.dynamic_link.trace(tracer)
		if self.breadcrumb is not None:
			tracer.trace_frame(self.breadcrumb, self._bindings)
		if self.pc is not None: tracer.called_from(self.pc)
	
