"""
Call-By-Need with Direct Interpretation
Absolutely simplest, most straight-forward possible implementation.

"""

from typing import Any, Union
from collections import namedtuple, deque
import abc
import inspect
from boozetools.support.symtab import NameSpace, NoSuchSymbol
from .preamble import static_root
from . import syntax, type_algebra

class LintError(RuntimeError): pass
class NotSupported(RuntimeError): pass

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
	while isinstance(it, Thunk):
		it = it.force()
	return it

def evaluate(dynamic_env:NameSpace, expr:syntax.Expr) -> LAZY_VALUE:
	# Hinkey double-dispatch would be faster as a dictionary look-up.
	# That's a side-quest, though.
	def strict(sub_expr): return actual_value(evaluate(dynamic_env, sub_expr))
	if isinstance(expr, syntax.Literal): return expr.value
	elif isinstance(expr, syntax.Lookup): return _look_up(dynamic_env, expr.name)
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
		raise NotSupported(type(expr), expr)

def delay(dynamic_env:NameSpace, item) -> LAZY_VALUE:
	# For two kinds of expression, there is no profit to delay:
	if isinstance(item, syntax.Literal): return item.value
	if isinstance(item, syntax.Lookup): return _look_up(dynamic_env, item.name)
	# In less trivial cases, make a thunk and pass that instead.
	if isinstance(item, syntax.Expr): return Thunk(dynamic_env, item)
	# Some internals already have the data and it's no use making a (new) thunk.
	return item

def _look_up(dynamic_env:NameSpace, name:syntax.Token) -> LAZY_VALUE:
	try:
		return dynamic_env[name.text]
	except NoSuchSymbol:
		guilty_function:syntax.Function = dynamic_env.place
		error = "Function %r uses undefined name %r. Some day this will get caught before run-time."
		raise LintError(error%(guilty_function.signature.name.text, name.text))

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
	def __init__(self, fields):
		self.fields = fields
	
	def apply(self, caller_env: NameSpace, args: list[syntax.Expr]) -> Any:
		assert len(args) == len(self.fields)
		structure = dict(zip(self.fields, [delay(caller_env, expr) for expr in args]))
		return structure


def run_module(module: syntax.Module):
	module_env = NameSpace(parent=dynamic_root, place=module)
	for key, dfn in module.namespace.local.items():
		if isinstance(dfn, syntax.Function):
			module_env[key] = close_one_function(module_env, dfn)
		elif isinstance(dfn, syntax.TypeDecl):
			pass
		else:
			print("Don't know how to deal with %r %r"%(type(dfn), key))
	for expr in module.main:
		result = evaluate(module_env, expr)
		if isinstance(result, Thunk): result = actual_value(result)
		if isinstance(result, dict): dethunk(result)
		print(result)
	return result

def dethunk(result:dict):
	dict_queue = deque()
	dict_queue.append(result)
	while dict_queue:
		work_dict = dict_queue.popleft()
		for k,v in work_dict.items():
			if isinstance(v, Thunk): work_dict[k] = v = actual_value(v)
			if isinstance(v, dict): dict_queue.append(v)

def _fill_dynamic_root():
	for key, dfn in static_root.local.items():
		if isinstance(dfn, type_algebra.ProductType):
			dynamic_root[key] = Constructor(dfn.slots)
		elif callable(dfn):
			dynamic_root[key] = Primitive(key, dfn)
		else:
			dynamic_root[key] = dfn

dynamic_root = NameSpace(place=None)
_fill_dynamic_root()
