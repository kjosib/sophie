import traceback
from typing import Any, Union, Sequence, Optional
from collections import deque
from . import syntax, primitive
from .stacking import Frame, Activation

STRICT_VALUE = Union[
	int, float, str, dict,
	"Procedure", "BoundMethod", "Message", "Step",
]
LAZY_VALUE = Union[STRICT_VALUE, "Thunk"]
ENV = Frame[LAZY_VALUE]

###############################################################################

ABSENT = object()
class Thunk:
	""" A kind of not-yet-value which can be forced. """
	def __init__(self, dynamic_env:ENV, expr: syntax.ValExpr):
		assert isinstance(expr, syntax.ValExpr), type(expr)
		self._dynamic_env = dynamic_env
		self._expr = expr
		self._value = ABSENT
		
	def force(self) -> STRICT_VALUE:
		if self._value is ABSENT:
			self._value = _strict(self._expr, self._dynamic_env)
			assert not isinstance(self._value, syntax.ValExpr), type(self._expr)
			del self._dynamic_env, self._expr
		return self._value
	
	def __str__(self):
		if self._value is ABSENT:
			return "<Thunk: %s>"%self._expr
		else:
			return str(self._value)

def force(it:LAZY_VALUE) -> STRICT_VALUE:
	"""
	While this will not return a thunk as such,
	it may return a structure which contains thunks.
	"""
	while isinstance(it, Thunk):
		it = it.force()
	return it

def _strict(expr:syntax.ValExpr, dynamic_env:ENV):
	return force(evaluate(expr, dynamic_env))

###############################################################################

def _eval_literal(expr:syntax.Literal, dynamic_env:ENV):
	return expr.value

def _eval_lookup(expr:syntax.Lookup, dynamic_env:ENV):
	sym = expr.ref.dfn
	static_env = dynamic_env.chase(sym)
	try: return static_env.fetch(sym)
	except KeyError:
		if isinstance(sym, syntax.UserFunction):
			if sym.params:
				value = Closure(static_env, sym)
			else:
				inner = Activation.for_function(static_env, sym, ())
				value = delay(inner, sym.expr)
		elif isinstance(sym, syntax.TypeAlias):
			value = _snap_type_alias(sym, static_env)
		else:
			assert False, type(sym)
		return static_env.assign(sym, value)

def _eval_bin_exp(expr:syntax.BinExp, dynamic_env:ENV):
	return OPS[expr.glyph](_strict(expr.lhs, dynamic_env), _strict(expr.rhs, dynamic_env))

def _eval_unary_exp(expr:syntax.UnaryExp, dynamic_env:ENV):
	return OPS[expr.glyph](_strict(expr.arg, dynamic_env))

def _eval_shortcut_exp(expr:syntax.ShortCutExp, dynamic_env:ENV):
	lhs = _strict(expr.lhs, dynamic_env)
	assert isinstance(lhs, bool)
	return lhs if lhs == OPS[expr.glyph] else _strict(expr.rhs, dynamic_env)

def _eval_call(expr:syntax.Call, dynamic_env:ENV):
	procedure = _strict(expr.fn_exp, dynamic_env)
	thunks = tuple(delay(dynamic_env, a) for a in expr.args)
	return procedure.apply(thunks)

def _eval_cond(expr:syntax.Cond, dynamic_env:ENV):
	if_part = _strict(expr.if_part, dynamic_env)
	sequel = expr.then_part if if_part else expr.else_part
	return delay(dynamic_env, sequel)

def _eval_field_ref(expr:syntax.FieldReference, dynamic_env:ENV):
	lhs = _strict(expr.lhs, dynamic_env)
	key = expr.field_name.text
	if isinstance(lhs, dict):
		return lhs[key]
	else:
		return getattr(lhs, key)

def _eval_explicit_list(expr:syntax.ExplicitList, dynamic_env:ENV):
	tail = NIL
	for sx in reversed(expr.elts):
		head = delay(dynamic_env, sx)
		tail = CONS.apply((head, tail))
	return tail

