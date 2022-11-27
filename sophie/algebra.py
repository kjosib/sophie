"""
Evaluating types with a substitution-by-need model of computation.
"""
from typing import Sequence, Mapping
from collections import deque
from .ontology import SymbolTableEntry, Term, TypeVariable, PrimitiveType
#########################

class Apply(Term):
	"""
	If you squint, this is basically a thunk.
	The "environment" is a bit simpler because all the variables are distinct and we know which ones are free.
	"""
	def __init__(self, symbol:SymbolTableEntry, actuals:Mapping[TypeVariable, Term]):
		assert isinstance(symbol, SymbolTableEntry)
		assert set(actuals.keys()).issuperset(symbol.quantifiers)
		free = frozenset().union(*[arg.free for arg in actuals.values()])
		super().__init__(free)
		self.symbol = symbol
		self.actuals = actuals
	def rank(self): return self.symbol.echelon
	def demote(self): return self.symbol.typ.rewrite(self.actuals)
	def rewrite(self, gamma:Mapping):
		if not self.free & gamma.keys(): return self
		new_mapping = {free:bound.rewrite(gamma) for free, bound in self.actuals.items()}
		return Apply(self.symbol, new_mapping)
	def instantiate(self, gamma: dict):
		fresh = {free:free.instantiate(gamma) for free in self.free}
		return self.rewrite(fresh)



class Arrow(Term):
	def __init__(self, arg: Term, res: Term):
		super().__init__(arg.free | res.free)
		self.arg, self.res = arg, res
	def __repr__(self): return "%s -> %s"%(self.arg, self.res)
	def rewrite(self, gamma:Mapping): return Arrow(self.arg.rewrite(gamma), self.res.rewrite(gamma))
	def instantiate(self, gamma:dict):
		arg, res = self.arg.instantiate(gamma), self.res.instantiate(gamma)
		if self.arg is arg and self.res is res: return self
		else: return Arrow(arg, res)


class Tagged(Term):
	# The proper destructor here is pattern-application.
	def __init__(self, genera:object, species:str, body:Term):
		super().__init__(body.free)
		self.genera = genera
		self.species = species
		self.body = body
	def __repr__(self): return "%s::%s %s"%(self.genera, self.species, self.body)
	def rewrite(self, gamma:Mapping): return Tagged(self.genera, self.species, self.body.rewrite(gamma))
	def instantiate(self, gamma: dict): return Tagged(self.genera, self.species, self.body.instantiate(gamma))


class Sum(Term):
	""" The proper destructor is scope-resolution. """
	def __init__(self, genera:object, alts:dict[str,Tagged]):
		super().__init__(frozenset().union(*[f.free for f in alts.values()]))
		self.genera = genera
		self.alts = alts
	def rewrite(self, gamma: Mapping):
		return Sum(self.genera, {
			key: value.rewrite(gamma)
			for key, value in self.alts.items()
		})
	def instantiate(self, gamma: dict):
		return Sum(self.genera, {
			key: value.instantiate(gamma)
			for key, value in self.alts.items()
		})

class Product(Term):
	# The proper "destructor" is an indexed-access operation.
	# That's not accessible idiomatically; it's an internal thing.
	def __init__(self, fields: Sequence[Term]):
		super().__init__(frozenset().union(*[f.free for f in fields]))
		self.fields = fields
	def __repr__(self): return "(%s)"%(",".join(map(str, self.fields)))
	def rewrite(self, gamma:Mapping): return Product(tuple(t.rewrite(gamma) for t in self.fields))
	def instantiate(self, gamma:dict):
		fields = tuple(t.instantiate(gamma) for t in self.fields)
		if all(a is b for a,b in zip(fields, self.fields)): return self
		else: return Product(fields)


class Record(Term):
	# The proper destructor is a field-access operation.
	def __init__(self, symbol:object, index, product:Product):
		super().__init__(product.free)
		self.symbol = symbol
		self.index = index
		self.product = product
	def __repr__(self): return "<record %s>"%self.symbol
	def rewrite(self, gamma:Mapping): return Record(self.symbol, self.index, self.product.rewrite(gamma))
	def instantiate(self, gamma:dict):
		product = self.product.instantiate(gamma)
		if product is self.product: return self
		else: return Record(self.symbol, self.index, product)


class UnitType(Term):
	""" In principle you could have different ones of these... For now, they're all equivalent. """
	def __repr__(self): return "(/)"
	def rewrite(self, gamma:Mapping): return self
	def instantiate(self, gamma: dict): return self

the_unit = UnitType(frozenset())


#########################

class Incompatible(TypeError):
	pass

def unify(peas:Term, carrots:Term) -> dict[TypeVariable:Term]:
	def proxy(term):
		while term in gamma: term = gamma[term]
		return term
	def enq(a,b): queue.append((a,b))
	def U(a, b):
		a, b = proxy(a), proxy(b)
		if a is b: return
		elif type(a) is TypeVariable: gamma[a] = b
		elif type(b) is TypeVariable: gamma[b] = a
		else:
			while a.rank != b.rank:
				if a.rank > b.rank:
					a = a.demote(gamma)
				else:
					b = b.demote(gamma)
			T = type(a)
			if T is not type(b):
				raise Incompatible(a,b)
			elif T is Apply:
				if a.ctor is b.ctor:
					assert len(a.actuals) == len(b.actuals)
					for x,y in zip(a.actuals, b.actuals):
						enq(x,y)
				else:
					raise Incompatible(a,b)
			elif T is PrimitiveType:
				# Nominal Equivalence
				if a is not b:
					raise Incompatible(a,b)
			elif T is Arrow:
				# Structural Equivalence
				enq(a.arg, b.arg)
				enq(a.res, b.res)
			elif T is Product:
				# Structural Equivalence
				if len(a.fields) != len(b.fields):
					raise Incompatible(a,b)
				for x,y in zip(a.fields,b.fields):
					enq(x,y)
			else:
				raise TypeError(T)
	
	gamma = {}
	queue = deque()
	enq(peas, carrots)
	while queue:
		U(*queue.popleft())
	return gamma
