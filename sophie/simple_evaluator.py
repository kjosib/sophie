"""
Call-By-Need with Direct Interpretation
Absolutely simplest, most straight-forward possible implementation.

"""
import sys
from typing import Any, Union
from collections import namedtuple, deque
import abc
import inspect
from boozetools.support.symtab import NameSpace, NoSuchSymbol
from .preamble import static_root
from . import syntax

class Procedure(abc.ABC):
	""" A run-time object that can be applied with arguments. """
	@abc.abstractmethod
	def apply(self, caller_env:NameSpace, args:list[syntax.Expr]) -> Any:
		pass

STRICT_VALUE = Union[int, float, str, Procedure, namedtuple, "Closure"]

ABSENT = object()
class Thunk:
	""" A kind of not-yet-value which can be forced. """
	def __init__(self, dynamic_env: NameSpace, expr: syntax.Expr):
		assert isinstance(expr, syntax.Expr), type(expr)
		self._dynamic_env = dynamic_env
		self._expr = expr
		self._value = ABSENT
		
	def force(self) -> STRICT_VALUE:
		if self._value is ABSENT:
			self._value = actual_value(evaluate(self._dynamic_env, self._expr))
			del self._dynamic_env, self._expr
		return self._value
	
	def __str__(self):
		if self._value is ABSENT:
			return "<Thunk: %s>"%self._expr
		else:
			return str(self._value)

LAZY_VALUE = Union[STRICT_VALUE, Thunk]

def actual_value(it:LAZY_VALUE) -> STRICT_VALUE:
	'''
	While this will not return a thunk as such,
	it may return a structure which contains thunks.
	'''
	while isinstance(it, Thunk):
		it = it.force()
	return it

def evaluate(dynamic_env:NameSpace, expr:syntax.Expr) -> LAZY_VALUE:
	# Hinkey double-dispatch might be faster as a dictionary look-up.
	# That's a side-quest, though.
	def strict(sub_expr): return actual_value(evaluate(dynamic_env, sub_expr))
	if isinstance(expr, syntax.Literal): return expr.value
	elif isinstance(expr, syntax.Lookup): return dynamic_env[expr.name.text]
	elif isinstance(expr, syntax.BinExp):
		return expr.op(strict(expr.lhs), strict(expr.rhs))
	elif isinstance(expr, syntax.UnaryExp):
		return expr.op(strict(expr.arg))
	elif isinstance(expr, syntax.ShortCutExp):
		lhs = strict(expr.lhs)
		assert isinstance(lhs, bool)
		return lhs if lhs == expr.keep else strict(expr.rhs)
	elif isinstance(expr, syntax.Call):
		procedure = strict(expr.fn_exp)
		assert isinstance(procedure, Procedure)
		return procedure.apply(dynamic_env, expr.args)
	elif isinstance(expr, syntax.Cond):
		if_part = strict(expr.if_part)
		sequel = expr.then_part if if_part else expr.else_part
		return delay(dynamic_env, sequel)
	elif isinstance(expr, syntax.FieldReference):
		lhs = strict(expr.lhs)
		key = expr.field_name.text
		if isinstance(lhs, dict): return lhs[key]
		else: return getattr(lhs, key)
	elif isinstance(expr, syntax.ExplicitList):
		cons = dynamic_root['cons']
		assert isinstance(cons, Constructor)
		it = None
		for sx in reversed(expr.elts):
			it = cons.apply(dynamic_env, [sx, it])
		return it
	# elif isinstance(expr, syntax.Comprehension):  # Undecided how just yet.
	else:
		raise NotImplementedError(type(expr), expr)

def delay(dynamic_env:NameSpace, item) -> LAZY_VALUE:
	# For two kinds of expression, there is no profit to delay:
	if isinstance(item, syntax.Literal): return item.value
	if isinstance(item, syntax.Lookup): return dynamic_env[item.name.text]
	# In less trivial cases, make a thunk and pass that instead.
	if isinstance(item, syntax.Expr): return Thunk(dynamic_env, item)
	# Some internals already have the data and it's no use making a (new) thunk.
	return item

