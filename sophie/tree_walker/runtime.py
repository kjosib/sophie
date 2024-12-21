import sys
import operator
from typing import Optional, Reversible
from .. import syntax, primitive 
from ..ontology import SELF
from ..diagnostics import trace_absurdity, Annotation
from .types import ENV, STRICT_VALUE, LAZY_VALUE
from .evaluator import force, delay, evaluate, perform, attach_evaluation_methods
from .values import Function, Constructor, Closure, close, BoundMethod, UserDefinedActor

GLOBAL_SCOPE = {}

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
SHORTCUT = {
	"AND":False,
	"OR":True,
}

def overloaded_bin_op(a:STRICT_VALUE, op:str, b:STRICT_VALUE):
	signature = _type_class(a), _type_class(b)
	if op in RELOP_MAP:
		order = OVERLOAD["<=>", signature].apply((a, b))
		return order[""] in RELOP_MAP[op]
	else:
		return OVERLOAD[op, signature].apply((a, b))
	

RELOP_MAP = {}

OVERLOAD = {}

PRIMITIVE_TYPE_TOKENS = {}

def _type_class(x:STRICT_VALUE):
	try: return x[""].as_token()
	except TypeError: return PRIMITIVE_TYPE_TOKENS[type(x)]

###############################################################################

def _strict(expr:syntax.ValueExpression, frame:ENV):
	return force(evaluate(expr, frame))

###############################################################################

def _eval_literal(expr:syntax.Literal, frame:ENV):
	return expr.value

def _eval_lookup(expr:syntax.Lookup, frame:ENV):
	sym = expr.ref.dfn
	try: return frame[sym] # NOQA
	except KeyError:
		try: return GLOBAL_SCOPE[sym]
		except KeyError:
			ann = Annotation(expr, "This wasn't found; compiler bug")
			print(ann.path, file=sys.stderr)
			print(ann.illustrate(), file=sys.stderr)
			print(frame, file=sys.stderr)
			raise


def _eval_lambda_form(expr:syntax.LambdaForm, frame:ENV):
	closure = Closure(expr.function)
	closure.perform_capture(frame)
	return closure

def _eval_bin_exp(expr:syntax.BinExp, frame:ENV):
	a = _strict(expr.lhs, frame)
	b = _strict(expr.rhs, frame)
	try:
		return PRIMITIVE_BINARY[expr.op.text](a, b)
	except TypeError:
		return overloaded_bin_op(a, expr.op.text, b)

def _eval_unary_exp(expr:syntax.UnaryExp, frame:ENV):
	return PRIMITIVE_UNARY[expr.op.text](_strict(expr.arg, frame))

def _eval_shortcut_exp(expr:syntax.ShortCutExp, frame:ENV):
	lhs = _strict(expr.lhs, frame)
	assert isinstance(lhs, bool)
	return lhs if lhs == SHORTCUT[expr.op.text] else _strict(expr.rhs, frame)

def _eval_call(expr:syntax.Call, frame:ENV):
	function = _strict(expr.fn_exp, frame)
	assert isinstance(function, Function)
	thunks = tuple(delay(a, frame) for a in expr.args)
	return function.apply(thunks)

def _eval_cond(expr:syntax.Cond, frame:ENV):
	if_part = _strict(expr.if_part, frame)
	sequel = expr.then_part if if_part else expr.else_part
	return evaluate(sequel, frame)

def _eval_field_ref(expr:syntax.FieldReference, frame:ENV):
	lhs = _strict(expr.lhs, frame)
	key = expr.field_name.text
	if isinstance(lhs, dict):
		try: return lhs[key]
		except KeyError:
			raise
	else:
		return getattr(lhs, key)

def _eval_explicit_list(expr:syntax.ExplicitList, frame:ENV):
	tail = NIL
	for sx in reversed(expr.elts):
		head = delay(sx, frame)
		tail = CONS.apply((head, tail))
	return tail

def _eval_match_expr(expr:syntax.MatchExpr, frame:ENV):
	subject = _strict(expr.subject.expr, frame)
	frame[expr.subject] = subject
	tag = subject[""]
	try:
		alternative = expr.dispatch[tag]
	except KeyError:
		branch = expr.otherwise
		assert branch is not None, (tag, type(tag))
		return evaluate(branch, frame)
	else:
		close(frame, alternative.where)
		return evaluate(alternative.sub_expr, frame)

def _eval_do_block(expr:syntax.DoBlock, frame:ENV):
	for na in expr.actors:
		assert isinstance(na, syntax.NewActor)
		template = _strict(na.expr, frame)
		frame[na] = template.instantiate() # NOQA
	# TODO: Solve the tail-recursion problem.
	for expr in expr.steps:
		perform(_strict(expr, frame))

def _eval_skip(expr:syntax.Skip, frame:ENV):
	return

def _eval_bind_method(expr:syntax.BindMethod, frame:ENV):
	return BoundMethod(_strict(expr.receiver, frame), expr.method_name.text)

def _eval_as_task(expr:syntax.AsTask, frame:ENV):
	sub = _strict(expr.proc_ref, frame)
	return sub.as_task()

def _eval_assign_member(expr:syntax.AssignMember, frame:ENV):
	frame[SELF].state[expr.dfn] = _strict(expr.expr, frame)

def _eval_absurdity(expr:syntax.Absurdity, frame:ENV):
	trace_absurdity(frame, expr)
	exit()
	
attach_evaluation_methods(globals())

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

def reset_runtime(preamble_scope):
	"""
	The run-time needs frequent access to a few term-symbols
	defined in the preamble. We enter references into global
	variables named for the symbol (but all-upper-case).
	"""
	
	PRIMITIVE_TYPE_TOKENS.clear()
	for typ, name in primitive.literal_type_map.items():
		token = preamble_scope.types.symbol(name).as_token()
		PRIMITIVE_TYPE_TOKENS[typ] = token
	
	OVERLOAD.clear()
	for name in 'nil', 'cons', 'less', 'same', 'more', 'this', 'nope':
		globals()[name.upper()] = GLOBAL_SCOPE[preamble_scope.terms.symbol(name)]
	for relation, cases in {
		"<":("less",),
		"==":("same",),
		">":("more",),
		"!=":("less", "more"),
		"<=":("less", "same"),
		">=":("more", "same"),
	}.items():
		RELOP_MAP[relation] = tuple(preamble_scope.terms.symbol(order) for order in cases)

def install_overrides(overrides):
	for sub in overrides:
		assert isinstance(sub, syntax.UserOperator), "No FFI operator support just yet. Sorry."
		signature = sub.dispatch_vector()
		OVERLOAD[sub.nom.key(), signature] = GLOBAL_SCOPE[sub]
