"""
Types are functions.
For now, Sophie evaluates types in (a version of) the simply-typed lambda calculus.

"""
from typing import Sequence, Mapping
from collections import deque

#########################

#########################


class Term:
	""" It's a term re-writing system to compute types. """
	rank = 0   # Rank for all structural types.
	def rewrite(self, gamma:Mapping): raise NotImplementedError(type(self))
	def instantiate(self, gamma:dict): raise NotImplementedError(type(self))

class TypeVariable(Term):
	_counter = 0   # Each is distinct; there is thus no such thing as capture.
	def __init__(self):
		self.nr = TypeVariable._counter
		TypeVariable._counter += 1
	def __repr__(self): return "<%s>"%self.nr
	def rewrite(self, gamma:Mapping): return gamma.get(self, self)
	def instantiate(self, gamma:dict):
		if self not in gamma:
			gamma[self] = TypeVariable()
		return gamma[self]


#########################

class Alias(Term):
	""" Think of this as essentially a pending function-call. """
	def __init__(self, ctor:Term, mapping: Mapping[TypeVariable, Term]):
		# Keys are formal params used by constructor.
		self.ctor = ctor
		self.mapping = mapping
		self.rank = 1 + ctor.rank
	def __repr__(self):
		mapping = ";  ".join("%s:=%s"%i for i in self.mapping.items() )
		return "%s[%s]"%(self.ctor, mapping)
	def rewrite(self, gamma:Mapping):
		# This is just a change-of-variables.
		# Can do this without losing information
		new_mapping = { k:gamma.get(v,v) for k,v in self.mapping.items() }
		return Alias(self.ctor, new_mapping)
	def demote(self):
		# Return a less-aliased form of the same type.
		# If you want to know whether two aliases are compatible,
		# Demote the higher-ranking one repeatedly until you get items of the same rank.
		# Then compare the resulting items.
		return self.ctor.rewrite(self.mapping)


class PrimitiveType(Term):
	""" Presumably add clerical details here. """
	def __init__(self, name): self.name = name
	def __repr__(self): return "<%s>"%self.name
	def rewrite(self, gamma:Mapping): return self
	def has_value_domain(self): return False  # .. HACK ..
	def instantiate(self, gamma:dict): return self

class Arrow(Term):
	def __init__(self, arg: Term, res: Term): self.arg, self.res = arg, res
	def __repr__(self): return "%s -> %s"%(self.arg, self.res)
	def rewrite(self, gamma:Mapping): return Arrow(self.arg.rewrite(gamma), self.res.rewrite(gamma))
	def instantiate(self, gamma:dict):
		arg, res = self.arg.instantiate(gamma), self.res.instantiate(gamma)
		if self.arg is arg and self.res is res: return self
		else: return Arrow(arg, res)


class Product(Term):
	# The proper "destructor" is an indexed-access operation.
	# That's not accessible idiomatically; it's an internal thing.
	def __init__(self, fields: Sequence[Term]): self.fields = fields
	def __repr__(self): return "(%s)"%(",".join(map(str, self.fields)))
	def rewrite(self, gamma:Mapping): return Product(tuple(t.rewrite(gamma) for t in self.fields))
	def instantiate(self, gamma:dict):
		fields = tuple(t.instantiate(gamma) for t in self.fields)
		if all(a is b for a,b in zip(fields, self.fields)): return self
		else: return Product(fields)

class Record(Term):
	# The proper destructor is a field-access operation.
	def __init__(self, symbol:str, index, product:Product):
		self.symbol = symbol
		self.index = index
		self.product = product
	def __repr__(self): return "<record %s>"%self.symbol
	def rewrite(self, gamma:Mapping):
		return Record(self.symbol, self.index, self.product.rewrite(gamma))

class Tagged(Term):
	# The proper destructor here is pattern-matching.
	def __init__(self, symbol:str, body:Term):
		self.symbol = symbol
		self.body = body
	def __repr__(self): return "%s %s"%(self.symbol, self.body)
	def rewrite(self, gamma:Mapping): return Tagged(self.symbol, self.body.rewrite(gamma))

#########################

class Incompatible(TypeError):
	pass

def unify(peas:Term, carrots:Term) -> dict[TypeVariable:Term]:
	def proxy(term):
		while term in gamma: term = gamma[term]
		return term
	def enq(a,b): queue.append((a,b))
	def U(A, B):
		A, B = proxy(A), proxy(B)
		if A is B: return
		elif type(A) is TypeVariable: gamma[A] = B
		elif type(B) is TypeVariable: gamma[B] = A
		else:
			while A.rank != B.rank:
				if A.rank > B.rank:
					A = A.demote()
				else:
					B = B.demote()
			T = type(A)
			if T is not type(B):
				raise Incompatible(A,B)
			elif T is Alias:
				if A.symbol == B.symbol:
					pass
				else:
					raise Incompatible(A,B)
			elif T is PrimitiveType:
				# Nominal Equivalence
				if A is not B:
					raise Incompatible(A,B)
			elif T is Arrow:
				# Structural Equivalence
				enq(A.arg, B.arg)
				enq(A.res, B.res)
			elif T is Product:
				# Structural Equivalence
				if len(A.fields) != len(B.fields):
					raise Incompatible(A,B)
				for x,y in zip(A.fields,B.fields):
					enq(x,y)
	
	gamma = {}
	queue = deque()
	enq(peas, carrots)
	while queue:
		U(*queue.popleft())
	return gamma
