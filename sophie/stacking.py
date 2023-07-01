"""
This is supposed to be a support module for anything that smells of executing code.
Because Sophie's type-checking philosophy is "run the program over the types",
that means these activation records get used in both the type-checker and the evaluator.

For now I've removed the complexity of tracking static depth.
Sophie does run a little slower this way, but it's for a purpose.
Upon this simplified foundation, I'll build as needed to properly reflect
the upcoming message-passing semantics.
"""

from typing import TypeVar, Generic, Optional
from pathlib import Path
from .ontology import Symbol
from .syntax import UserDefinedFunction, ValExpr

T = TypeVar("T")

PLACE_HOLDER = object()

class StackFrame(Generic[T]):
	_bindings : dict[Symbol, T]
	pc : ValExpr
	def path(self) -> Path:
		raise NotImplementedError(type(self))
	def chase(self, key:Symbol) -> "StackFrame[T]":
		raise NotImplementedError(type(self))
	def dump(self):
		raise NotImplementedError(type(self))
	def trace(self, tracer):
		raise NotImplementedError(type(self))
	def hold_place_for(self, key:Symbol):
		assert key not in self._bindings, key
		self._bindings[key] = PLACE_HOLDER
	def install(self, key:Symbol, value):
		self._bindings[key] = value
		return value
	def fetch(self, key:Symbol):
		item = self._bindings[key]
		if item is PLACE_HOLDER: raise KeyError(item)
		else: return item

class RootFrame(StackFrame):
	"""The runtime counterpart to primitive-root namespace"""
	def __init__(self):
		self._bindings = {}
	def path(self) -> Path:
		pass
	def chase(self, key:Symbol) -> "StackFrame[T]":
		assert key in self._bindings, key  # Name resolution succeeded.
		return self
	def dump(self):
		print("-- Stack bottom --")
	def trace(self, tracer):
		pass

class ModuleFrame(StackFrame):
	def __init__(self, root:RootFrame, source_path:Optional[Path]):
		self._root = root
		self._path = source_path
		self._bindings = {}
	def path(self):
		return self._path
	def chase(self, key:Symbol) -> StackFrame[T]:
		return self if key in self._bindings else self._root.chase(key)
	def dump(self):
		print("-- %s --"%self._path)
		print(list(self._bindings))
	def trace(self, tracer):
		if hasattr(self, "pc"): tracer.called_from(self.path(), self.pc.head())

class FunctionFrame(StackFrame):
	def __init__(self, udf: UserDefinedFunction, static_link: StackFrame[T], arguments):
		self.udf = udf
		self.static_link = static_link
		self._bindings = dict(zip(udf.params, arguments))
		for key in udf.where:
			self.hold_place_for(key)
	def path(self):
		return self.udf.source_path
	def chase(self, key:Symbol) -> StackFrame[T]:
		return self if key in self._bindings else self.static_link.chase(key)
	def dump(self):
		print("-- %s : %s --"%(self.udf, self.path()))
		print(list(self._bindings))
	def trace(self, tracer):
		if hasattr(self, "pc"):
			tracer.called_from(self.path(), self.pc.head())
		tracer.called_with(self.path(), self.udf.head(), self._bindings)

