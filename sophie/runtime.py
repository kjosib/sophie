import operator
from typing import Any, Union, Sequence, Optional, Reversible
from . import syntax, primitive
from .ontology import SELF
from .stacking import Frame, Activation, RootFrame
from .scheduler import Task, Actor
from .diagnostics import trace_absurdity

def _compare(a,b):
	if a < b: return LESS
	if a == b: return SAME
	return MORE

PRIMITIVE_BINARY = {
	"^"   : operator.pow,
	"*"   : operator.mul,
	"/"   : operator.truediv,
	"DIV" : operator.floordiv,
	"MOD" : operator.mod,
	"+"   : operator.add,
	"-"   : operator.sub,
	"==" : operator.eq,
	"!=" : operator.ne,
	"<="  : operator.le,
	"<" : operator.lt,
	">="  : operator.ge,
	">" : operator.gt,
	"<=>" : _compare
}
PRIMITIVE_UNARY = {
	"-" : operator.neg,
	"NOT" : operator.not_,
}
STRICT_VALUE = Union[
	int, float, str, dict,
	"Procedure", "BoundMethod", "Message", "Step",
]
LAZY_VALUE = Union[STRICT_VALUE, "Thunk"]
ENV = Frame[LAZY_VALUE]
VTABLE = object()
SHORTCUT = {
	"AND":False,
	"OR":True,
}

THREADED_ROOT = RootFrame()

def overloaded_bin_op(a:STRICT_VALUE, op:str, b:STRICT_VALUE, dynamic_env:ENV):
	signature = _type_class(a), _type_class(b)
	if op in RELOP_MAP:
		order = OVERLOAD["<=>", signature].apply((a, b), dynamic_env)
		return order[""] in RELOP_MAP[op]
	else:
		return OVERLOAD[op, signature].apply((a, b), dynamic_env)
	

RELOP_MAP = {}

OVERLOAD = {}

_PRIMITIVE_TYPE_CLASS = {
	int: primitive.root_namespace['number'],
	float: primitive.root_namespace['number'],
	str: primitive.root_namespace['string'],
	bool: primitive.root_namespace['flag'],
}

def _type_class(x:STRICT_VALUE):
	try: return _PRIMITIVE_TYPE_CLASS[type(x)]
	except KeyError: return x[""].as_token()

###############################################################################

ABSENT = object()
class Thunk:
	""" A kind of not-yet-value which can be forced. """
	def __init__(self, expr: syntax.ValExpr, dynamic_env: ENV):
		assert isinstance(expr, syntax.ValExpr), type(expr)
		self.dynamic_env = dynamic_env
		self.expr = expr
		self.value = ABSENT
		
	def __str__(self):
		if self.value is ABSENT:
			return "<Thunk: %s>"%self.expr
		else:
			return str(self.value)

def force(it:LAZY_VALUE) -> STRICT_VALUE:
	"""
	Force repeatedly until the result is no longer a thunk, then return that result.
	This simulates tail-call elimination, now that closures promptly return thunks.
	"""
	while isinstance(it, Thunk):
		if it.value is ABSENT:
			it.value = evaluate(it.expr, it.dynamic_env)
			del it.expr, it.dynamic_env
		it = it.value
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
				inner = Activation.for_function(static_env, dynamic_env, sym, ())
				value = delay(sym.expr, inner)
		elif isinstance(sym, syntax.TypeAlias):
			value = _snap_type_alias(sym, static_env)
		else:
			assert False, type(sym)
		return static_env.assign(sym, value)

def _eval_lambda_form(expr:syntax.LambdaForm, dynamic_env:ENV):
	return Closure(dynamic_env, expr.function)

def _eval_bin_exp(expr:syntax.BinExp, dynamic_env:ENV):
	a = _strict(expr.lhs, dynamic_env)
	b = _strict(expr.rhs, dynamic_env)
	try:
		return PRIMITIVE_BINARY[expr.op.text](a, b)
	except TypeError:
		return overloaded_bin_op(a, expr.op.text, b, dynamic_env)

def _eval_unary_exp(expr:syntax.UnaryExp, dynamic_env:ENV):
	return PRIMITIVE_UNARY[expr.op.text](_strict(expr.arg, dynamic_env))

def _eval_shortcut_exp(expr:syntax.ShortCutExp, dynamic_env:ENV):
	lhs = _strict(expr.lhs, dynamic_env)
	assert isinstance(lhs, bool)
	return lhs if lhs == SHORTCUT[expr.op.text] else _strict(expr.rhs, dynamic_env)

def _eval_call(expr:syntax.Call, dynamic_env:ENV):
	procedure = _strict(expr.fn_exp, dynamic_env)
	thunks = tuple(delay(a, dynamic_env) for a in expr.args)
	return procedure.apply(thunks, dynamic_env)

