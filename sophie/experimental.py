from collections import deque
from typing import Sequence

from boozetools.support.foundation import Visitor
from . import primitive, syntax, ontology
from .algebra import Arrow, Product, Term, TypeVariable, Nominal, PullRabbit

OPS = {glyph:typ for glyph, (op, typ) in primitive.ops.items()}

class Experiment(Visitor):
	"""
	By this point, all type-definition bodies and type-expressions are well-founded.
	"""
	def __init__(self, module, on_error:callable, verbose=False):
		assert callable(on_error)
		self.on_error = on_error
		gamma = {}
		try:
			for _ in range(3):
				for fn in module.all_functions:
					self.visit_Function(fn, gamma)
					if verbose:
						print(">>", fn.nom.text, fn.typ.render(gamma, {}))
				if verbose:
					print("============")
			for expr in module.main:
				self.visit(expr, {})
		except UnificationFailed as e:
			a,b, stem = e.args
			delta = {}
			self.on_error([stem], e.gripe%(a.render(gamma, delta), b.render(gamma, delta)))

	def visit_Function(self, fn: syntax.Function, gamma):
		res = self.visit(fn.expr, gamma)
		rabbit = PullRabbit(gamma)
		if fn.params:
			arg = Product(tuple(p.typ for p in fn.params))
			unify([Arrow(arg, res), fn.typ], gamma, fn.nom)
			fn.typ = fn.typ.visit(rabbit)
			assert isinstance(fn.typ, Arrow)
			assert isinstance(fn.typ.arg, Product)
			for p,t in zip(fn.params, fn.typ.arg.fields):
				p.typ = t
		else:
			fn.typ = res.visit(rabbit)
		pass
	
	def _call_site(self, expr, fn_type, arg_exprs, gamma):
		arg = Product(tuple(self.visit(a, gamma) for a in arg_exprs))
		res = TypeVariable()
		unify([Arrow(arg, res), fn_type], gamma, expr)
		return res.visit(PullRabbit(gamma))

	def visit_Call(self, expr: syntax.Call, gamma):
		fn_type = self.visit(expr.fn_exp, gamma)
		return self._call_site(expr, fn_type, expr.args, gamma)

	def visit_BinExp(self, expr: syntax.BinExp, gamma):
		return self._call_site(expr, OPS[expr.glyph], (expr.lhs, expr.rhs), gamma)

	def visit_UnaryExp(self, expr: syntax.UnaryExp, gamma):
		return self._call_site(expr, OPS[expr.glyph], (expr.arg, ), gamma)

	def visit_Literal(self, expr: syntax.Literal, gamma):
		if isinstance(expr.value, str):
			return primitive.literal_string
		if isinstance(expr.value, bool):
			return primitive.literal_flag
		if isinstance(expr.value, (int, float)):
			return primitive.literal_number
		raise TypeError(expr.value)

	def visit_Lookup(self, expr: syntax.Lookup, gamma):
		return self._value_type(expr.ref.dfn)
	
	def _value_type(self, dfn:ontology.Symbol):
		"""
		This function is where let-polymorphism comes from.
		Based on the type of the symbol,
		compose a type which represents the thing of that
		name as used in that place.
		"""
		if isinstance(dfn, syntax.Function):
			return dfn.typ.fresh({})
		if isinstance(dfn, (
				syntax.FormalParameter,
				ontology.MatchProxy,
				primitive.NativeFunction,
				primitive.NativeValue,
		)):
			return dfn.typ
		if isinstance(dfn, syntax.SubTypeSpec):
			variant = dfn.variant
			if isinstance(dfn.body, syntax.RecordSpec):
				return Arrow(dfn.body.product_type, variant.typ).fresh({})
			elif dfn.body is None:
				return variant.typ.fresh({})
			else:
				return Arrow(dfn.typ, variant.typ).fresh({})
		if isinstance(dfn, syntax.TypeDecl):
			if isinstance(dfn.body, syntax.RecordSpec):
				return Arrow(dfn.body.product_type, dfn.typ).fresh({})
			elif dfn.body is None:
				return dfn.typ.fresh({})
		raise RuntimeError(dfn, type(dfn))
	
	def visit_ExplicitList(self, expr: syntax.ExplicitList, gamma):
		inside = [self.visit(x, gamma) for x in expr.elts]
		unify(inside, gamma, expr)
		return Nominal(primitive.LIST.dfn, [inside[0]])
	
	def visit_MatchExpr(self, mx: syntax.MatchExpr, gamma):
		unify([mx.input_type, self._value_type(mx.subject_dfn)], gamma, mx.subject)
		parts = []
		for alt in mx.alternatives:
			# for sub_fn in alt.where:
			# 	self.visit_Function(sub_fn, gamma)
			parts.append(self.visit(alt.sub_expr, gamma))
		if mx.otherwise: parts.append(self.visit(mx.otherwise, gamma))
		unify(parts, gamma, mx)
		return parts[0]
	
	def visit_ShortCutExp(self, sx: syntax.ShortCutExp, gamma):
		unify([
			primitive.literal_flag,
			self.visit(sx.lhs, gamma),
			self.visit(sx.rhs, gamma),
		], gamma, sx)
		return primitive.literal_flag
	
	def visit_FieldReference(self, fr:syntax.FieldReference, gamma):
		result = TypeVariable()
		inner_typ = self.visit(fr.lhs, gamma)
		if isinstance(inner_typ, TypeVariable):
			return result
		elif isinstance(inner_typ, Nominal):
			dfn : ontology.Symbol = inner_typ.dfn
			
			if isinstance(dfn, (syntax.TypeDecl, syntax.SubTypeSpec)):
				if isinstance(dfn.body, syntax.RecordSpec):
					key = fr.field_name.text
					nsl = dfn.body.namespace.local
					try: field = nsl[key]
					except KeyError:
						self.on_error([fr], "Expression of %s type has no field %s. Possibilities are %s"%(inner_typ, key, list[nsl]))
						return result
					fn_type = Arrow(dfn.typ, field.typ).fresh({})
					goal = Arrow(inner_typ, result)
					unify([fn_type, goal], gamma, fr)
					return result
				else:
					self.on_error([fr], "Expression of %s type has no fields."%inner_typ)
					return result
		else:
			print("Guru Meditation:")
			print(inner_typ, type(inner_typ))
			exit(9)
		
	def visit_Cond(self, cond:syntax.Cond, gamma):
		branches = [self.visit(x, gamma) for x in (cond.then_part, cond.else_part)]
		unify([primitive.literal_flag, self.visit(cond.if_part, gamma)], gamma, cond.if_part)
		unify(branches, gamma, cond)
		return branches[0]
		
