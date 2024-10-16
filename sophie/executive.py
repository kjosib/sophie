"""
I decided to factor out the run-time from the executive.
This is the overall control for the run-time.
"""
import sys
from collections import deque
from . import syntax, primitive,  ontology
from .stacking import Frame, RootFrame, Activation
from .runtime import (
	force, _strict, Constructor, Primitive, Thunk,
	ActorClass, ActorTemplate, is_sophie_list, iterate_list,
	reset, install_overrides
)
from .resolution import RoadMap
from .scheduler import MAIN_QUEUE, SimpleTask

DRIVERS = {}

def run_program(roadmap:RoadMap):
	DRIVERS.clear()
	_set_strictures(roadmap.preamble)
	preamble_scope = roadmap.module_scopes[roadmap.preamble]
	root = _dynamic_root(preamble_scope)
	for module in roadmap.each_module:
		_set_strictures(module)
		env = Activation.for_module(root, module)
		_prepare(env, roadmap.module_scopes[module])
		for d in module.foreign:
			if d.linkage is not None:
				py_module = sys.modules[d.source.value]
				linkage = [env.fetch(ref.dfn) for ref in d.linkage]
				DRIVERS.update(py_module.sophie_init(*linkage) or ())
		install_overrides(env, module.user_operators)
		for expr in module.main:
			env.pc = expr
			MAIN_QUEUE.execute(SimpleTask(_display, expr, env))
		root.absorb(env)

def _display(expr, env):
	result = _strict(expr, env)
	if hasattr(result, "perform"):
		result.perform(env)
		return
	if is_sophie_list(result):
		result = list(iterate_list(result))
	elif isinstance(result, dict):
		tag = result.get("")
		if tag in DRIVERS:
			DRIVERS[tag](env, result)
			return
		dethunk(result)
	if result is not None:
		print(result)


def _set_strictures(module):
	for udf in module.all_fns + module.all_procs:
		udf.strictures = tuple(i for i, p in enumerate(udf.params) if p.is_strict)

def _dynamic_root(preamble_scope) -> RootFrame:
	root = RootFrame()
	_prepare(root, primitive.root_namespace)
	_prepare(root, preamble_scope)
	reset(lambda s:root.fetch(preamble_scope[s]))
	return root

def _prepare(env:Frame, namespace:ontology.NS):
	for key, dfn in namespace.local.items():
		if isinstance(dfn, syntax.Record):
			env.assign(dfn, Constructor(dfn, dfn.spec.field_names()))
		elif isinstance(dfn, (syntax.SubTypeSpec, syntax.TypeAlias)):
			if isinstance(dfn.body, (syntax.ArrowSpec, syntax.TypeCall)):
				pass
			elif isinstance(dfn.body, syntax.RecordSpec):
				env.assign(dfn, Constructor(dfn, dfn.body.field_names()))
			elif dfn.body is None:
				env.assign(dfn, {"": dfn})
			else:
				raise ValueError("Tagged scalars (%r) are not implemented."%key)
		elif isinstance(dfn, syntax.FFI_Alias):
			env.assign(dfn, _native_object(dfn))
		elif isinstance(dfn, syntax.Subroutine):
			env.declare(dfn)
		elif isinstance(dfn, syntax.UserAgent):
			env.assign(dfn, ActorClass(env, dfn) if dfn.members else ActorTemplate(env, dfn, ()))
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
	syntax.Role,
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

###############################################################################


