"""
Build the primitive namespace.
Also, some bits used for operator syntax
and the primitive literal types
"""

from .ontology import NS, Nom
from . import calculus, syntax

root_namespace = NS(place=None)

def _built_in_type(name:str) -> calculus.OpaqueType:
	symbol = syntax.Opaque(Nom(name, None), ())
	term = calculus.OpaqueType(symbol)
	root_namespace[name] = symbol
	return term

literal_number = _built_in_type("number")
literal_string = _built_in_type("string")
literal_flag = _built_in_type("flag")
literal_act = _built_in_type("act")

