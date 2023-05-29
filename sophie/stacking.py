from typing import TypeVar, Generic, Optional
from pathlib import Path
from .ontology import Symbol
from .syntax import UserDefinedFunction

T = TypeVar("T")

class StackFrame(Generic[T]):
	depth : int
	bindings : dict[Symbol, T]
	def path(self) -> Path:
		raise NotImplementedError(type(self))
	def chase(self, target:Symbol) -> "StackFrame[T]":
		raise NotImplementedError(type(self))

class StackBottom(StackFrame):
	depth = 0
	def __init__(self, source_path:Optional[Path]):
		self.current_path = source_path
		self.bindings = {}
	def path(self):
		return self.current_path
	def chase(self, target:Symbol) -> "StackFrame[T]":
		return self

class ActivationRecord(StackFrame):
	def __init__(self, udf:UserDefinedFunction, static_link:StackFrame[T], arguments):
		self.udf = udf
		self.static_link = static_link
		self.depth = static_link.depth + 1
		self.bindings = dict(zip(udf.params, arguments))
	def path(self):
		return self.udf.source_path
	def chase(self, target:Symbol) -> "StackFrame[T]":
		for _ in range(self.depth - target.static_depth):
			self = self.static_link
		return self
	