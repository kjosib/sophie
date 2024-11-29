"""
Build the primitive namespace.
Also, some bits used for operator syntax
and the primitive literal types
"""

from .ontology import Nom
from . import calculus, syntax
from .space import Scope

root_scope = Scope.fresh()
built_in_type_names = []

def _built_in_type(name:str) -> calculus.OpaqueType:
	built_in_type_names.append(name)
	symbol = syntax.Opaque(Nom(name, None), ())
	root_scope.types.define(symbol)
	return calculus.OpaqueType(symbol)

literal_number = _built_in_type("number")
literal_string = _built_in_type("string")
literal_flag = _built_in_type("flag")
literal_act = _built_in_type("act")