def _eval_cond(expr:syntax.Cond, dynamic_env:ENV):
	if_part = _strict(expr.if_part, dynamic_env)
	sequel = expr.then_part if if_part else expr.else_part
	return evaluate(sequel, dynamic_env)

def _eval_field_ref(expr:syntax.FieldReference, dynamic_env:ENV):
	lhs = _strict(expr.lhs, dynamic_env)
	key = expr.field_name.text
	if isinstance(lhs, dict):
		try: return lhs[key]
		except KeyError:
			raise
	else:
		return getattr(lhs, key)

def _eval_explicit_list(expr:syntax.ExplicitList, dynamic_env:ENV):
	tail = NIL
	for sx in reversed(expr.elts):
		head = delay(sx, dynamic_env)
		tail = CONS.apply((head, tail), dynamic_env)
	return tail

def _eval_match_expr(expr:syntax.MatchExpr, dynamic_env:ENV):
	subject = dynamic_env.assign(expr.subject, _strict(expr.subject.expr, dynamic_env))
	tag = subject[""]
	try:
		alternative = expr.dispatch[tag]
	except KeyError:
		branch = expr.otherwise
		assert branch is not None, (tag, type(tag))
		return evaluate(branch, dynamic_env)
	else:
		for sub_fn in alternative.where:
			dynamic_env.declare(sub_fn)
		return evaluate(alternative.sub_expr, dynamic_env)

def _eval_do_block(expr:syntax.DoBlock, dynamic_env:ENV):
	return CompoundAction(expr, dynamic_env)

def _eval_skip(expr:syntax.Skip, dynamic_env:ENV):
	return Nop()

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

def _eval_assign_field(expr:syntax.AssignField, dynamic_env:ENV):
	state = dynamic_env.chase(SELF).fetch(SELF)
	return AssignAction(state, expr.nom.key(), evaluate(expr.expr, dynamic_env))

def _eval_absurdity(expr:syntax.Absurdity, dynamic_env:ENV):
	trace_absurdity(dynamic_env, expr)
	exit()
	

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
	return fn(expr, dynamic_env)

_NO_DELAY = {syntax.Literal, syntax.Lookup, syntax.DoBlock, syntax.LambdaForm}

def delay(expr: syntax.ValExpr, dynamic_env: ENV) -> LAZY_VALUE:
	# For certain kinds of expression, there is no profit to delay:
	if type(expr) in _NO_DELAY: return evaluate(expr, dynamic_env)
	# Volatile expressions (that depend on a field of SELF) must not delay:
	if expr.is_volatile: return _strict(expr, dynamic_env)
	# In less trivial cases, make a thunk and pass that instead.
	return Thunk(expr, dynamic_env)

EVALUATE = {}
for _k, _v in list(globals().items()):
	if _k.startswith("_eval_"):
		_t = _v.__annotations__["expr"]
		assert isinstance(_t, type), (_k, _t)
		EVALUATE[_t] = _v

###############################################################################

class Function:
	""" A run-time object that can be applied with arguments. """
	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> Any:
		# It must be a LAZY_VALUE and not a syntax.ValExpr
		# lest various internal things fail to work,
		# which things to not tie back to specific syntax objects.
		# For example, explicit lists.
		raise NotImplementedError

class Closure(Function):
	""" The run-time manifestation of a sub-function: a callable value tied to its natal environment. """

	def __init__(self, static_link:ENV, udf:syntax.UserFunction):
		assert hasattr(udf, "strictures"), udf
		self._static_link = static_link
		self._udf = udf
	
	def __str__(self):
		return str(self._udf)
	
	def _name(self): return self._udf.nom.text

	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> LAZY_VALUE:
		for i in self._udf.strictures:
			force(args[i])
		inner_env = Activation.for_function(self._static_link, dynamic_env, self._udf, args)
		return delay(self._udf.expr, inner_env)

class Primitive(Function):
	""" All parameters to primitive procedures are strict. Also a kind of value, like a closure. """
	def __init__(self, fn: callable):
		self._fn = fn
	
	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> STRICT_VALUE:
		return self._fn(*map(force, args))

class Constructor(Function):
	def __init__(self, key:syntax.Symbol, fields:list[str]):
		self.key = key
		self.fields = fields
	
	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> Any:
		# TODO: It would be well to handle tagged values as Python pairs.
		#  This way any value could be tagged, and various case-matching
		#  things could work more nicely (and completely).
		assert len(args) == len(self.fields)
		structure = {"": self.key}
		for field, arg in zip(self.fields, args):
			assert not isinstance(arg, syntax.ValExpr)
			structure[field] = arg
		return structure

class ActorClass(Function):
	def __init__(self, global_link:ENV, uda:syntax.UserAgent):
		self._global_link = global_link
		self._uda = uda
		
	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> "ActorTemplate":
		assert len(args) == len(self._uda.fields)
		return ActorTemplate(self._global_link, self._uda, args)


