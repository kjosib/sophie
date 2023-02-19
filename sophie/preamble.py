"""
# Built-in / primitive definitions and types are in the docstring of this Python file.
# Native types flag, number, and string are installed separately in "native" Python.
# Also for the moment, I import (most of) Python's math library.

import:

foreign "math" where

	e, inf, nan, pi, tau : number;
	
	acos, acosh, asin, asinh, atan, atanh,
	ceil, cos, cosh, degrees, erf, erfc, exp, expm1,
	fabs, factorial, floor, gamma, gcd,
	isqrt, lcm, lgamma, log, log10, log1p, log2,
	modf, radians, sin, sinh, sqrt,
	tan, tanh, trunc, ulp : (number) -> number;
	
	isfinite, isinf, isnan : (number) -> flag;
	
	atan2, comb, copysign, dist, fmod, ldexp, log_base@"log",
	nextafter, perm, pow, remainder : (number, number) -> number;
	
end;

# A few of Python's standard math functions are trouble (currently).
	# ``log`` is bivalent: You can pass it one or two parameters. Sophie gets around this by aliasing ``log_base``.
	# ``dist`` computes Euclidean distance between two points specified as vectors, but Sophie still lacks these.
	# ``fsum``, ``prod``, and ``hypot`` also work on vectors; same problem. (Pure-Sophie versions are provided.)
	# ``frexp`` returns a tuple, which would confuse the evaluator. It needs an adapter to a known record type.

type:
	list[x] is CASE:
		 cons(head:x, tail:list[x]);
		 nil;
	ESAC;
	
	pair[a,b] is (fst:a, snd:b);
	
	drawing is (steps: list[turtle_step]);
	
	turtle_step is case:
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
		pensize(width:number);
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
		cons -> cons(xs.head, rest) if predicate(xs.head) else rest where
			rest = filter(predicate, xs.tail);
		end cons;
	esac;

	reduce(fn, a, xs) = case xs:
		nil -> a;
		cons -> reduce(fn, fn(a, xs.head), xs.tail);
	esac;
	
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
	product(xs) = reduce(mul, 1, xs) where mul(a,b) = a*b; end product;
	hypot(xs) = sqrt(sum(map(square, xs))) where square(x) = x*x; end hypot;
end.

"""

def _init():
	from . import front_end, resolution, primitive, diagnostics, manifest
	report = diagnostics.Report()
	report.set_path(__file__)
	preamble = front_end.parse_text(__doc__, __file__, report)
	if not report.issues:
		resolution.resolve_words(preamble, primitive.root_namespace, report)
	if not report.issues:
		manifest.type_module(preamble, report)
	if not report.issues:
		from . import type_inference
		type_inference.infer_types(preamble, report, verbose=False)
	if report.issues:
		report.complain_to_console()
		raise RuntimeError()
	else:
		primitive.LIST = preamble.globals['list'].typ
		return preamble.globals

static_root = _init()

def do_turtle_graphics(force, NIL, drawing):
	import turtle, tkinter
	root = tkinter.Tk()
	root.focus_force()
	root.title("Sophie: Turtle Graphics")
	screen = tkinter.Canvas(root, width=1000, height=1000)
	screen.pack()
	t = turtle.RawTurtle(screen)
	t.hideturtle()
	t.speed(0)
	t.screen.tracer(2^31)
	t.screen.delay(0)
	t.setheading(90)
	stepCount = 0
	steps = force(drawing["steps"])
	while steps is not NIL:
		stepCount += 1
		s = force(steps['head'])
		steps = force(steps['tail'])
		args = dict(s)  # Make a copy because of (deliberate) aliasing.
		tag = args.pop("")
		fn = getattr(t, tag)
		fn(*map(force, args.values()))  # Insertion-order is assured.
	t.screen.update()
	text = str(stepCount)+" turtle steps. Click the drawing or press any key to dismiss it."
	print(text)
	label = tkinter.Label(root, text=text)
	label.pack()
	root.bind("<ButtonRelease>", lambda event: root.destroy())
	root.bind("<KeyPress>", lambda event: root.destroy())
	tkinter.mainloop()

