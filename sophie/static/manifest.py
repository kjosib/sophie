"""
Type Declarations -- Symbols -- provide the definitions of words used in type syntax.
Type Expressions -- Syntaxes -- express literal values in the way that "11" expresses eleven-ness.
Certain operations transform types in ways that syntax per-se will never represent.
Therefore, the convenient thing to do is have a way to map syntax into SophieType.

Much of type-checking amounts to the question whether a particular
concrete type -- with no "free variables", so to speak, fits the
constraint of some certain type-expression in the syntax.

This amounts to a sort of parallel tree-walk: On the left hand side,
we have a pattern; on the right, a match-candidate: both SophieType.

"""

from typing import Sequence
from boozetools.support.foundation import Visitor
from ..ontology import TypeExpression, TypeSymbol
from ..syntax import (
	TypeParameter, TypeAliasSymbol, TypeDefinition, RecordSpec,
	TypeCall, ArrowSpec, TypeCapture, MessageSpec
)
from .domain import SophieType, InferenceVariable, SymbolicType, ArrowType, MessageType

def translate(tps:Sequence[TypeParameter], tx:TypeExpression) -> SophieType:
	assert all(isinstance(p, TypeParameter) for p in tps)
	assert isinstance(tx, TypeExpression)
	gamma = {p:InferenceVariable() for p in tps}
	return Translator(gamma).visit(tx)

def constructor(tps:Sequence[TypeParameter], spec:RecordSpec, type_dfn:TypeSymbol):
	assert all(isinstance(p, TypeParameter) for p in tps)
	type_args = [InferenceVariable() for p in tps]
	gamma = dict(zip(tps, type_args))
	translator = Translator(gamma)
	args = [translator.visit(f.type_expr) for f in spec.fields]
	result = SymbolicType(type_dfn, type_args)
	return ArrowType(args, result)

class Translator(Visitor):
	_gamma:dict[TypeParameter, SophieType]
	def __init__(self, gamma:dict[TypeParameter, SophieType]):
		self._gamma = gamma
	
	def tour(self, items): return tuple(map(self.visit, items))
	
	def visit_TypeCall(self, tc:TypeCall):
		symbol = tc.ref.dfn
		if isinstance(symbol, TypeParameter):
			assert not tc.arguments
			return self.capture(symbol)
		else:
			assert isinstance(symbol, TypeDefinition)
			args = self.tour(tc.arguments) or InferenceVariable.several(symbol.type_arity())
			if isinstance(symbol, TypeAliasSymbol):
				# For now, resolve all the aliases up front.
				# Eventually, this might get lazy in favor of smarter messages.
				gamma_prime = dict(zip(symbol.type_params, args))
				return Translator(gamma_prime).visit(symbol.type_expr)
			else:
				return SymbolicType(symbol, args)
	
	@staticmethod
	def visit_NoneType(_): return InferenceVariable()
	
	@staticmethod
	def visit_FreeType(_): return InferenceVariable()
	
	def visit_TypeCapture(self, cap:TypeCapture):
		return self.capture(cap.type_parameter)
	
	def capture(self, param:TypeParameter):
		if param not in self._gamma:
			self._gamma[param] = InferenceVariable()
		return self._gamma[param]
	
	def visit_ArrowSpec(self, sp:ArrowSpec):
		return ArrowType(self.tour(sp.lhs), self.visit(sp.rhs))
	
	def visit_MessageSpec(self, sp:MessageSpec):
		return MessageType(self.tour(sp.type_exprs))
	