"""
The generic machinery that everything needs,
without the specific methods corresponding to particular syntax.
"""

from typing import Union
from .. import syntax
from .types import SophieValue, LAZY_VALUE, STRICT_VALUE, ENV


EVALUABLE = Union[syntax.ValueExpression, syntax.Reference]


def evaluate(expr:EVALUABLE, frame:ENV) -> LAZY_VALUE:
	assert isinstance(frame, dict), frame
	try: fn = EVALUATE[type(expr)]
	except KeyError: raise NotImplementedError(type(expr), expr)
	return fn(expr, frame)

_NO_DELAY = {syntax.Literal, syntax.Lookup, syntax.DoBlock, syntax.LambdaForm}

def delay(expr: syntax.ValueExpression, frame: ENV) -> LAZY_VALUE:
	# For certain kinds of expression, there is no profit to delay:
	if type(expr) in _NO_DELAY: return evaluate(expr, frame)
	# In less trivial cases, make a thunk and pass that instead.
	return Thunk(expr, frame)

def force(it:LAZY_VALUE) -> STRICT_VALUE:
	"""
	Force repeatedly until the result is no longer a thunk, then return that result.
	This simulates tail-call elimination, now that closures promptly return thunks.
	"""
	while isinstance(it, Thunk): it = it.force()
	return it

EVALUATE = {}

def attach_evaluation_methods(python_scope):
	for _k, _v in list(python_scope.items()):
		if _k.startswith("_eval_"):
			_t = _v.__annotations__["expr"]
			assert isinstance(_t, type), (_k, _t)
			EVALUATE[_t] = _v


_ABSENT = object()


class Thunk(SophieValue):
	""" A kind of not-yet-value which can be forced. """
	def __init__(self, expr: syntax.ValueExpression, frame:ENV):
		assert isinstance(expr, syntax.ValueExpression), type(expr)
		self.expr = expr
		self.frame = frame
		self.value = _ABSENT
	
	def __str__(self):
		if self.value is _ABSENT:
			return "<Thunk: %s>" % self.expr
		else:
			return str(self.value)
	
	def force(self):
		if self.value is _ABSENT:
			self.value = evaluate(self.expr, self.frame)
			del self.expr
			del self.frame
		return self.value
	
def perform(action):
	# In principle, you could schedule a function that
	# evaluates to a reference to a procedure.
	# Then, the function's .perform returns the procedure,
	# and the procedure's .perform returns None,
	# which is internally our cue that the job's done.
	while action is not None:
		action = force(action).perform()

