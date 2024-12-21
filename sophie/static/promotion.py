import sys
from typing import Sequence
from boozetools.support.foundation import Visitor
from .domain import (
	SophieType, SymbolicType, ArrowType, Closure, DynamicDispatch,
	Special, Error, BOTTOM, ACTION, ZERO_ARG_PROC, is_equivalent, READY_MESSAGE,
)
from ..syntax import TypeCase

class PromotionFinder(Visitor):
	"""
	This object embodies an algorithm to find a least-common-supertype
	among several constituents. That is, it discerns the smallest type
	which contains every value of any constituent type, and therefore
	provides only the *intersection* of their guarantees.
	
	Frequently enough, that type is ERROR.
	"""
	
	def __init__(self, first_typ):
		self._unifier = first_typ
	
	def result(self):
		return self._unifier
	
	def unify_with(self, typ: SophieType):
		self._unifier = self.do(self._unifier, typ)
	
	def parallel(self, these: Sequence[SophieType], those: Sequence[SophieType]):
		assert len(these) == len(those)
		return [self.do(a, b) for a, b in zip(these, those)]
	
	def do(self, this: SophieType, that: SophieType):
		if this.equivalence_class == that.equivalence_class: return this
		if isinstance(that, Special): return self.visit(that, this)
		return self.visit(this, that) or Error("32: %s is unrelated to %s"%(this, that))
	
	@staticmethod
	def visit_Error(this: Error, _:SophieType):
		print("I don't think this is even possible.", file=sys.stderr)
		return this
	
	@staticmethod
	def visit_Special(this: Special, that: SophieType):
		if this is BOTTOM: return that
		if this is ACTION:
			if that is BOTTOM: return ACTION
			if is_equivalent(that, ZERO_ARG_PROC): return ACTION
			if is_equivalent(that, READY_MESSAGE): return ACTION
			return Error("48: %s is not ACTION"%that)
	
	def visit_SymbolicType(self, this:SymbolicType, that:SophieType):
		goal = this.symbol
		if isinstance(that, SymbolicType):
			other = that.symbol
			if goal is not other:
				if isinstance(goal, TypeCase): goal = goal.variant
				if isinstance(other, TypeCase): other = other.variant
			if goal is other:
				return SymbolicType(goal, self.parallel(this.type_args, that.type_args))
	
	
	def visit_Closure(self, this: Closure, that: SophieType):
		if isinstance(that, (Closure, ArrowType, DynamicDispatch)):
			if this.value_arity() == that.value_arity():
				# In principle, we take the intersection of the parameters to the union of the results.
				# In practice, that means some sort of "try both" logic,
				# and it's entirely too complicated for a five-minute hack session.
				raise NotImplementedError("To do.")
