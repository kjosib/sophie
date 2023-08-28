import traceback
from typing import Any, Union, Sequence, Optional
from . import syntax, primitive
from .stacking import Frame, Activation
from .scheduler import MAIN_QUEUE, Task, Actor

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
	return evaluate(sequel, dynamic_env)

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
	return evaluate(branch, dynamic_env)

def _eval_do_block(expr:syntax.DoBlock, dynamic_env:ENV):
	return CompoundAction(expr, dynamic_env)

def _eval_bind_method(expr:syntax.BindMethod, dynamic_env:ENV):
	return BoundMethod(_strict(expr.receiver, dynamic_env), expr.method_name.text)

def _eval_as_task(expr:syntax.AsTask, dynamic_env:ENV):
	sub = _strict(expr.sub, dynamic_env)
	if isinstance(sub, Closure):
		return ClosureMessage(sub)
	else:
		assert isinstance(sub, Action), type(sub)
		assert not isinstance(sub, BoundMethod)
		return PlainTask(sub)

###############################################################################

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

class Function:
	""" A run-time object that can be applied with arguments. """
	def apply(self, args: Sequence[LAZY_VALUE]) -> Any:
		# It must be a LAZY_VALUE and not a syntax.ValExpr
		# lest various internal things fail to work,
		# which things to not tie back to specific syntax objects.
		# For example, explicit lists.
		raise NotImplementedError

class Closure(Function):
	""" The run-time manifestation of a sub-function: a callable value tied to its natal environment. """

	def __init__(self, static_link:ENV, udf:syntax.UserFunction):
		self._static_link = static_link
		self._udf = udf
	
	def _name(self): return self._udf.nom.text

	def apply(self, args: Sequence[LAZY_VALUE]) -> LAZY_VALUE:
		inner_env = Activation.for_function(self._static_link, self._udf, args)
		return evaluate(self._udf.expr, inner_env)

class Primitive(Function):
	""" All parameters to primitive procedures are strict. Also a kind of value, like a closure. """
	def __init__(self, fn: callable):
		self._fn = fn
	
	def apply(self, args: Sequence[LAZY_VALUE]) -> STRICT_VALUE:
		return self._fn(*map(force, args))

class Constructor(Function):
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

###############################################################################

class Action:
	def perform(self):
		""" Do something here and now in the current thread. """
		raise NotImplementedError(type(self))

class Nop(Action):
	def perform(self): pass

class CompoundAction(Action):
	def __init__(self, block:syntax.DoBlock, dynamic_env:ENV):
		self._block = block
		self._dynamic_env = dynamic_env
	def perform(self):
		agents = self._block.agents
		if agents:
			env = Activation.for_do_block(self._dynamic_env)
			for na in agents:
				assert isinstance(na, syntax.NewAgent)
				template = _strict(na.expr, self._dynamic_env)
				env.assign(na, template.instantiate())
		else:
			env = self._dynamic_env
		# TODO: Solve the tail-recursion problem.
		for expr in self._block.steps:
			env.pc = expr
			action = _strict(expr, self._dynamic_env)
			action.perform()

class BoundMessage(Action):
	def __init__(self, receiver, method_name, *args):
		self._receiver = receiver
		self._method_name = method_name
		self._args = args
		
	def perform(self):
		self._receiver.accept_message(self._method_name, self._args)

class TaskAction(Action):
	def __init__(self, task:Task):
		self._task = task
	def perform(self):
		MAIN_QUEUE.insert_task(self._task)

###############################################################################

class Message(Function):
	""" Interface for things that, with arguments, become messages ready to send. """
	def dispatch_with(self, *args):
		self.apply(args).perform()

class BoundMethod(Message, Action):
	def __init__(self, receiver, method_name):
		self._receiver = receiver
		self._method_name = method_name

	def apply(self, args: Sequence[LAZY_VALUE]) -> LAZY_VALUE:
		return BoundMessage(self._receiver, self._method_name, *(force(a) for a in args))
	
	def perform(self):
		""" Hack so that a single runtime class handles both parametric and non-parametric messages to actors """
		self._receiver.accept_message(self._method_name, ())

class ClosureMessage(Message):
	def __init__(self, closure: Closure):
		self._closure = closure

	def apply(self, args: Sequence[LAZY_VALUE]) -> Any:
		task = ParametricTask(self._closure, [force(a) for a in args])
		return TaskAction(task)
	
###############################################################################

class PlainTask(Task):
	def __init__(self, action:Action):
		self._action = action
	def proceed(self):
		self._action.perform()

class ParametricTask(Task):
	def __init__(self, closure:Closure, args:Sequence[STRICT_VALUE]):
		self._closure = closure
		self._args = args
	def proceed(self):
		action = force(self._closure.apply(self._args))
		assert isinstance(action, Action), type(action)
		action.perform()

class UserDefinedActor(Actor):
	
	def __init__(self, vtable:dict, private_state:dict):
		super().__init__()
		self._vtable = vtable
		self._private_state = private_state
	
	def handle(self, message, args):
		behavior = self._vtable[message]
		if args: behavior.apply(args).perform()
		else: behavior.perform()

###############################################################################

NIL:Optional[dict] = None # Gets replaced at runtime.
CONS:Constructor

def iterate_list(lst:LAZY_VALUE):
	lst = force(lst)
	while lst is not NIL:
		yield force(lst['head'])
		lst = force(lst['tail'])

###############################################################################


