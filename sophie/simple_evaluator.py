"""
Call-By-Need with Direct Interpretation
No longer quite the simplest, most straight-forward possible implementation.

"""
import sys
from typing import Any, Union, Sequence
from collections import namedtuple, deque
import abc
from . import syntax, primitive, ontology

STATIC_LINK = object()

STRICT_VALUE = Union[int, float, str, "Procedure", namedtuple, dict]

ABSENT = object()
class Thunk:
	""" A kind of not-yet-value which can be forced. """
	def __init__(self, dynamic_env:dict, expr: syntax.ValExpr):
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

LAZY_VALUE = Union[STRICT_VALUE, Thunk]

class Procedure(abc.ABC):
	""" A run-time object that can be applied with arguments. """
	@abc.abstractmethod
	def apply(self, args: list[LAZY_VALUE]) -> Any:
		pass

def actual_value(it:LAZY_VALUE) -> STRICT_VALUE:
	"""
	While this will not return a thunk as such,
	it may return a structure which contains thunks.
	"""
	while isinstance(it, Thunk):
		it = it.force()
	return it

def strict(expr:syntax.ValExpr, dynamic_env:dict):
	return actual_value(evaluate(expr, dynamic_env))

def _eval_literal(expr:syntax.Literal, dynamic_env:dict):
	return expr.value

def _eval_lookup(expr:syntax.Lookup, dynamic_env:dict):
	dfn = expr.ref.dfn
	target_depth = dfn.static_depth
	if target_depth == 0:
		return lookup(dfn, SOPHIE_GLOBALS)
	else:
		sp = dynamic_env
		for _ in range(target_depth, expr.source_depth):
			# i.e. (source_depth - target_depth).times do {...}
			sp = sp[STATIC_LINK]
	return lookup(dfn, sp)

def _eval_bin_exp(expr:syntax.BinExp, dynamic_env:dict):
	return OPS[expr.glyph](strict(expr.lhs, dynamic_env), strict(expr.rhs, dynamic_env))

def _eval_unary_exp(expr:syntax.UnaryExp, dynamic_env:dict):
	return OPS[expr.glyph](strict(expr.arg, dynamic_env))

def _eval_shortcut_exp(expr:syntax.ShortCutExp, dynamic_env:dict):
	lhs = strict(expr.lhs, dynamic_env)
	assert isinstance(lhs, bool)
	return lhs if lhs == OPS[expr.glyph] else strict(expr.rhs, dynamic_env)

def _eval_call(expr:syntax.Call, dynamic_env:dict):
	procedure = strict(expr.fn_exp, dynamic_env)
	assert isinstance(procedure, Procedure)
	return procedure.apply([delay(dynamic_env, a) for a in expr.args])

def _eval_cond(expr:syntax.Cond, dynamic_env:dict):
	if_part = strict(expr.if_part, dynamic_env)
	sequel = expr.then_part if if_part else expr.else_part
	return delay(dynamic_env, sequel)

def _eval_field_ref(expr:syntax.FieldReference, dynamic_env:dict):
	lhs = strict(expr.lhs, dynamic_env)
	key = expr.field_name.text
	if isinstance(lhs, dict):
		return lhs[key]
	else:
		return getattr(lhs, key)

def _eval_explicit_list(expr:syntax.ExplicitList, dynamic_env:dict):
	it = NIL
	for sx in reversed(expr.elts):
		it = CONS.apply([evaluate(sx, dynamic_env), it])
	return it

def _eval_match_expr(expr:syntax.MatchExpr, dynamic_env:dict):
	dynamic_env[expr.subject] = subject = strict(expr.subject.expr, dynamic_env)
	tag = subject[""]
	try:
		branch = expr.dispatch[tag]
	except KeyError:
		branch = expr.otherwise
		if branch is None:
			raise RuntimeError("Confused by tag %r; should not be possible now that type-checking works."%tag)
	return delay(dynamic_env, branch)

def _lookup_udf(udf: syntax.UserDefinedFunction, env: dict):
	# I guess this is where memoization comes from.
	assert type(udf) is syntax.UserDefinedFunction, type(udf)
	try: return env[udf]
	except KeyError:
		env[udf] = it = Closure(env, udf) if udf.params else delay(env, udf.expr)
		return it

def _lookup_by_name(sym, env:dict):
	return env[sym.nom.text]

def _lookup_type_alias(sym:syntax.TypeAlias, env:dict):
	tc : syntax.TypeCall = sym.body  # Guaranteed by resolution.check_constructors
	it = env[sym] = lookup(tc.ref.dfn, env)  # Snap the pointers along the way
	return it

def _lookup_all_else(dfn, env:dict):
	return env[dfn]

EVALUABLE = Union[syntax.ValExpr, syntax.Reference]

def evaluate(expr:EVALUABLE, dynamic_env:dict) -> LAZY_VALUE:
	try: fn = EVALUATE[type(expr)]
	except KeyError: raise NotImplementedError(type(expr), expr)
	else: return fn(expr, dynamic_env)

