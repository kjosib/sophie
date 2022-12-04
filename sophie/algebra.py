"""
Evaluating types with a straight-up substitution model of computation.
  --  Simple and working is better than stuck in the mud.  --

Design Note:
-------------
Here, "constructor" is assumed to connect with something in the problem domain (i.e. the type system).
(For example, it might be a sum-type or new-type )
"""
from typing import Sequence
from collections import deque
from .ontology import Symbol, Term

#########################


class TypeVariable(Term):
	_counter = 0  # Each is distinct; there can be no capture.
	def __init__(self):
		self.nr = TypeVariable._counter
		TypeVariable._counter += 1
	def __repr__(self): return "<%s>" % self.nr
	def rewrite(self, delta: dict):
		# This is for trivial re-write during the manifest phase.
		return delta.get(self, self)
	def pull_rabbit(self, gamma:dict):
		# This is for the non-trivial re-write after a round of inference.
		while self in gamma: self = gamma[self]
		return self
	def fresh(self, gamma: dict):
		if self not in gamma:
			gamma[self] = TypeVariable()
		return gamma[self]
	def phylum(self): return TypeVariable
	def render(self, gamma: dict, delta):
		while self in gamma: self = gamma[self]
		if isinstance(self, TypeVariable):
			if self not in delta:
				delta[self] = "<%s>"%_name_variable(len(delta)+1)
			return delta[self]
		else:
			return self.render(gamma, delta)
	def poll(self, seen:set): seen.add(self)

def _name_variable(n):
	name = ""
	while n:
		n, remainder = divmod(n-1, 26)
		name = chr(97+remainder) + name
	return name

#########################

class Nominal(Term):
	"""
	This type forms the boundary between the unifier and the rest of the system.
	The unifier is meant to leave these closed.
	Value-language syntax will be privy to the "insides".
	"""
	def __init__(self, dfn: Symbol, params: Sequence[TypeVariable]):
		assert isinstance(dfn, Symbol)
		self.dfn = dfn
		self.params = params
	def phylum(self):
		return self.dfn
	def rewrite(self, delta: dict):
		return Nominal(self.dfn, [v.rewrite(delta) for v in self.params])
	def pull_rabbit(self, gamma:dict):
		return Nominal(self.dfn, [v.pull_rabbit(gamma) for v in self.params])
	def fresh(self, gamma: dict):
		return Nominal(self.dfn, [v.fresh(gamma) for v in self.params])
	def unify_with(self, other, enq):
		# Note to self: This is where sub-type logic might go,
		# perhaps in combination with a smarter .phylum() operation.
		for x,y in zip(self.params, other.params): enq(x,y)
		pass
	def __repr__(self):
		return str(self.dfn.nom.text) + ("[%s]" % (', '.join(map(str, self.params))) if self.params else "")
	def render(self, gamma: dict, delta):
		if self.params:
			args = [p.render(gamma, delta) for p in self.params]
			brick = "[%s]"%(", ".join(args))
		else:
			brick = ""
		return self.dfn.nom.text+brick
	def poll(self, seen:set):
		for p in self.params: p.poll(seen)

class Arrow(Term):
	def __init__(self, arg: Term, res: Term): self.arg, self.res = arg, res
	def __repr__(self): return "%s -> %s" % (self.arg, self.res)
	def rewrite(self, delta: dict): return Arrow(self.arg.rewrite(delta), self.res.rewrite(delta))
	def pull_rabbit(self, gamma: dict): return Arrow(self.arg.pull_rabbit(gamma), self.res.pull_rabbit(gamma))
	def fresh(self, gamma: dict): return Arrow(self.arg.fresh(gamma), self.res.fresh(gamma))
	def unify_with(self, other, enq):
		# Structural Equivalence
		enq(self.arg, other.arg)
		enq(self.res, other.res)
	def phylum(self): return Arrow
	def render(self, gamma: dict, delta):
		arg = self.arg.render(gamma, delta)
		res = self.res.render(gamma, delta)
		return "%s -> %s" % (arg, res)
	def poll(self, seen:set):
		self.arg.poll(seen)
		self.res.poll(seen)

class Product(Term):
	def __init__(self, fields: Sequence[Term]): self.fields = fields
	def __repr__(self): return "(%s)" % (",".join(map(str, self.fields)))
	def rewrite(self, delta: dict): return Product(tuple(t.rewrite(delta) for t in self.fields))
	def pull_rabbit(self, gamma: dict): return Product(tuple(t.pull_rabbit(gamma) for t in self.fields))
	def fresh(self, gamma: dict): return Product(tuple(t.fresh(gamma) for t in self.fields))
	def unify_with(self, other, enq):
		# Structural Equivalence
		for x, y in zip(self.fields, other.fields):
			enq(x, y)
	def phylum(self): return Product, len(self.fields)
	def render(self, gamma: dict, delta):
		args = [a.render(gamma, delta) for a in self.fields]
		return "(%s)" % (", ".join(args))
	def poll(self, seen:set):
		for k in self.fields: k.poll(seen)

#########################

