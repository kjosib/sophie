"""
The Algebra of Type Checking
=============================

In the new world order:

The SophieType class hierarchy represents type judgements.
Think of them as "abstract values" in the same sense that
Sophie's type-checker is based on abstract-interpretation.

---------------------------------------------------------------------------
"""

from typing import Sequence
from ..ontology import SELF, TypeSymbol
from ..syntax import Subroutine, UserActor, UserOperator, UserProcedure
from ..stacking import Frame,RootFrame, Activation

_TYPE_NUMBERING = {}

class SophieType:
	equivalence_class: int
	
	def __init__(self, domain_key):
		type_key = (type(self), domain_key)
		try:
			self.equivalence_class = _TYPE_NUMBERING[type_key]
		except KeyError:
			self.equivalence_class = _TYPE_NUMBERING[type_key] = len(_TYPE_NUMBERING)
	
	def value_arity(self) -> int:
		# Most things are not callable.
		return -1
	def token(self) -> TypeSymbol:
		raise NotImplementedError(type(self))
	
	def rewrite(self, gamma:dict["InferenceVariable", "SophieType"]) -> "SophieType":
		raise NotImplementedError(type(self))
	
	def __repr__(self) -> str:
		return self.render({})
	
	def render(self, delta:dict["InferenceVariable", str]) -> str:
		raise NotImplementedError(type(self))
	
	def dispatch_signature(self) -> tuple[TypeSymbol, ...]:
		raise NotImplementedError(type(self))
	
	def is_error(self): return False
	pass

TYP_ENV = Frame[SophieType]
_VOID = RootFrame[SophieType]()



def is_equivalent(s:SophieType, t:SophieType) -> bool:
	return s.equivalence_class == t.equivalence_class

def _common_key(head, components:Sequence[SophieType]):
	# Convenience for a few kinds of types
	return head, tuple(t.equivalence_class for t in components)

class InferenceVariable(SophieType):
	""" These have identity and are hashable, which does the job. """
	def __init__(self):
		# Current working theory: When we're doing an
		# equivalence check, it's with a "concrete" type.
		# If an inference variable is involved, then it's
		# a bug.
		super().__init__(self)
	def render(self, delta) -> str:
		if self not in delta: delta[self] = "$%d"%(1+len(delta))
		return delta[self]
	@staticmethod
	def several(nr:int):
		return tuple(InferenceVariable() for _ in range(nr))
	def rewrite(self, gamma) -> SophieType:
		return gamma.get(self, BOTTOM)

class SymbolicType(SophieType):
	""" The type that a TypeCall represents in type-expression context. """
	def __init__(self, symbol:TypeSymbol, type_args:Sequence[SophieType]):
		assert symbol.type_arity() == len(type_args), (symbol, type_args)
		assert all(isinstance(a, SophieType) for a in type_args)
		self.symbol = symbol
		self.type_args = type_args
		super().__init__(_common_key(symbol, type_args))
	def render(self, delta) -> str: return self.symbol.nom.text+_bracket("[", self.type_args, delta, "]")
	def rewrite(self, gamma) -> SophieType:
		return SymbolicType(self.symbol, _rewrite(self.type_args, gamma))
	def token(self) -> TypeSymbol: return self.symbol

def _rewrite(args, gamma):
	return tuple(a.rewrite(gamma) for a in args)

class ArrowType(SophieType):
	def __init__(self, arg_types:Sequence[SophieType], result_type:SophieType):
		self.arg_types, self.result_type = arg_types, result_type
		super().__init__(_common_key(result_type.equivalence_class, arg_types))
	def render(self, delta):
		return _bracket("(", self.arg_types, delta, ")") + "->" + self.result_type.render(delta)
	def value_arity(self):
		return len(self.arg_types)
	def dispatch_signature(self) -> tuple[TypeSymbol, ...]:
		return tuple(a.token() for a in self.arg_types)

class MessageType(SophieType):
	def __init__(self, arg_types:Sequence[SophieType]):
		self.arg_types = arg_types
		super().__init__(_common_key("message", arg_types))
	def render(self, delta):
		return "!"+_bracket("(", self.arg_types, delta, ")")
	def value_arity(self):
		return len(self.arg_types) or -1
	def dispatch_signature(self) -> tuple[TypeSymbol, ...]:
		return tuple(a.token() for a in self.arg_types) or "message"
	def rewrite(self, gamma) -> SophieType:
		return MessageType(_rewrite(self.arg_types, gamma))

def _bracket(bra, args, delta, ket):
	if args: return bra+ ", ".join(a.render(delta) for a in args)+ket
	else: return ""

