"""
These functions just exist as a support scaffolding for various test cases,
mainly of the type-checking scheme.
"""

def identity(x):
	return x

def compose(f, g):
	# This ought to work as follows, at least in principle:
	return lambda x: f(g(x))

