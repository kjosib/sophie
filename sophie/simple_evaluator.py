"""
Call-By-Need with Direct Interpretation
No longer quite the simplest, most straight-forward possible implementation.

"""
import sys
from typing import Any, Union, Sequence, Optional
from collections import namedtuple, deque
import abc
from . import syntax, primitive, ontology
from .stacking import StackFrame, StackBottom, ActivationRecord

FAKE_SOURCE_PATH = "FAKE_SOURCE_PATH" # until fixed.

STRICT_VALUE = Union[int, float, str, "Procedure", namedtuple, dict]
LAZY_VALUE = Union[STRICT_VALUE, "Thunk"]
ENV = StackFrame[LAZY_VALUE]

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
			self._value = strict(self._expr, self._dynamic_env)
			del self._dynamic_env, self._expr
		return self._value
	
	def __str__(self):
		if self._value is ABSENT:
			return "<Thunk: %s>"%self._expr
		else:
			return str(self._value)


class Procedure(abc.ABC):
	""" A run-time object that can be applied with arguments. """
	@abc.abstractmethod
	def apply(self, dynamic_env:ENV, args: list[LAZY_VALUE]) -> Any:
		pass

def actual_value(it:LAZY_VALUE) -> STRICT_VALUE:
	"""
	While this will not return a thunk as such,
	it may return a structure which contains thunks.
	"""
	while isinstance(it, Thunk):
		it = it.force()
	return it

def strict(expr:syntax.ValExpr, dynamic_env:ENV):
	return actual_value(evaluate(expr, dynamic_env))

def _eval_literal(expr:syntax.Literal, dynamic_env:ENV):
	return expr.value

def _eval_lookup(expr:syntax.Lookup, dynamic_env:ENV):
	dfn = expr.ref.dfn
	return lookup(dfn, dynamic_env.chase(dfn))


def _eval_bin_exp(expr:syntax.BinExp, dynamic_env:ENV):
	return OPS[expr.glyph](strict(expr.lhs, dynamic_env), strict(expr.rhs, dynamic_env))

def _eval_unary_exp(expr:syntax.UnaryExp, dynamic_env:ENV):
	return OPS[expr.glyph](strict(expr.arg, dynamic_env))

def _eval_shortcut_exp(expr:syntax.ShortCutExp, dynamic_env:ENV):
	lhs = strict(expr.lhs, dynamic_env)
	assert isinstance(lhs, bool)
	return lhs if lhs == OPS[expr.glyph] else strict(expr.rhs, dynamic_env)

def _eval_call(expr:syntax.Call, dynamic_env:ENV):
	procedure = strict(expr.fn_exp, dynamic_env)
	return procedure.apply(dynamic_env, [delay(dynamic_env, a) for a in expr.args])

def _eval_cond(expr:syntax.Cond, dynamic_env:ENV):
	if_part = strict(expr.if_part, dynamic_env)
	sequel = expr.then_part if if_part else expr.else_part
	return delay(dynamic_env, sequel)

def _eval_field_ref(expr:syntax.FieldReference, dynamic_env:ENV):
	lhs = strict(expr.lhs, dynamic_env)
	key = expr.field_name.text
	if isinstance(lhs, dict):
		return lhs[key]
	else:
		return getattr(lhs, key)

def _eval_explicit_list(expr:syntax.ExplicitList, dynamic_env:ENV):
	it = NIL
	for sx in reversed(expr.elts):
		it = CONS.apply(dynamic_env, [evaluate(sx, dynamic_env), it])
	return it

def _eval_match_expr(expr:syntax.MatchExpr, dynamic_env:ENV):
	dynamic_env.bindings[expr.subject] = subject = strict(expr.subject.expr, dynamic_env)
	tag = subject[""]
	try:
		branch = expr.dispatch[tag]
	except KeyError:
		branch = expr.otherwise
		if branch is None:
			raise RuntimeError("Confused by tag %r; should not be possible now that type-checking works."%tag)
	return delay(dynamic_env, branch)

def _snap_type_alias(alias:syntax.TypeAlias, env:ENV):
	assert isinstance(alias.body, syntax.TypeCall)  # resolution.check_constructors guarantees this.
	return lookup(alias.body.ref.dfn, env)

def _snap_udf(udf:syntax.UserDefinedFunction, env:ENV):
	return Closure(env, udf) if udf.params else delay(env, udf.expr)

SNAP : dict[type, callable] = {
	syntax.TypeAlias: _snap_type_alias,
	syntax.UserDefinedFunction:_snap_udf,
}

def lookup(dfn:ontology.Symbol, env:ENV):
	try: return env.bindings[dfn]
	except KeyError:
		env.bindings[dfn] = it = SNAP[type(dfn)](dfn, env)
		return it

EVALUABLE = Union[syntax.ValExpr, syntax.Reference]

def evaluate(expr:EVALUABLE, dynamic_env:ENV) -> LAZY_VALUE:
	assert isinstance(dynamic_env, StackFrame), type(dynamic_env)
	try: fn = EVALUATE[type(expr)]
	except KeyError: raise NotImplementedError(type(expr), expr)
	else: return fn(expr, dynamic_env)

def delay(dynamic_env:ENV, item:syntax.ValExpr) -> LAZY_VALUE:
	# For two kinds of expression, there is no profit to delay:
	if isinstance(item, syntax.Literal): return item.value
	if isinstance(item, syntax.Lookup): return _eval_lookup(item, dynamic_env)
	# In less trivial cases, make a thunk and pass that instead.
	assert isinstance(item, syntax.ValExpr)
	return Thunk(dynamic_env, item)