class Closure(SophieType):
	# Suitable for user-defined functions, procedures, etc.
	capture_key : tuple[SophieType, ...]
	
	def __init__(self, sub:Subroutine, env:TYP_ENV):
		self.sub = sub
		self.capture_key = tuple(map(env.fetch, self.sub.memo_schedule.captures))
		super().__init__(_common_key(self.sub, self.capture_key))
		self.captured = {}  # Save for later: closures may capture peers.
	def perform_capture(self, env):
		# Needs to be in a second phase from construction,
		# because closures can capture each other mutually.
		for cap in self.sub.captures: self.captured[cap] = env.fetch(cap)
	def memo_key(self, actual_types) -> tuple:
		memo_args = tuple(actual_types[i].equivalence_class for i in self.sub.memo_schedule.arguments)
		return self.sub, self.capture_key, memo_args
	def value_arity(self) -> int: return len(self.sub.params)
	def render(self, _) -> str:
		return "{%s/%d}"%(self.sub.nom.text, len(self.sub.params))
	def dispatch_signature(self) -> tuple[TypeSymbol, ...]:
		assert isinstance(self.sub, UserOperator)
		return self.sub.dispatch_vector()

class DynamicDispatch(SophieType):
	# TODO: Invent syntax for declaring these things,
	#       and then for participating in them.
	def __init__(self, name:str, arity:int):
		self._name = name
		self._arity = arity
		self._cases = {}
		super().__init__(name)

	def value_arity(self) -> int: return self._arity
	
	def append_case(self, case:SophieType, report):
		assert case.value_arity() == self._arity
		arg_tokens = case.dispatch_signature()
		if arg_tokens in self._cases: report.conflicting_overload()
		elif not all(arg_tokens): report.unsuported_overrload()
		elif len(arg_tokens) != self._arity: report.conflicting_overload()
		else: self._cases[arg_tokens] = case
	
	def dispatch(self, arg_types:Sequence[SophieType]):
		arg_tokens = tuple(a.token() for a in arg_types)
		assert len(arg_tokens) == self._arity
		return self._cases.get(arg_tokens, None)
	
	def render(self, delta) -> str:
		return self._name

class ParametricTask(SophieType):
	""" The type of a task-ified user-defined (maybe-parametric) procedure. """
	def __init__(self, closure:Closure):
		assert isinstance(closure, Closure)
		assert closure.value_arity()
		assert isinstance(closure.sub, UserProcedure)
		super().__init__(closure.equivalence_class)
		self.closure = closure
	def value_arity(self) -> int: return self.closure.value_arity()
	def render(self, delta) -> str: return "!"+self.closure.render(delta)

class ParametricTpl(SophieType):
	def __init__(self, actor_dfn: UserActor):
		super().__init__(actor_dfn)
		self.actor_dfn = actor_dfn
	def value_arity(self) -> int: return len(self.actor_dfn.fields)

class ConcreteTpl(SophieType):
	def __init__(self, actor_dfn: UserActor, arg_types:Sequence[SophieType]):
		assert len(arg_types) == len(actor_dfn.fields)
		super().__init__(_common_key(actor_dfn, arg_types))
		self.actor_dfn = actor_dfn
		self.arg_types = arg_types
		self.fields = Activation(_VOID, actor_dfn)
		self.fields.assign(SELF, UDAType(self))
		self.fields.update(zip(actor_dfn.fields, arg_types))
		self.behavior = {
			b.nom.key(): Closure(b, self.fields)
			for b in actor_dfn.behaviors
		}
		for closure in self.behavior.values():
			closure.perform_capture(self.fields)
		
	def value_arity(self) -> int: return -1  # Not callable; instantiable.
	def render(self, delta) -> str:
		return "<template:%s%s>"%(self.actor_dfn.nom.text, _bracket("(", self.arg_types, delta, ")"))

class UDAType(SophieType):
	"""
	Has much in common with a subroutine type,
	except that the environment link here is going to contain
	the state of the actor itself. This is necessary because
	assignment statements can possibly cause state to promote.
	"""
	def __init__(self, tpl: ConcreteTpl):
		super().__init__(tpl.equivalence_class)
		self.tpl = tpl
	def value_arity(self) -> int: return -1  # Not callable
	def render(self, delta) -> str: return "{actor:%s}"%self.tpl.actor_dfn.nom.text

class Special(SophieType):
	def __init__(self, name:str):
		super().__init__(name)
		self._name = name
	def render(self, delta) -> str: return self._name
	def rewrite(self, gamma): return self

class Error(SophieType):
	def __init__(self, nature):
		super().__init__(None)
		print("Error:", nature)
		self.nature = nature
	def render(self, delta) -> str: return "<Error: %s>" % self.nature
	def is_error(self): return True

BOTTOM = Special("<BOTTOM>")
ACTION = Special("<ACTION>")
READY_MESSAGE = MessageType(())
ZERO_ARG_PROC = ArrowType((), ACTION)
