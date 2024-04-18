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
	
	def perform(self, dynamic_env:ENV):
		return force(self)

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
				inner = Activation.for_subroutine(static_env, dynamic_env, sym, ())
				value = delay(sym.expr, inner)
		elif isinstance(sym, syntax.UserProcedure):
			value = Closure(static_env, sym)
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
	agents = expr.agents
	if agents:
		inner = Activation.for_do_block(dynamic_env)
		for na in agents:
			assert isinstance(na, syntax.NewAgent)
			template = _strict(na.expr, dynamic_env)
			inner.assign(na, template.instantiate(dynamic_env))
	else:
		inner = dynamic_env
	# TODO: Solve the tail-recursion problem.
	for expr in expr.steps:
		inner.pc = expr
		perform(_strict(expr, inner), inner)

def _eval_skip(expr:syntax.Skip, dynamic_env:ENV):
	return

def _eval_bind_method(expr:syntax.BindMethod, dynamic_env:ENV):
	return BoundMethod(_strict(expr.receiver, dynamic_env), expr.method_name.text)

def _eval_as_task(expr:syntax.AsTask, dynamic_env:ENV):
	sub = _strict(expr.proc_ref, dynamic_env)
	return sub.as_task()

def _eval_assign_member(expr:syntax.AssignMember, dynamic_env:ENV):
	uda = dynamic_env.chase(SELF).fetch(SELF)
	uda.state[expr.dfn] = _strict(expr.expr, dynamic_env)

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
	# For now, I'll use Closure for both functions and procedures.

	def __init__(self, static_link:ENV, udf:syntax.Subroutine):
		assert hasattr(udf, "strictures"), udf
		self._static_link = static_link
		self._udf = udf
	
	def __str__(self):
		return str(self._udf)
	
	def _name(self): return self._udf.nom.text

	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> LAZY_VALUE:
		for i in self._udf.strictures:
			force(args[i])
		inner_env = Activation.for_subroutine(self._static_link, dynamic_env, self._udf, args)
		return delay(self._udf.expr, inner_env)
	
	def perform(self, dynamic_env:ENV) -> STRICT_VALUE:
		return self.apply((), dynamic_env)
	
	def as_task(self):
		return ParametricTask(self) if self._udf.params else PlainTask(self, ())

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
		assert len(args) == len(self._uda.members)
		return ActorTemplate(self._global_link, self._uda, args)


class ActorTemplate:
	def __init__(self, global_link:ENV, uda:syntax.UserAgent, args: Sequence[LAZY_VALUE]):
		self._global_link = global_link
		self._uda = uda
		self._args = args
	
	def instantiate(self, dynamic_link:ENV):
		state = dict(zip(self._uda.members, map(force, self._args)))
		vtable = self._uda.message_space.local
		return UserDefinedActor(state, vtable, self._global_link)

class UserDefinedActor(Actor):
	def __init__(self, state:dict, vtable:dict, global_env:ENV):
		super().__init__()
		self.state = state
		self._vtable = vtable
		self.global_env = global_env
	
	def handle(self, message, args):
		behavior = self._vtable[message]
		outer = Activation.for_actor(self, THREADED_ROOT)
		inner = Activation.for_subroutine(outer, THREADED_ROOT, behavior, args)
		perform(evaluate(behavior.expr, inner), inner)

	def state_pairs(self):
		return self.state

###############################################################################

def perform(action, dynamic_env:ENV):
	while action is not None:
		action = action.perform(dynamic_env)

###############################################################################
class ParametricMessage(Function):
	""" Interface for things that, with arguments, become messages ready to send. """
	def dispatch_with(self, *args):
		self.apply(args, THREADED_ROOT).perform(THREADED_ROOT)

class ParametricTask(ParametricMessage):
	def __init__(self, closure: Closure):
		self._closure = closure

	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> Any:
		return PlainTask(self._closure, tuple(force(a) for a in args))

class BoundMethod(ParametricMessage):
	def __init__(self, receiver, method_name):
		self._receiver = receiver
		self._method_name = method_name

	def apply(self, args: Sequence[LAZY_VALUE], dynamic_env:ENV) -> Any:
		return MessageTask(self._receiver, self._method_name, tuple(force(a) for a in args))

	def perform(self, dynamic_env:ENV):
		self._receiver.accept_message(self._method_name, ())
	
class MessageTask:
	def __init__(self, receiver, method_name, args:Sequence[STRICT_VALUE]):
		self._receiver = receiver
		self._method_name = method_name
		self._args = args
		
	def perform(self, dynamic_env:ENV):
		self._receiver.accept_message(self._method_name, self._args)

class PlainTask(Task):
	def __init__(self, closure:Closure, args:Sequence[STRICT_VALUE]):
		self._closure = closure
		self._args = args
	
	def perform(self, dynamic_env:ENV):
		self.enqueue()

	def proceed(self):
		it = self._closure.apply(self._args, THREADED_ROOT)
		perform(it, THREADED_ROOT)
	

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

def is_sophie_list(it:STRICT_VALUE):
	return isinstance(it, dict) and it[""] is CONS.key

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
