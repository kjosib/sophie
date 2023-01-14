from collections import deque
from typing import Sequence

from boozetools.support.foundation import Visitor, strongly_connected_components_hashable
from . import primitive, syntax, ontology
from .algebra import Arrow, Product, SophieType, TypeVariable, Nominal, PullRabbit, Render

OPS = {glyph:typ for glyph, (op, typ) in primitive.ops.items()}

def infer_types(module:syntax.Module, report, verbose=False):
	on_error = report.on_error("Inferring Types")
	call_graph = CallSitePreparation(module).call_graph
	deduce = DeductionEngine(module, verbose)
	try:
		for component in strongly_connected_components_hashable(call_graph):
			deduce.solve(component)
		for expr in module.main:
			deduce.visit(expr)
	except UnificationFailed as e:
		a, b, stem = e.prior, e.term, e.at
		delta = Render()
		on_error([stem], e.gripe % (a.visit(delta), b.visit(delta)))
	except NoSuchField as e:
		message = "Expression of type %s %s."%(e.inner_typ.visit(Render()), e.gripe)
		on_error([e.at], message)
	except TooComplex:
		on_error(component, "This set of functions was too complex for me to solve the types of. Maybe add some annotations?")

class CallSitePreparation(Visitor):
	"""
	Put result-type variables at all the call sites,
	and capture the call graph in the process.
	"""
	def __init__(self, module:syntax.Module):
		self.call_graph = {}
		self._local_functions = frozenset(module.all_functions)
		for fn in module.all_functions:
			self.call_graph[fn] = self._edges = set()
			self.visit(fn.expr)
		self._edges = set()
		for expr in module.main:
			self.caller = None
			self.visit(expr)
	
	def visit_Literal(self, expr: syntax.Literal): pass
	
	def visit_Lookup(self, expr: syntax.Lookup):
		dfn = expr.ref.dfn
		if dfn in self._local_functions:
			self._edges.add(dfn)
	
	def visit_MatchExpr(self, mx: syntax.MatchExpr):
		for alt in mx.alternatives:
			self.visit(alt.sub_expr)
		if mx.otherwise is not None:
			self.visit(mx.otherwise)
	
	def visit_Cond(self, cond: syntax.Cond):
		self.visit(cond.then_part)
		self.visit(cond.if_part)
		self.visit(cond.else_part)
	
	def visit_ShortCutExp(self, sx: syntax.ShortCutExp):
		self.visit(sx.lhs)
		self.visit(sx.rhs)
	
	def visit_FieldReference(self, fr: syntax.FieldReference):
		self.visit(fr.lhs)
	
	def visit_Call(self, expr: syntax.Call):
		expr.res_typ = TypeVariable()
		self.visit(expr.fn_exp)
		for a in expr.args:
			self.visit(a)
	
	def visit_BinExp(self, expr: syntax.BinExp):
		expr.res_typ = TypeVariable()
		self.visit(expr.lhs)
		self.visit(expr.rhs)
	
	def visit_UnaryExp(self, expr: syntax.UnaryExp):
		expr.res_typ = TypeVariable()
		self.visit(expr.arg)
		
	def visit_ExplicitList(self, expr: syntax.ExplicitList):
		for a in expr.elts:
			self.visit(a)

