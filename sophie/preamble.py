"""
# Built-in / primitive definitions and types are in the docstring of this Python file.
# Native types flag, number, and string are installed separately in native Python.
# Also for the moment, I import (most of) Python's math library directly into the primitive-root namespace.

type:
	list[x] is CASE
		 cons(head:x, tail:list[x]);
		 nil;
	ESAC;
	
	drawing is (steps: list[turtle_step]);
	
	turtle_step is case
		forward(distance:number);
		backward(distance:number);
		right(angle:number);
		left(angle:number);
		goto(x:number, y:number);
		setheading(angle:number);
		home;
		pendown;
		penup;
		color(color:string);
		pensize(width:string);
		showturtle;
		hideturtle;
	esac;
	
define:
	id(x) = x;
	any(xs) = case xs: nil -> no; cons -> xs.head or any(xs.tail); esac;
	all(xs) = case xs: nil -> yes; cons -> xs.head and all(xs.tail); esac;
	
	map(fn, xs) = case xs:
		nil -> nil;
		cons -> cons(fn(xs.head), map(fn, xs.tail));
	esac;
	
	filter(predicate, xs) = case xs:
		nil -> nil;
		cons -> cons(xs.head, rest) if predicate(xs.head) else rest;
	esac where
		rest = filter(predicate, xs.tail);
	end filter;
	
	reduce(fn, a, xs) = case xs:
		nil -> a;
		cons -> reduce(fn, fn(a, xs.head), xs.tail);
	esac;
	
	expand(fn, acc, xs) = case xs:
		nil -> nil;
		cons -> cons(item, expand(fn, item, xs.tail));
	esac where
		item = fn(acc, xs.head);
	end expand;
	
	cat(xs,ys) = case xs:
		nil -> ys;
		cons -> cons(xs.head, cat(xs.tail, ys));
	esac;
	
	flat(xss) = case xss:
		nil -> nil;
		cons -> cat(xss.head, flat(xss.tail));
	esac;
	
	take(n, xs) = nil if n < 1 else case xs:
		nil -> nil;
		cons -> cons(xs.head, take(n-1, xs.tail));
	esac;
	
	skip(n, xs) = xs if n < 1 else case xs:
		nil -> nil;
		cons -> skip(n-1, xs.tail);
	esac;
	
	sum(xs) = reduce(add, 0, xs) where add(a,b) = a+b; end sum;
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
	primitive_root['yes'] = True
	primitive_root['no'] = False
	
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
