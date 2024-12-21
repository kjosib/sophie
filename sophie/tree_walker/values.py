"""
This module defines the specialized value-types that the tree-walker operates in terms of.
Basic primitive values play themselves, but special things like closures need more help.
"""
from abc import abstractmethod
from typing import Iterable
from ..ontology import SELF
from .. import syntax
from .scheduler import Task, Actor, per_thread
from .types import ARGS, STRICT_VALUE, SophieValue, ENV, STRICT_ARGS, LAZY_VALUE
from .evaluator import force, evaluate, perform, delay

def _frame(sub:syntax.Subroutine, args: ARGS) -> ENV:
	assert len(sub.params) == len(args), (sub, args)
	frame = dict(zip(sub.params, args))
	close(frame, sub.where)
	return frame

def close(frame:ENV, where:Iterable[syntax.Subroutine]):
	for sub in where:
		frame[sub] = delay(sub.expr, frame) if sub.is_thunk() else Closure(sub)
	for sub in where:
		if sub.is_thunk(): close(frame, sub.where)
		else: frame[sub].perform_capture(frame) # NOQA

###############################################################################

class Function(SophieValue):
	""" A run-time object that can be applied with arguments. """
	@abstractmethod
	def apply(self, args: ARGS) -> LAZY_VALUE: pass
	pass

class Closure(Function):
	""" The run-time manifestation of a sub-function: a callable value tied to its natal environment. """
	# The same Closure type serves for both functions and procedures.
	_captures: ENV
	
	def __init__(self, sub: syntax.Subroutine):
		self._sub = sub
	
	def perform_capture(self, frame:ENV):
		self._captures = {sym:frame[sym] for sym in self._sub.captures}
	
	def __str__(self):
		return str(self._sub)
	
	def _name(self): return self._sub.nom.text
	
	def apply(self, args: ARGS) -> LAZY_VALUE:
		for i in self._sub.strictures: force(args[i])
		inner = dict(zip(self._sub.params, args))
		inner.update(self._captures)
		close(inner, self._sub.where)
		
		# Important Tech Note:
		# 
		# We return a thunk here (via `delay`) instead of directly
		# evaluating the expression (via `evaluate`) in order to
		# emulate tail-call elimination and avoid stack overflow.
		
		return delay(self._sub.expr, inner) 
	
	def perform(self): return self.apply(())
	
	def as_task(self):
		return ParametricTask(self) if self._sub.params else PlainTask(self, ())

class Primitive(Function):
	""" All parameters to primitive procedures are strict. Also a kind of value, like a closure. """
	def __init__(self, fn: callable):
		self._fn = fn
	
	def apply(self, args: ARGS) -> STRICT_VALUE:
		return self._fn(*map(force, args))

class Constructor(Function):
	def __init__(self, key: syntax.Symbol, fields: list[str]):
		self.key = key
		self.fields = fields
	
	def apply(self, args: ARGS) -> STRICT_VALUE:
		# TODO: It would be well to handle tagged values as Python pairs.
		#  This way any value could be tagged, and various case-matching
		#  things could work more nicely (and completely).
		assert len(args) == len(self.fields)
		structure = dict(zip(self.fields, args))
		structure[""] = self.key
		return structure

class ActorClass(Function):
	def __init__(self, uda: syntax.UserActor):
		self._uda = uda
	
	def apply(self, args: ARGS) -> "ActorTemplate":
		assert len(args) == len(self._uda.fields)
		return ActorTemplate(self._uda, args)

class ActorTemplate(SophieValue):
	def __init__(self, uda: syntax.UserActor, args: ARGS):
		self._uda = uda
		self._args = args
	
	def instantiate(self):
		state = dict(zip(self._uda.fields, map(force, self._args)))
		vtable = self._uda.behavior_space._symbol
		return UserDefinedActor(state, vtable)

class UserDefinedActor(Actor):
	def __init__(self, state: dict, vtable: dict):
		super().__init__()
		self.state = state
		self.state[SELF] = self
		self._vtable = vtable
	
	def handle(self, message, args):
		behavior = self._vtable[message]
		frame = _frame(behavior, args)
		frame.update(self.state)
		per_thread.current_actor = self
		perform(evaluate(behavior.expr, frame))

###############################################################################

class MessageTask:
	def __init__(self, receiver, method_name, args: STRICT_ARGS):
		self._receiver = receiver
		self._method_name = method_name
		self._args = args
	
	def perform(self):
		self._receiver.accept_message(self._method_name, self._args)

class PlainTask(Task):
	def __init__(self, closure: Closure, args: STRICT_ARGS):
		self._closure = closure
		self._args = args
	
	def perform(self):
		self.enqueue()
	
	def proceed(self):
		perform(self._closure.apply(self._args))

###############################################################################

class ParametricMessage(Function):
	""" Interface for things that, with arguments, become messages ready to send. """
	def dispatch_with(self, *args):
		perform(self.apply(args))
	
	@abstractmethod
	def apply(self, args: ARGS) -> LAZY_VALUE: pass

class ParametricTask(ParametricMessage):
	def __init__(self, closure: Closure):
		self._closure = closure
	
	def apply(self, args: ARGS) -> PlainTask:
		return PlainTask(self._closure, tuple(force(a) for a in args))

class BoundMethod(ParametricMessage):
	def __init__(self, receiver, method_name):
		self._receiver = receiver
		self._method_name = method_name
	
	def apply(self, args: ARGS) -> MessageTask:
		return MessageTask(self._receiver, self._method_name, tuple(force(a) for a in args))
	
	def perform(self):
		self.apply(()).perform()