class UnificationFailed(Exception):
	gripe:str
	def __init__(self, prior, term, at):
		self.prior, self.term, self.at = prior, term, at
class Incompatible(UnificationFailed):
	gripe = "This needs a value to be both %s and also %s, which cannot happen."
class RecursiveTypeError(UnificationFailed):
	gripe = "This tries to equate %s with %s which contains it, but a type cannot be part of itself."

def _proxy(a: Term, gamma: dict):
	if a in gamma:
		b = _proxy(gamma[a], gamma)
		gamma[a] = b
		return b
	else:
		return a

def unify(terms: Sequence[Term], gamma: dict, stem):
	def enq(a, b):
		queue.append((a, b))
	def U(a, b):
		a, b = _proxy(a, gamma), _proxy(b, gamma)
		# Lemma 1: neither A nor B are in gamma.
		# Lemma 2: A and B each stand for themselves.
		if a is b:
			return
		elif type(a) is TypeVariable:
			# if A occurs in B, then reject. It would be ill-founded.
			if b.mentions(a): raise RecursiveTypeError(a, b, stem)
			gamma[a] = b  # A is made to stand for B
		elif type(b) is TypeVariable:
			# if B occurs in A, then reject. It would be ill-founded.
			if a.mentions(b): raise RecursiveTypeError(b, a, stem)
			gamma[b] = a  # B is made to stand for A
		elif a.phylum() == b.phylum():
			a.unify_with(b, enq)
		else:
			raise Incompatible(a, b, stem)
	
	queue = deque()
	t0 = terms[0]
	for t1 in terms[1:]:
		enq(t0, t1)
		while queue:
			U(*queue.popleft())
	return
