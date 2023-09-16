"""
I decided to factor out the run-time from the executive.
This is the overall control for the run-time.
"""
import sys
from collections import deque
from . import syntax, primitive, runtime, ontology
from .stacking import Frame, RootFrame, Activation
from .runtime import (
	force, _strict, Constructor, Primitive, Thunk,
	Action, ActorClass, ActorTemplate
)
from .resolution import RoadMap
from .scheduler import MAIN_QUEUE


def run_program(roadmap:RoadMap):
	class MainTask:
		@staticmethod
		def proceed():
			result.perform()

	drivers = {}
	preamble_scope = roadmap.module_scopes[roadmap.preamble]
	root = _dynamic_root(preamble_scope)
	result = None
	for module in roadmap.each_module:
		env = Activation.for_module(root, module)
		_prepare(env, roadmap.module_scopes[module])
		for d in module.foreign:
			if d.linkage is not None:
				py_module = sys.modules[d.source.value]
				linkage = [env.fetch(ref.dfn) for ref in d.linkage]
				drivers.update(py_module.sophie_init(*linkage))
		for expr in module.main:
			env.pc = expr
			result = _strict(expr, env)
			if isinstance(result, Action):
				MAIN_QUEUE.perform(MainTask)
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
		# This kludge makes QualifiedReference work,
		# at least until a proper linkage model takes over.
		root._bindings.update(env._bindings)
	return result

def _dynamic_root(static_root) -> RootFrame:
	root = RootFrame()
	_prepare(root, primitive.root_namespace)
	_prepare(root, static_root)
	if 'nil' in static_root:
		runtime.NIL = root.fetch(static_root['nil'])
		runtime.CONS = root.fetch(static_root['cons'])
	else:
		runtime.NIL, runtime.CONS = None, None
	return root

def _prepare(env:Frame, namespace:ontology.NS):
	for key, dfn in namespace.local.items():
		if isinstance(dfn, syntax.Record):
			env.assign(dfn, Constructor(key, dfn.spec.field_names()))
		elif isinstance(dfn, (syntax.SubTypeSpec, syntax.TypeAlias)):
			if isinstance(dfn.body, (syntax.ArrowSpec, syntax.TypeCall)):
				pass
			elif isinstance(dfn.body, syntax.RecordSpec):
				env.assign(dfn, Constructor(key, dfn.body.field_names()))
			elif dfn.body is None:
				env.assign(dfn, {"": key})
			else:
				raise ValueError("Tagged scalars (%r) are not implemented."%key)
		elif isinstance(dfn, syntax.FFI_Alias):
			env.assign(dfn, _native_object(dfn))
		elif isinstance(dfn, syntax.UserFunction):
			env.declare(dfn)
		elif isinstance(dfn, syntax.UserAgent):
			env.assign(dfn, ActorClass(env, dfn) if dfn.fields else ActorTemplate(env, dfn, ()))
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
	syntax.ArrowSpec,
	syntax.TypeCall,
	syntax.Variant,
	syntax.Opaque,
	syntax.Interface,
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

###############################################################################