class DeductionEngine(Visitor):
	"""
	By this point, all type-definition bodies and type-expressions are well-founded.
	"""
	def __init__(self, module:syntax.Module, verbose=False):
		self._verbose = verbose
		self._gamma = {}
		self._bunny = PullRabbit(self._gamma)
	
	def solve(self, component):
		for _ in range(10):
			self._bunny.reset()
			for fn in component:
				self.visit_Function(fn)
			if not self._bunny.did_narrow:
				if self._verbose:
					for fn in component:
						print(_+1, ">>", fn.nom.text, ":", fn.typ.visit(Render()))
				return
		raise TooComplex()
	
	def visit_Function(self, fn: syntax.Function):
		res = self.visit(fn.expr)
		if fn.params:
			arg = Product(tuple(p.typ for p in fn.params))
			unify([Arrow(arg, res), fn.typ], self._gamma, fn.nom)
			fn.typ = fn.typ.visit(self._bunny)
			for p in fn.params:
				p.typ = p.typ.visit(self._bunny)
		else:
			unify([res, fn.typ], self._gamma, fn.nom)
			fn.typ = res.visit(self._bunny)
		pass
	
	def _call_site(self, expr:ontology.Expr, fn_type, arg_exprs):
		arg = Product(tuple(self.visit(a) for a in arg_exprs))
		unify([Arrow(arg, expr.res_typ), fn_type], self._gamma, expr)
		expr.res_typ = expr.res_typ.visit(self._bunny)
		return expr.res_typ

	def visit_Call(self, expr: syntax.Call):
		fn_type = self.visit(expr.fn_exp)
		return self._call_site(expr, fn_type, expr.args)

	def visit_BinExp(self, expr: syntax.BinExp):
		return self._call_site(expr, OPS[expr.glyph], (expr.lhs, expr.rhs))

	def visit_UnaryExp(self, expr: syntax.UnaryExp):
		return self._call_site(expr, OPS[expr.glyph], (expr.arg, ))

	def visit_Literal(self, expr: syntax.Literal):
		if isinstance(expr.value, str):
			return primitive.literal_string
		if isinstance(expr.value, bool):
			return primitive.literal_flag
		if isinstance(expr.value, (int, float)):
			return primitive.literal_number
		raise TypeError(expr.value)

	def visit_Lookup(self, expr: syntax.Lookup):
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
	
	def visit_ExplicitList(self, expr: syntax.ExplicitList):
		inside = [self.visit(x) for x in expr.elts]
		unify(inside, self._gamma, expr)
		return Nominal(primitive.LIST.dfn, [inside[0]])
	
	def visit_MatchExpr(self, mx: syntax.MatchExpr):
		unify([mx.input_type, self._value_type(mx.subject_dfn)], self._gamma, mx.subject)
		parts = []
		for alt in mx.alternatives:
			parts.append(self.visit(alt.sub_expr))
		if mx.otherwise: parts.append(self.visit(mx.otherwise))
		unify(parts, self._gamma, mx)
		return parts[0]
	
	def visit_ShortCutExp(self, sx: syntax.ShortCutExp):
		unify([
			primitive.literal_flag,
			self.visit(sx.lhs),
			self.visit(sx.rhs),
		], self._gamma, sx)
		return primitive.literal_flag
	
	def visit_FieldReference(self, fr:syntax.FieldReference):
		result = TypeVariable()
		inner_typ = self.visit(fr.lhs)
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
						raise NoSuchField(fr, inner_typ, "has no field %s. Possibilities are %s"%(key, list[nsl]))
					fn_type = Arrow(dfn.typ, field.typ).fresh({})
					goal = Arrow(inner_typ, result)
					unify([fn_type, goal], self._gamma, fr)
					return result
				else:
					raise NoSuchField(fr, inner_typ, "has no fields.")
		else:
			print("Guru Meditation:")
			print(inner_typ, type(inner_typ))
			exit(9)
		
	def visit_Cond(self, cond:syntax.Cond):
		branches = [self.visit(x) for x in (cond.then_part, cond.else_part)]
		unify([primitive.literal_flag, self.visit(cond.if_part)], self._gamma, cond)
		unify(branches, self._gamma, cond)
		return branches[0]
		
class UnificationFailed(Exception):
	gripe:str
	def __init__(self, prior, term, at):
		self.prior, self.term, self.at = prior, term, at
class Incompatible(UnificationFailed):
	gripe = "This tries to be both %r and also %r, which cannot happen."
class RecursiveTypeError(UnificationFailed):
	gripe = "This tries to equate %s with %s which contains it, but a type cannot be part of itself."

class NoSuchField(Exception):
	def __init__(self, at:syntax.FieldReference, inner_typ, gripe):
		self.at, self.inner_typ, self.gripe = at, inner_typ, gripe
		
class TooComplex(Exception):
	pass

def _proxy(a: SophieType, gamma: dict):
	if a in gamma:
		b = _proxy(gamma[a], gamma)
		gamma[a] = b
		return b
	else:
		return a

def unify(terms: Sequence[SophieType], gamma: dict, stem):
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