class Closure(Procedure):
	""" The run-time manifestation of a sub-function: a callable value tied to its natal environment. """

	def __init__(self, static_link:ENV, udf:syntax.UserDefinedFunction):
		self._static_link = static_link
		self._udf = udf
	
	def _name(self): return self._udf.nom.text

	def apply(self, dynamic_env:ENV, args: list[LAZY_VALUE]) -> LAZY_VALUE:
		inner_env = ActivationRecord(self._udf, dynamic_env, self._static_link, args)
		return evaluate(self._udf.expr, inner_env)

class Primitive(Procedure):
	""" All parameters to primitive procedures are strict. Also a kind of value, like a closure. """
	def __init__(self, fn:callable):
		self._fn = fn
		
	def apply(self, dynamic_env:ENV, args: list[LAZY_VALUE]) -> STRICT_VALUE:
		return self._fn(*(actual_value(a) for a in args))

class Constructor(Procedure):
	def __init__(self, key:str, fields:list[str]):
		self.key = key
		self.fields = fields
	
	def apply(self, dynamic_env:ENV, args: list[LAZY_VALUE]) -> Any:
		# TODO: It would be well to handle tagged values as Python pairs.
		#  This way any value could be tagged, and various case-matching
		#  things could work more nicely (and completely).
		assert len(args) == len(self.fields)
		structure = {"":self.key}
		for field, arg in zip(self.fields, args):
			structure[field] = arg
		return structure

def run_program(static_root, each_module: Sequence[syntax.Module]):
	drivers = {}
	env = StackBottom(None)
	_prepare_root_environment(env, static_root)
	result = None  # Pacify the IDE
	for module in each_module:
		env.current_path = module.path
		_prepare_global_scope(env, module.globals.local.items())
		for d in module.foreign:
			if d.linkage is not None:
				py_module = sys.modules[d.source.value]
				linkage = [env.bindings[ref.dfn] for ref in d.linkage]
				drivers.update(py_module.sophie_init(actual_value, *linkage))
				
		for expr in module.main:
			env.pc = expr
			result = strict(expr, env)
			if isinstance(result, dict):
				tag = result.get("")
				if tag in drivers:
					drivers[tag](actual_value, env, result)
					continue
				dethunk(result)
				if tag == 'cons':
					result = decons(result)
			if result is not None:
				print(result)
	return result

NIL:dict
CONS:Constructor

def _prepare_root_environment(env:StackBottom, static_root):
	global NIL, CONS
	_prepare_global_scope(env, primitive.root_namespace.local.items())
	_prepare_global_scope(env, static_root.local.items())
	if 'nil' in static_root:
		NIL = env.bindings[static_root['nil']]
		CONS = env.bindings[static_root['cons']]
	else:
		NIL, CONS = None, None

def _prepare_global_scope(env:StackBottom, items):
	for key, dfn in items:
		if isinstance(dfn, syntax.Record):
			env.bindings[dfn] = Constructor(key, dfn.spec.field_names())
		elif isinstance(dfn, (syntax.SubTypeSpec, syntax.TypeAlias)):
			if isinstance(dfn.body, (syntax.ArrowSpec, syntax.TypeCall)):
				pass
			elif isinstance(dfn.body, syntax.RecordSpec):
				env.bindings[dfn] = Constructor(key, dfn.body.field_names())
			elif dfn.body is None:
				env.bindings[dfn] = {"": key}
			else:
				raise ValueError("Tagged scalars (%r) are not implemented."%key)
		elif isinstance(dfn, ontology.NativeFunction):
			env.bindings[dfn] = _native_object(dfn)
		elif type(dfn) in _ignore_these:
			pass
		else:
			raise ValueError("Don't know how to deal with %r %r"%(type(dfn), key))

def _native_object(dfn:ontology.NativeFunction):
	if callable(dfn.val):
		return Primitive(dfn.val)
	else:
		return dfn.val

_ignore_these = {
	# type(None),
	syntax.UserDefinedFunction,  # Gets built on-demand.
	syntax.ArrowSpec,
	syntax.TypeCall,
	syntax.Variant,
	syntax.Opaque,
}

def dethunk(result:dict):
	"""
	This can be considered as (most of) the first and most trivial I/O driver.
	Its entire job is to push a program to completion by evaluating every thunk it produces.
	There should be a better way, but it will probably be the consequence of an I/O subsystem.
	"""
	dict_queue = deque()
	dict_queue.append(result)
	while dict_queue:
		work_dict = dict_queue.popleft()
		for k,v in work_dict.items():
			if isinstance(v, Thunk): work_dict[k] = v = actual_value(v)
			if isinstance(v, dict): dict_queue.append(v)

def decons(item:dict) -> list:
	result = []
	while isinstance(item, dict) and item.get("") == 'cons':
		result.append(item['head'])
		item = item['tail']
	if item is not NIL:
		result.append(item)
	return result


EVALUATE = {}
for _k, _v in list(globals().items()):
	if _k.startswith("_eval_"):
		_t = _v.__annotations__["expr"]
		assert isinstance(_t, type), (_k, _t)
		EVALUATE[_t] = _v
OPS = {glyph:op for glyph, (op, typ) in primitive.ops.items()}