LOOKUP : dict[type, callable] = {
	syntax.UserDefinedFunction: _lookup_udf,
	syntax.FormalParameter: _lookup_by_name,
	syntax.Subject: _lookup_all_else,
	syntax.Record: _lookup_all_else,
	syntax.SubTypeSpec: _lookup_all_else,
	syntax.FFI_Alias: _lookup_all_else,
	syntax.TypeAlias: _lookup_type_alias,
}

def lookup(dfn:ontology.Symbol, env:dict) -> LAZY_VALUE:
	try: fn = LOOKUP[type(dfn)]
	except KeyError: raise NotImplementedError(type(dfn), dfn)
	else: return fn(dfn, env)

def delay(dynamic_env:dict, item) -> LAZY_VALUE:
	# For two kinds of expression, there is no profit to delay:
	if isinstance(item, syntax.Literal): return item.value
	if isinstance(item, syntax.Lookup): return _eval_lookup(item, dynamic_env)
	# In less trivial cases, make a thunk and pass that instead.
	if isinstance(item, syntax.ValExpr): return Thunk(dynamic_env, item)
	# Some internals already have the data and it's no use making a (new) thunk.
	return item

class Closure(Procedure):
	""" The run-time manifestation of a sub-function: a callable value tied to its natal environment. """

	def __init__(self, static_link:dict, udf:syntax.UserDefinedFunction):
		self._udf = udf
		self._static_link = static_link
		self._params = [p.nom.text for p in udf.params]
		self._arity = len(self._params)
	
	def _name(self): return self._udf.nom.text

	def apply(self, args: list[LAZY_VALUE]) -> LAZY_VALUE:
		# Can't have arity mismatch anymore; the type checker catches it.
		assert self._arity == len(args), "Procedure %s expected %d args, got %d."%(self._name(), self._arity, len(args))
		inner_env = {STATIC_LINK:self._static_link}
		for param_name, a in zip(self._params, args):
			inner_env[param_name] = a
		return evaluate(self._udf.expr, inner_env)

class Primitive(Procedure):
	""" All parameters to primitive procedures are strict. Also a kind of value, like a closure. """
	def __init__(self, fn:callable):
		self._fn = fn
		
	def apply(self, args: list[LAZY_VALUE]) -> STRICT_VALUE:
		# Can't have arity mismatch anymore; the type checker catches it.
		return self._fn(*(actual_value(a) for a in args))

class Constructor(Procedure):
	def __init__(self, key:str, fields:list[str]):
		self.key = key
		self.fields = fields
	
	def apply(self, args: list[LAZY_VALUE]) -> Any:
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
	_prepare_root_environment(static_root)
	result = None  # Pacify the IDE
	for module in each_module:
		_prepare_global_scope(SOPHIE_GLOBALS, module.globals.local.items())
		for d in module.foreign:
			if d.linkage is not None:
				py_module = sys.modules[d.source.value]
				linkage = [SOPHIE_GLOBALS[ref.dfn] for ref in d.linkage]
				drivers.update(py_module.sophie_init(actual_value, *linkage))
				
		for expr in module.main:
			result = strict(expr, SOPHIE_GLOBALS)
			if isinstance(result, dict):
				tag = result.get("")
				if tag in drivers:
					drivers[tag](actual_value, result)
					continue
				dethunk(result)
				if tag == 'cons':
					result = decons(result)
			if result is not None:
				print(result)
	return result

SOPHIE_GLOBALS = {}
NIL:dict
CONS:Constructor

def _prepare_root_environment(static_root):
	global NIL, CONS
	SOPHIE_GLOBALS.clear()
	_prepare_global_scope(SOPHIE_GLOBALS, primitive.root_namespace.local.items())
	_prepare_global_scope(SOPHIE_GLOBALS, static_root.local.items())
	if 'nil' in static_root:
		NIL = SOPHIE_GLOBALS[static_root['nil']]
		CONS = SOPHIE_GLOBALS[static_root['cons']]
	else:
		NIL, CONS = None, None

def _prepare_global_scope(env:dict, items):
	for key, dfn in items:
		if isinstance(dfn, syntax.Record):
			env[dfn] = Constructor(key, dfn.spec.field_names())
		elif isinstance(dfn, (syntax.SubTypeSpec, syntax.TypeAlias)):
			if isinstance(dfn.body, (syntax.ArrowSpec, syntax.TypeCall)):
				pass
			elif isinstance(dfn.body, syntax.RecordSpec):
				env[dfn] = Constructor(key, dfn.body.field_names())
			elif dfn.body is None:
				env[dfn] = {"": key}
			else:
				raise ValueError("Tagged scalars (%r) are not implemented."%key)
		elif isinstance(dfn, syntax.UserDefinedFunction):
			env[dfn] = _lookup_udf(dfn, env)
		elif isinstance(dfn, ontology.NativeFunction):
			env[dfn] = _native_object(dfn)
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
