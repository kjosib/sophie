"""
Evaluating types with a straight-up substitution model of computation.
  --  Simple and working is better than stuck in the mud.  --

Design Note:
-------------
Here, "constructor" is assumed to connect with something in the problem domain (i.e. the type system).
(For example, it might be a sum-type or new-type )
"""
from typing import Sequence, Any
from collections import deque
#########################

class Term:
	""" It's a term re-writing system to compute types. """
	def rewrite(self, gamma: dict): raise NotImplementedError(type(self))
	def fresh(self, gamma: dict): raise NotImplementedError(type(self))
	def phylum(self): raise NotImplementedError(type(self))

class TypeVariable(Term):
	_counter = 0  # Each is distinct; there is thus no such thing as capture.
	def __init__(self):
		self.nr = TypeVariable._counter
		TypeVariable._counter += 1
	def __repr__(self): return "<%s>" % self.nr
	def rewrite(self, gamma: dict):
		return gamma.get(self, self)
	def fresh(self, gamma:dict):
		if self not in gamma:
			gamma[self] = TypeVariable()
		return gamma[self]
	
#########################

class Nominal(Term):
	"""
	This type forms the boundary between the unifier and the rest of the system.
	The unifier is meant to leave these closed.
	Value-language syntax will be privy to the "insides".
	"""
	def __init__(self, semantic: Any, params: Sequence[TypeVariable]):
		assert hasattr(semantic, "dfn")
		self.semantic = semantic
		self.params = params
	def phylum(self): return self.semantic
	def rewrite(self, gamma: dict):
		return Nominal(self.semantic, [v.rewrite(gamma) for v in self.params])
	def fresh(self, gamma: dict):
		return Nominal(self.semantic, [v.fresh(gamma) for v in self.params])
	def unify_with(self, other, enq):
		# Note to self: This is where sub-type logic might go,
		# perhaps in combination with a smarter .phylum() operation.
		for x,y in zip(self.params, other.params): enq(x,y)
		pass
	def __repr__(self):
		return str(self.semantic.key)+("[%s]"%(', '.join(map(str, self.params))) if self.params else "")


class Arrow(Term):
	def __init__(self, arg: Term, res: Term): self.arg, self.res = arg, res
	def __repr__(self): return "%s -> %s" % (self.arg, self.res)
	def rewrite(self, gamma: dict): return Arrow(self.arg.rewrite(gamma), self.res.rewrite(gamma))
	def fresh(self, gamma: dict): return Arrow(self.arg.fresh(gamma), self.res.fresh(gamma))
	def unify_with(self, other, enq):
		# Structural Equivalence
		enq(self.arg, other.arg)
		enq(self.res, other.res)
	def phylum(self): return Arrow

class Product(Term):
	def __init__(self, fields: Sequence[Term]): self.fields = fields
	def __repr__(self): return "(%s)" % (",".join(map(str, self.fields)))
	def rewrite(self, gamma: dict): return Product(tuple(t.rewrite(gamma) for t in self.fields))
	def fresh(self, gamma: dict): return Product(tuple(t.fresh(gamma) for t in self.fields))
	def unify_with(self, other, enq):
		# Structural Equivalence
		if len(self.fields) == len(other.fields):
			for x, y in zip(self.fields, other.fields): enq(x, y)
		else: raise Incompatible(self, other)
	def phylum(self): return Product, len(self.fields)

#########################

class Incompatible(Exception):
	pass


def unify(peas: Term, carrots: Term) -> dict[TypeVariable:Term]:
	def proxy(term):
		while term in gamma: term = gamma[term]
		return term
	def enq(a, b): queue.append((a, b))
	def U(a, b):
		a, b = proxy(a), proxy(b)
		if a is b:
			return
		elif type(a) is TypeVariable:
			gamma[a] = b
		elif type(b) is TypeVariable:
			gamma[b] = a
		elif a.phylum() == b.phylum():
			a.unify_with(b, enq)
		else:
			raise Incompatible(a, b)

	gamma = {}
	queue = deque()
	enq(peas, carrots)
	while queue:
		U(*queue.popleft())
	return gamma