class ActorTemplate:
	def __init__(self, global_link:ENV, uda:syntax.UserAgent, args: Sequence[LAZY_VALUE]):
		self._global_link = global_link
		self._uda = uda
		self._args = args
	
	def instantiate(self, dynamic_link:ENV):
		private_state = dict(zip(self._uda.field_names(), map(force, self._args)))
		private_state[VTABLE] = self._uda.message_space.local
		frame = Activation(self._global_link, dynamic_link, self._uda)
		frame.assign(SELF, private_state)
		return UserDefinedActor(frame)

###############################################################################

class Action:
	def perform(self):
		""" Do something here and now in the current thread. """
		raise NotImplementedError(type(self))

class Nop(Action):
	def perform(self): pass

class AssignAction(Action):
	def __init__(self, state:dict[str,STRICT_VALUE], field_name:str, new_value:LAZY_VALUE):
		self._state = state
		self._field_name = field_name
		self._new_value = new_value
	def perform(self):
		self._state[self._field_name] = force(self._new_value)

class CompoundAction(Action):
	def __init__(self, block:syntax.DoBlock, dynamic_env:ENV):
		self._block = block
		self._dynamic_env = dynamic_env
	def perform(self):
		agents = self._block.agents
		if agents:
			inner = Activation.for_do_block(self._dynamic_env)
			for na in agents:
				assert isinstance(na, syntax.NewAgent)
				template = _strict(na.expr, self._dynamic_env)
				inner.assign(na, template.instantiate(self._dynamic_env))
		else:
			inner = self._dynamic_env
		# TODO: Solve the tail-recursion problem.
		for expr in self._block.steps:
			inner.pc = expr
			action = _strict(expr, inner)
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
		self._task.enqueue()

###############################################################################

class Message(Function):
	""" Interface for things that, with arguments, become messages ready to send. """
	def dispatch_with(self, *args):
		self.apply(args, THREADED_ROOT).perform()

class BoundMethod(Message, Action):
	def __init__(self, receiver, method_name):
		self._receiver = receiver
		self._method_name = method_name

	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> LAZY_VALUE:
		return BoundMessage(self._receiver, self._method_name, *(force(a) for a in args))
	
	def perform(self):
		""" Hack so that a single runtime class handles both parametric and non-parametric messages to actors """
		self._receiver.accept_message(self._method_name, ())

class ClosureMessage(Message):
	def __init__(self, closure: Closure):
		self._closure = closure

	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> Any:
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
		action = force(self._closure.apply(self._args, THREADED_ROOT))
		assert isinstance(action, Action), type(action)
		action.perform()

class UserDefinedActor(Actor):
	def __init__(self, frame:ENV):
		super().__init__()
		self._frame = frame
	
	def handle(self, message, args):
		state = self._frame.fetch(SELF)
		behavior = state[VTABLE][message]
		assert isinstance(behavior, syntax.Behavior)
		frame = Activation.for_behavior(self._frame, THREADED_ROOT, behavior, args)
		_strict(behavior.expr, frame).perform()

###############################################################################

NIL:Optional[dict] = None # Gets replaced at runtime.
LESS:Optional[dict] = None # Gets replaced at runtime.
SAME:Optional[dict] = None # Gets replaced at runtime.
MORE:Optional[dict] = None # Gets replaced at runtime.
NOPE:Optional[dict] = None # Gets replaced at runtime.
CONS:Constructor
THIS:Constructor

def iterate_list(lst:LAZY_VALUE):
	lst = force(lst)
	while lst[""] == CONS.key:
		yield force(lst['head'])
		lst = force(lst['tail'])
	assert lst[""] == NIL[""]

def as_sophie_list(items:Reversible):
	lst = NIL
	for head in reversed(items):
		lst = {"":CONS.key, "head":head, "tail":lst}
	return lst

def sophie_nope(): return NOPE
def sophie_this(item): return {"":THIS.key, "item":item}

###############################################################################

def reset(fetch):
	OVERLOAD.clear()
	for k in 'nil', 'cons', 'less', 'same', 'more', 'this', 'nope':
		globals()[k.upper()] = fetch(k)
	for relation, cases in {
		"<":("less",),
		"==":("same",),
		">":("more",),
		"!=":("less", "more"),
		"<=":("less", "same"),
		">=":("more", "same"),
	}.items():
		RELOP_MAP[relation] = tuple(fetch(order)[""] for order in cases)

def install_overrides(env:ENV, overrides):
	for udf in overrides:
		assert isinstance(udf, syntax.UserOperator), "No FFI operator support just yet. Sorry."
		signature = udf.dispatch_vector()
		OVERLOAD[udf.nom.key(), signature] = Closure(env, udf)
