"""
I decided to factor out the run-time from the executive.
This is the overall control for the run-time.
"""
import sys
from collections import deque
from .. import syntax
from .evaluator import Thunk, force, perform
from .values import Constructor, Primitive, ActorClass, ActorTemplate, close
from .runtime import (
	_strict, GLOBAL_SCOPE,
	is_sophie_list, iterate_list,
	reset_runtime, install_overrides
)
from ..resolution import RoadMap
from .scheduler import MAIN_QUEUE, SimpleTask

DRIVERS = {}

def run_program(roadmap:RoadMap):
	DRIVERS.clear()
	GLOBAL_SCOPE.clear()
	_set_strictures(roadmap.preamble)
	_prepare(roadmap.preamble)
	reset_runtime(roadmap.export_scopes[roadmap.preamble])
	for module in roadmap.each_module:
		_set_strictures(module)
		_prepare(module)
		for d in module.foreign:
			if d.linkage is not None:
				py_module = sys.modules[d.source.value]
				linkage = [GLOBAL_SCOPE[ref.dfn] for ref in d.linkage]
				DRIVERS.update(py_module.sophie_init(*linkage) or ())
		install_overrides(module.user_operators)
		for expr in module.main:
			MAIN_QUEUE.execute(SimpleTask(_display, expr))

def _display(expr):
	result = _strict(expr, GLOBAL_SCOPE)
	if hasattr(result, "perform"):
		perform(result)
		return
	if is_sophie_list(result):
		result = list(iterate_list(result))
	elif isinstance(result, dict):
		tag = result.get("")
		if tag in DRIVERS:
			DRIVERS[tag](result)
			return
		dethunk(result)
	if result is not None:
		print(result)


def _set_strictures(module):
	for udf in module.all_fns + module.all_procs:
		udf.strictures = tuple(i for i, p in enumerate(udf.params) if p.is_strict)

def _prepare(module:syntax.Module):
	for ifs in module.foreign: _prepare_foreign(ifs)
	for typ in module.types: _prepare_type(typ)
	for actor in module.actors: _prepare_actor(actor)
	close(GLOBAL_SCOPE, module.top_subs)
	install_overrides(module.user_operators)

def _prepare_foreign(ifs:syntax.ImportForeign):
	for group in  ifs.groups:
		for dfn in group.symbols:
			native_object = Primitive(dfn.val) if callable(dfn.val) else dfn.val
			GLOBAL_SCOPE[dfn] = native_object

def _prepare_type(typ:syntax.TypeDefinition):
	def construct(dfn): GLOBAL_SCOPE[dfn] = Constructor(dfn, dfn.spec.field_names())
	if isinstance(typ, syntax.RecordSymbol):construct(typ)
	elif isinstance(typ, syntax.VariantSymbol):
		for case in typ.type_cases:
			if isinstance(case, syntax.RecordTag): construct(case)
			elif isinstance(case, syntax.EnumTag): GLOBAL_SCOPE[case] = {"": case}
	
def _prepare_actor(actor):
	GLOBAL_SCOPE[actor] = ActorClass(actor) if actor.fields else ActorTemplate(actor, ())


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


