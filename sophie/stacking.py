"""
This is supposed to be a support module for anything that smells of executing code.
Because Sophie's type-checking philosophy is "run the program over the types",
that means these activation records get used in both the type-checker and the evaluator.

Despite superficial similarity, this is not treated quite the same as a namespace.
"""

from typing import TypeVar, Generic, Union, Optional
from pathlib import Path
from .ontology import Symbol
from .syntax import Subroutine, ValExpr, Subject, Module

CRUMB = Union[Symbol, Module, None]

T = TypeVar("T")

PLACE_HOLDER = object()

class Frame(Generic[T]):
	_bindings : dict[Symbol, T]
	pc : ValExpr = None
	breadcrumb : CRUMB = None
	def path(self) -> Path: raise NotImplementedError(type(self))
	def chase(self, key:Symbol) -> "Frame[T]": raise NotImplementedError(type(self))
	def trace(self, tracer): raise NotImplementedError(type(self))
	def declare(self, key:Symbol): self.assign(key, PLACE_HOLDER)
	def holds(self, key:Symbol) -> bool: return key in self._bindings
	def assign(self, key:Symbol, value:T):
		self._bindings[key] = value
		return value
	def update(self, pairs):
		self._bindings.update(pairs)
	def fetch(self, key:Symbol) -> T:
		item = self._bindings[key]
		if item is PLACE_HOLDER: raise KeyError(key)
		else: return item

class RootFrame(Frame):
	"""The runtime counterpart to primitive-root namespace"""
	def __init__(self):
		self._bindings = {}
	def chase(self, key:Symbol) -> "Frame[T]":
		if key in self._bindings:
			return self
		else:
			raise KeyError(key)
	def trace(self, tracer):
		tracer.hit_bottom()
	
	def absorb(self, other:Frame):
		# This kludge allows imported symbols to work.
		# The root-frame stands in for an inter-module linkage model.
		self._bindings.update(other._bindings)

class Activation(Frame):
	def __init__(self, static_link: Frame[T], dynamic_link: Frame[T], breadcrumb:CRUMB):
		self._bindings = {}
		self._static_link = static_link
		self._dynamic_link = dynamic_link
		self.breadcrumb = breadcrumb
	
	def path(self) -> Optional[Path]:
		if self.breadcrumb and hasattr(self.breadcrumb, 'source_path'):
			return self.breadcrumb.source_path
		else:
			return self._static_link.path() 
		
	def chase(self, key:Symbol) -> Frame[T]:
		return self if key in self._bindings else self._static_link.chase(key)

	def trace(self, tracer):
		self._dynamic_link.trace(tracer)
		if self.breadcrumb is not None:
			tracer.trace_frame(self.path(), self.breadcrumb, self._bindings)
		if self.pc is not None: tracer.called_from(self.path(), self.pc)
	
	@staticmethod
	def for_subroutine(static_link: Frame[T], dynamic_link: Frame[T], sub: Subroutine, arguments) -> "Activation[T]":
		assert len(sub.params) == len(arguments), (sub, arguments)
		ar = Activation(static_link, dynamic_link, sub)
		ar.update(zip(sub.params, arguments))
		for key in sub.where:
			ar.declare(key)
		return ar

	@staticmethod
	def for_subject(static_link: Frame[T], subject:Subject, value:T) -> "Activation[T]":
		ar = Activation(static_link, static_link, subject)
		ar.assign(subject, value)
		return ar
	
	@staticmethod
	def for_module(static_link: Frame[T], module:Module) -> "Activation[T]":
		ar = Activation(static_link, RootFrame(), module)
		for udf in module.top_subs:
			ar.declare(udf)
		for uda in module.actor_definitions:
			ar.declare(uda)
		return ar

	@staticmethod
	def for_do_block(static_link: Frame[T]) -> "Activation[T]":
		return Activation(static_link, static_link, None)