def _eval_match_expr(expr:syntax.MatchExpr, dynamic_env:ENV):
	subject = dynamic_env.assign(expr.subject, _strict(expr.subject.expr, dynamic_env))
	tag = subject[""]
	try:
		branch = expr.dispatch[tag]
	except KeyError:
		branch = expr.otherwise
		if branch is None:
			raise RuntimeError("Confused by tag %r; should not be possible now that type-checking works."%tag)
	return delay(dynamic_env, branch)

def _eval_do_block(expr:syntax.DoBlock, dynamic_env:ENV):
	return CompoundStep(expr.steps, dynamic_env)

def _eval_bind_method(expr:syntax.BoundMethod, dynamic_env:ENV):
	return Method(_strict(expr.receiver, dynamic_env), expr.method_name.text)

def _snap_type_alias(alias:syntax.TypeAlias, global_env:ENV):
	# It helps to remember this is a run-time thing so type-parameters are irrelevant here.
	assert isinstance(alias.body, syntax.TypeCall)  # resolution.check_constructors guarantees this.
	dfn = alias.body.ref.dfn
	try: return global_env.fetch(dfn)
	except KeyError:
		assert isinstance(dfn, syntax.TypeAlias)
		return global_env.assign(dfn, _snap_type_alias(dfn, global_env))

EVALUABLE = Union[syntax.ValExpr, syntax.Reference]

def evaluate(expr:EVALUABLE, dynamic_env:ENV) -> LAZY_VALUE:
	assert isinstance(dynamic_env, Frame), type(dynamic_env)
	try: fn = EVALUATE[type(expr)]
	except KeyError: raise NotImplementedError(type(expr), expr)
	try: return fn(expr, dynamic_env)
	except Exception:
		traceback.print_exc()
		# for frame in THE_STACK:
		# 	frame.trace(tracer)
		exit(1)

def delay(dynamic_env:ENV, expr:syntax.ValExpr) -> LAZY_VALUE:
	# For two kinds of expression, there is no profit to delay:
	if isinstance(expr, syntax.Literal): return expr.value
	if isinstance(expr, syntax.Lookup): return _eval_lookup(expr, dynamic_env)
	# In less trivial cases, make a thunk and pass that instead.
	return Thunk(dynamic_env, expr)

EVALUATE = {}
for _k, _v in list(globals().items()):
	if _k.startswith("_eval_"):
		_t = _v.__annotations__["expr"]
		assert isinstance(_t, type), (_k, _t)
		EVALUATE[_t] = _v
OPS = {glyph:op for glyph, (op, typ) in primitive.ops.items()}

###############################################################################

class Procedure:
	""" A run-time object that can be applied with arguments. """
	def apply(self, args: Sequence[LAZY_VALUE]) -> Any:
		# It must be a LAZY_VALUE and not a syntax.ValExpr
		# lest various internal things fail to work,
		# which things to not tie back to specific syntax objects.
		# For example, explicit lists.
		raise NotImplementedError

class Closure(Procedure):
	""" The run-time manifestation of a sub-function: a callable value tied to its natal environment. """

	def __init__(self, static_link:ENV, udf:syntax.UserFunction):
		self._static_link = static_link
		self._udf = udf
	
	def _name(self): return self._udf.nom.text

	def apply(self, args: Sequence[LAZY_VALUE]) -> LAZY_VALUE:
		inner_env = Activation.for_function(self._static_link, self._udf, args)
		return evaluate(self._udf.expr, inner_env)

class Primitive(Procedure):
	""" All parameters to primitive procedures are strict. Also a kind of value, like a closure. """
	def __init__(self, fn: callable):
		self._fn = fn
	
	def apply(self, args: Sequence[LAZY_VALUE]) -> STRICT_VALUE:
		return self._fn(*map(force, args))