class Closure(Procedure):
	""" The run-time manifestation of a sub-function: a callable value tied to its natal environment. """

	def __init__(self, static_link:NameSpace, udf:syntax.Function):
		self._udf = udf
		self._static_link = static_link
		self._params = [p.name.text for p in udf.signature.params or ()]
		self._arity = len(self._params)
	
	def _name(self): return self._udf.signature.name.text

	def apply(self, caller_env:NameSpace, args:list[syntax.Expr]) -> LAZY_VALUE:
		if self._arity != len(args):
			raise TypeError("Procedure %s expected %d args, got %d."%(self._name(), self._arity, len(args)))
		inner_env = self._static_link.new_child(self._udf)
		for param_name, expr in zip(self._params, args):
			assert isinstance(expr, syntax.Expr), "%s :: %s given %r"%(self._name(), param_name, expr)
			inner_env[param_name] = delay(caller_env, expr)
		for key, fn in self._udf.sub_fns.items():
			inner_env[key] = close_one_function(inner_env, fn)
		return delay(inner_env, self._udf.expr)

def close_one_function(env:NameSpace, udf:syntax.Function):
	if udf.signature.params:
		return Closure(env, udf)
	elif udf.sub_fns:
		inner_env = env.new_child(udf)
		for inner_key, inner_function in udf.sub_fns:
			inner_env[inner_key] = close_one_function(inner_env, inner_function)
		return delay(inner_env, udf.expr)
	else:
		return delay(env, udf.expr)

class Primitive(Procedure):
	""" All parameters to primitive procedures are strict. Also a kind of value, like a closure. """
	def __init__(self, key:str, native):
		assert isinstance(key, str)
		assert callable(native)
		self._key = key
		self._native = native
		self._params = list(inspect.signature(native).parameters.keys())
		self._arity = len(self._params)
		
	def apply(self, caller_env:NameSpace, args:list[syntax.Expr]) -> STRICT_VALUE:
		if self._arity != len(args):
			message = "Native procedure %s expected %d args, got %d."
			raise TypeError(message%(self._key, self._arity, len(args)))
		values = [actual_value(evaluate(caller_env, a)) for a in args]
		return self._native(*values)

class Constructor(Procedure):
	def __init__(self, key:str, fields:list[str]):
		self.key = key
		self.fields = fields
	
	def apply(self, caller_env: NameSpace, args: list[syntax.Expr]) -> Any:
		assert len(args) == len(self.fields)
		structure = {"":self.key}
		for field, expr in zip(self.fields, args):
			structure[field] = delay(caller_env, expr)
		return structure

def run_module(module: syntax.Module):
	module_env = dynamic_root.new_child(module)
	_prepare_global_scope(module_env, module.namespace.local.items())
	for expr in module.main:
		result = evaluate(module_env, expr)
		if isinstance(result, Thunk): result = actual_value(result)
		if isinstance(result, dict): dethunk(result)
		print(result)
	return result

def _prepare_global_scope(dynamic_env:NameSpace, items):
	for key, dfn in items:
		if isinstance(dfn, syntax.Function):
			dynamic_env[key] = close_one_function(dynamic_env, dfn)
		elif isinstance(dfn, syntax.TypeSummand):
			if dfn.body:
				dynamic_env[key] = Constructor(key, dfn.body.fields())
			elif key != 'NIL':
				dynamic_env[key] = Constructor(key, [])
		elif isinstance(dfn, (syntax.TypeDecl, syntax.ProductType)):
			dynamic_env[key] = Constructor("", dfn.fields())
		elif callable(dfn):
			dynamic_root[key] = Primitive(key, dfn)
		elif isinstance(dfn, (float, int, str, bytes)):
			dynamic_root[key] = dfn
		elif type(dfn) in _ignore_these:
			pass
		else:
			dynamic_root[key] = dfn
			print("Don't know how to deal with %r %r"%(type(dfn), key), file=sys.stderr)

_ignore_these = {
	syntax.ArrowType,
	syntax.PrimitiveType,
	syntax.Token,
	syntax.TypeCall,
	syntax.UnionType,
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

dynamic_root = NameSpace(place=None)
_prepare_global_scope(dynamic_root, static_root.parent.local.items())
_prepare_global_scope(dynamic_root, static_root.local.items())
