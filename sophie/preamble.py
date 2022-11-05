"""
# Built-in / primitive definitions and types are in the docstring of this Python file.
# Native types flag, number, and string are installed separately in native Python.
# Also for the moment, I import (most of) Python's math library directly into the primitive-root namespace.

type:
	list[x] is CASE
		 cons(head:x, tail:list[x]);
		 nil;
	ESAC;
define:
	any(xs) = xs != nil and (xs.head or any(xs.tail));
	all(xs) = xs == nil or (xs.head and all(xs.tail));
	map(fn, xs) = nil if xs == nil else cons(fn(xs.head), map(fn, xs.tail));
	reduce(fn, zero, xs) = fold(zero, xs) where
		fold(a, xs) = a if xs == nil else fold(fn(a, xs.head), xs.tail);
	end reduce;
	filter(predicate, xs) = case
		when xs == nil then nil;
		when predicate(xs.head) then cons(xs.head, rest);
		else rest;
	esac where
		rest = filter(predicate, xs.tail);
	end filter;
	sum(xs) = reduce(add, 0, xs) where add(a,b) = a+b; end sum;
	take(n, xs) = nil if n < 1 else cons(xs.head, take(n-1, xs.tail));
	hypot(xs) = sqrt(sum(map(square, xs))) where square(x) = x*x; end hypot;
end.

"""

def _init():
	from boozetools.support.symtab import NameSpace
	from . import front_end, compiler
	from .syntax import PrimitiveType, Module
	import math
	NON_WORKING = {"hypot", "log"}
	primitive_root = NameSpace(place=None)
	primitive_root['flag'] = PrimitiveType()
	primitive_root['number'] = PrimitiveType()
	primitive_root['string'] = PrimitiveType()
	for name in dir(math):
		if not (name.startswith("_") or name in NON_WORKING):
			primitive_root[name] = getattr(math, name)
	primitive_root['log'] = lambda x:math.log(x)
	primitive_root['log_base'] = lambda x,b: math.log(x, b)
	
	preamble = front_end.parse_text(__doc__, __file__)
	if isinstance(preamble, Module):
		issues = compiler.resolve_words(preamble, primitive_root)
	else:
		issues = [preamble]
	if issues:
		front_end.complain(issues)
		raise ValueError()
	else:
		return preamble.namespace

static_root = _init()

