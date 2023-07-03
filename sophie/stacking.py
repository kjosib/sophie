"""
This is supposed to be a support module for anything that smells of executing code.
Because Sophie's type-checking philosophy is "run the program over the types",
that means these activation records get used in both the type-checker and the evaluator.

Despite superficial similarity, this is not treated quite the same as a namespace.

For now I've removed the complexity of tracking static depth.
Sophie does run a little slower this way, but it's for a purpose.
Upon this simplified foundation, I'll build as needed to properly reflect
the upcoming message-passing semantics.
"""

from typing import TypeVar, Generic
from pathlib import Path
from .ontology import Symbol
from .syntax import UserFunction, ValExpr, Subject

T = TypeVar("T")

PLACE_HOLDER = object()

class Frame(Generic[T]):
	_bindings : dict[T]
	pc : ValExpr = None
	def path(self) -> Path: raise NotImplementedError(type(self))
	def chase(self, key:Symbol) -> "Frame[T]": raise NotImplementedError(type(self))
	def trace(self, tracer): raise NotImplementedError(type(self))
	def declare(self, key:Symbol): self.assign(key, PLACE_HOLDER)
	def holds(self, key:Symbol) -> bool: return key in self._bindings
	def assign(self, key:Symbol, value:T):
		self._bindings[key] = value
		return value
	def fetch(self, key:Symbol) -> T:
		item = self._bindings[key]
		if item is PLACE_HOLDER: raise KeyError(item)
		else: return item

class RootFrame(Frame):
	"""The runtime counterpart to primitive-root namespace"""
	def __init__(self):
		self._bindings = {}
	def path(self) -> Path:
		pass
	def chase(self, key:Symbol) -> "Frame[T]":
		assert key in self._bindings, key  # Name resolution succeeded.
		return self
	def trace(self, tracer):
		tracer.hit_bottom()

class Activation(Frame):
	def __init__(self, static_link: Frame[T], breadcrumb:Symbol):
		self._bindings = {}
		self._static_link = static_link
		self.breadcrumb = breadcrumb
		
	def chase(self, key:Symbol) -> Frame[T]:
		return self if key in self._bindings else self._static_link.chase(key)

	def trace(self, tracer):
		tracer.trace_frame(self.breadcrumb, self._bindings, self.pc)

	@staticmethod
	def for_function(static_link: Frame[T], udf: UserFunction, arguments) -> "Activation[T]":
		assert len(udf.params) == len(arguments)
		ar = Activation(static_link, udf)
		ar._bindings.update(zip(udf.params, arguments))
		for key in udf.where:
			ar.declare(key)
		return ar

	@staticmethod
	def for_subject(static_link: Frame[T], subject:Subject) -> "Activation[T]":
		ar = Activation(static_link, subject)
		ar.declare(subject)
		return ar
