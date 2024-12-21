from typing import NamedTuple, Optional, Sequence
from boozetools.support.foundation import Visitor
from ..syntax import TypeSymbol, TypeCase
from .promotion import PromotionFinder
from .domain import (
	SophieType, InferenceVariable, Error, BOTTOM, ACTION,
	SymbolicType, ArrowType, Closure, DynamicDispatch,
	MessageType, ParametricTask,
)

class Mismatch(NamedTuple):
	need: SophieType
	got: SophieType

class PlausibleCover(Visitor):
	"""
	Right now, the chief operating mode is to determine plausibility.
	That means that what is too difficult to check, we do not check.
	The goal is to catch about what an awake programmer would catch,
	based on annotations alone.
	
	This treats the type on the left as a pattern to match with the type
	on the right. If it matches, we want the bindings that made it so.
	Those bindings may end up being a union of several types, if the
	same variable appears more than once in a pattern.
	"""
	
	bindings : dict[InferenceVariable, SophieType]   # Describe the formals
	mismatch : Optional[Mismatch]
	
	def __init__(self, engine):
		self._engine = engine
		self.bindings = {}
		self.mismatch = None
		self.stack = []

	def tour(self, formals:Sequence[SophieType], actuals:Sequence[SophieType]):
		assert len(formals) == len(actuals)
		for f, a in zip(formals, actuals):
			if self.is_ok():
				self.bind(f, a)
	
	def bind(self, formal:SophieType, actual:SophieType):
		assert not actual.is_error()
		if actual is not BOTTOM: self.visit(formal, actual)
	
	def push(self):
		self.stack.append(dict(self.bindings))
	
	def pop(self):
		self.bindings = self.stack.pop()
	
	def fail(self, formal, actual):
		self.mismatch = Mismatch(formal, actual)
	
	def visit_InferenceVariable(self, formal:InferenceVariable, actual:SophieType):
		if formal in self.bindings:
			union = _union_type(self.bindings[formal], actual)
			if union.is_error():
				self.fail(self.bindings[formal], actual)
			else:
				self.bindings[formal] = union
		else:
			self.bindings[formal] = actual
	
	def is_ok(self): return self.mismatch is None
	
	def visit_SymbolicType(self, formal:SymbolicType, actual:SophieType):
		if isinstance(actual, SymbolicType) and _is_supertype(formal.symbol, actual.symbol):
			self.tour(formal.type_args, actual.type_args)
		else:
			self.fail(formal, actual)
	
	def visit_ArrowType(self, formal:ArrowType, actual:SophieType):
		if actual.value_arity() == formal.value_arity():
			if isinstance(actual, DynamicDispatch):
				# FIXME: This is sub-optimal.
				#  If an inference variable is otherwise bound to some particular type,
				#  then we should be able to use that fact in the dispatch decision.
				#  Perhaps a future version can delay the question until there's more
				#  information derived in other ways.
				implementation = actual.dispatch(formal.arg_types)
				if implementation is None:
					self.fail(formal, actual)
					return
				else:
					actual = implementation
			if isinstance(actual, ArrowType):
				self.push()
				self.tour(actual.arg_types, formal.arg_types)
				result = actual.result_type.rewrite(self.bindings)
				self.pop()
				if self.is_ok(): self.bind(formal.result_type, result)
				return
			if isinstance(actual, Closure):
				# The hazard here is storing closures into fields or passing them to FFI things:
				# Something needs to make sure that's safe.
				if self._engine:
					result = self._engine.apply_closure(actual, formal.arg_types, PlausibleCover(None))
					self.bind(formal.result_type, result)
				return
		self.fail(formal, actual)
	
	def visit_MessageType(self, formal:MessageType, actual:SophieType):
		if actual.value_arity() == formal.value_arity():
			if isinstance(actual, MessageType):
				self.push()
				self.tour(actual.arg_types, formal.arg_types)
				self.pop()
				return
			if isinstance(actual, ParametricTask):
				if self._engine:
					step = self._engine.apply_closure(actual.closure, formal.arg_types, PlausibleCover(None))
					result = self._engine.perform(step)
					if result.is_error(): return  # Have already complained.
					if result is not ACTION: self.fail(formal, actual)
				return
		self.fail(formal, actual)



def _is_supertype(formal:TypeSymbol, actual:TypeSymbol):
	if formal is actual: return True
	if isinstance(actual, TypeCase) and actual.variant is formal: return True
	return False

def _union_type(t1, t2) -> SophieType:
	uf = PromotionFinder(t1)
	uf.unify_with(t2)
	return uf.result()

