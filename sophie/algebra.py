"""
Evaluating types with a straight-up substitution model of computation.
  --  Simple and working is better than stuck in the mud.  --

Design Note:
-------------
Here, "constructor" is assumed to connect with something in the problem domain (i.e. the type system).
(For example, it might be a sum-type or new-type )
"""
from typing import Sequence
from .ontology import Symbol, Term

#########################


class TypeVariable(Term):
	_counter = 0  # Each is distinct; there can be no capture.
	def __init__(self):
		self.nr = TypeVariable._counter
		TypeVariable._counter += 1
	def __repr__(self): return "<%s>" % self.nr
	def visit(self, visitor): return visitor.on_variable(self)
	def fresh(self, gamma: dict):
		if self not in gamma:
			gamma[self] = TypeVariable()
		return gamma[self]
	def phylum(self): return TypeVariable
	def render(self, gamma: dict, delta):
		while self in gamma: self = gamma[self]
		if isinstance(self, TypeVariable):
			if self not in delta:
				delta[self] = "?%s"%_name_variable(len(delta)+1)
			return delta[self]
		else:
			return self.render(gamma, delta)
	def poll(self, seen:set): seen.add(self)
	def mentions(self, v): return v is self

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
	def visit(self, visitor): return visitor.on_nominal(self)
	def fresh(self, gamma: dict):
		return self if not self.params else Nominal(self.dfn, [v.fresh(gamma) for v in self.params])
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
	def mentions(self, v):
		return any(p.mentions(v) for p in self.params)

class Arrow(Term):
	def __init__(self, arg: Term, res: Term): self.arg, self.res = arg, res
	def __repr__(self): return "%s -> %s" % (self.arg, self.res)
	def visit(self, visitor): return visitor.on_arrow(self)
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
	def mentions(self, v):
		return self.arg.mentions(v) or self.res.mentions(v)

class Product(Term):
	def __init__(self, fields: Sequence[Term]): self.fields = fields
	def __repr__(self): return "(%s)" % (",".join(map(str, self.fields)))
	def visit(self, visitor): return visitor.on_product(self)
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
	def mentions(self, v):
		return any(p.mentions(v) for p in self.fields)

#########################

class Visitor:
	def on_variable(self, v:TypeVariable): pass
	def on_nominal(self, n:Nominal): pass
	def on_arrow(self, a:Arrow): pass
	def on_product(self, p:Product): pass

#########################

class Rewrite(Visitor):
	# This is for trivial re-write during the manifest phase.
	def __init__(self, gamma:dict):
		self.gamma = gamma
	def on_variable(self, v: TypeVariable):
		return self.gamma.get(v,v)
	def on_nominal(self, n: Nominal):
		return n if not n.params else Nominal(n.dfn, [p.visit(self) for p in n.params])
	def on_arrow(self, a: Arrow):
		return Arrow(a.arg.visit(self), a.res.visit(self))
	def on_product(self, p: Product):
		return Product(tuple(f.visit(self) for f in p.fields))
	
class PullRabbit(Rewrite):
	# This is for the non-trivial re-write during inference.
	def __init__(self, gamma: dict):
		super().__init__(gamma)
		
	def on_variable(self, v: TypeVariable):
		j = v
		while v in self.gamma: v = self.gamma[v]
		# if j is not v:
		# 	print("   ", j, ":=", v)
		return v if isinstance(v, TypeVariable) else v.visit(self)
