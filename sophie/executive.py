"""
I decided to factor out the run-time from the executive.
This is the overall control for the run-time.
"""
import sys
from collections import deque
from typing import  Sequence
from . import syntax, primitive, runtime, ontology
from .stacking import StackBottom
from .runtime import force, _strict, BoundMethod, Message, drain_queue, Constructor, Primitive, Thunk

def run_program(static_root, each_module: Sequence[syntax.Module]):
	drivers = {}
	env = StackBottom(None)
	_prepare_root_environment(env, static_root)
	result = None
	for module in each_module:
		env.current_path = module.path
		_prepare_global_scope(env, module.globals.local.items())
		for d in module.foreign:
			if d.linkage is not None:
				py_module = sys.modules[d.source.value]
				linkage = [env.bindings[ref.dfn] for ref in d.linkage]
				drivers.update(py_module.sophie_init(*linkage))
		for expr in module.main:
			env.pc = expr
			result = _strict(expr, env)
			if isinstance(result, (BoundMethod, Message)):
				result.enqueue()
				drain_queue()
				continue
			if isinstance(result, dict):
				tag = result.get("")
				if tag in drivers:
					drivers[tag](env, result)
					continue
				dethunk(result)
				if tag == 'cons':
					result = decons(result)
			if result is not None:
				print(result)
	return result


def _prepare_root_environment(env:StackBottom, static_root):
	_prepare_global_scope(env, primitive.root_namespace.local.items())
	_prepare_global_scope(env, static_root.local.items())
	if 'nil' in static_root:
		runtime.NIL = env.bindings[static_root['nil']]
		runtime.CONS = env.bindings[static_root['cons']]
	else:
		runtime.NIL, runtime.CONS = None, None

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
		elif isinstance(dfn, syntax.FFI_Alias):
			env.bindings[dfn] = _native_object(dfn)
		elif type(dfn) in _ignore_these:
			pass
		else:
			raise ValueError("Don't know how to deal with %r %r"%(type(dfn), key))

def _native_object(dfn:syntax.FFI_Alias):
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
			if isinstance(v, Thunk): work_dict[k] = v = force(v)
			if isinstance(v, dict): dict_queue.append(v)

def decons(item:dict) -> list:
	result = []
	while isinstance(item, dict) and item.get("") == 'cons':
		result.append(item['head'])
		item = item['tail']
	if item is not runtime.NIL:
		result.append(item)
	return result