class Constructor(Procedure):
	def __init__(self, key:str, fields:list[str]):
		self.key = key
		self.fields = fields
	
	def apply(self, args: Sequence[LAZY_VALUE]) -> Any:
		# TODO: It would be well to handle tagged values as Python pairs.
		#  This way any value could be tagged, and various case-matching
		#  things could work more nicely (and completely).
		assert len(args) == len(self.fields)
		structure = {"": self.key}
		for field, arg in zip(self.fields, args):
			assert not isinstance(arg, syntax.ValExpr)
			structure[field] = arg
		return structure

class NativeObjectProxy:
	""" Wrap Python objects in one of these to use them as actors. """
	def __init__(self, principal):
		self._principal = principal
	def receive(self, method_name, args):
		method = getattr(self._principal, method_name)
		method(*args)

###############################################################################

class ParametricTask(Procedure):
	def __init__(self, closure):
		self._closure = closure
	def apply(self, args: Sequence[LAZY_VALUE]) -> Any:
		return ClosureMessage(self._closure, *(promote(a) for a in args))

class Method(Procedure):
	def __init__(self, receiver, method_name):
		self._receiver = receiver
		self._method_name = method_name
	def apply(self, args: Sequence[LAZY_VALUE]) -> LAZY_VALUE:
		return MethodMessage(self._receiver, self._method_name, *(promote(a) for a in args))
	def run(self):
		# Mild hack r/n...
		self.apply(()).run()

def promote(arg):
	# Convert a closure to a task, but all other things stay the same.
	it = force(arg)
	if isinstance(it, Closure): return ParametricTask(it)
	else: return it


###############################################################################

class Step:
	def run(self):
		raise NotImplementedError(type(self))

class Nop(Step):
	def run(self): pass

class CompoundStep(Step):
	def __init__(self, steps:Sequence[syntax.ValExpr], dynamic_env:ENV):
		self._steps = steps
		self._dynamic_env = dynamic_env
	def run(self):
		# TODO: Solve the tail-recursion problem.
		env = self._dynamic_env
		for expr in self._steps:
			env.pc = expr
			step = _strict(expr, self._dynamic_env)
			step.run()


###############################################################################

THE_QUEUE = deque()

def drain_queue():
	while THE_QUEUE:
		message = THE_QUEUE.popleft()
		# print("  -> Dequeue", message)
		message.proceed()

class Message(Step):
	def run(self):
		# print("  <- Enqueue", self)
		assert hasattr(self, "proceed")
		THE_QUEUE.append(self)
	def proceed(self):
		raise NotImplementedError(type(self))

class ClosureMessage(Message):
	def __init__(self, closure:Procedure, *args):
		self._closure = closure
		self._args = args
	def proceed(self):
		thunk = self._closure.apply(self._args)
		step = force(thunk)
		step.run()

class SimpleTask(Message):
	def __init__(self, thunk):
		self._thunk = thunk
	def proceed(self):
		step = force(self._thunk)
		step.run()

class MethodMessage(Message):
	def __init__(self, receiver, method_name, *args):
		self._receiver = receiver
		self._method_name = method_name
		self._args = args
	def proceed(self):
		self._receiver.receive(self._method_name, self._args)

###############################################################################

NIL:Optional[dict] = None # Gets replaced at runtime.
CONS:Constructor

def iterate_list(lst:LAZY_VALUE):
	lst = force(lst)
	while lst is not NIL:
		yield force(lst['head'])
		lst = force(lst['tail'])

###############################################################################
#
#  Give the console object run-time teeth

import sys
import random

class Console:
	@staticmethod
	def echo(text):
		for fragment in iterate_list(text):
			sys.stdout.write(fragment)
		sys.stdout.flush()

	@staticmethod
	def read(target:Procedure):
		message = target.apply([input()])
		message.run()

	@staticmethod
	def random(target:Procedure):
		message = target.apply([random.random()])
		message.run()

primitive.root_namespace['console'].val = NativeObjectProxy(Console())

###############################################################################


