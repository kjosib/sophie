"""
Main driver for Sophie langauge.

This will be done in phases:

1. to parse Sophie. This works on the happy path and a few error cases (not many) are also tested.
2. a simple-minded call-by-need evaluator. This also works, leaving out list comprehensions.
2a. Check that used words are defined somewhere. Maybe make some connections along the way.
3. a type checker. Not started yet.
4. strictness propagation, with call-site strictness where indicated.
5. interfacing to more outputs than a print-out of the computed value, such as turtle graphics
6. contemplating inputs
7. a deeper consideration for explicit concurrency
8. emitting native or VM code
9. an ecosystem
"""
from pathlib import Path
from typing import Optional

from boozetools.support.symtab import NameSpace, NoSuchSymbol, SymbolAlreadyExists
from boozetools.support.failureprone import Issue, Evidence, Severity
from boozetools.support.foundation import Visitor
from . import syntax

def resolve_words(module:syntax.Module, outside:NameSpace) -> list[Issue]:
	"""
	Let's say, at the end of this action, every name reference in the source text is
	linked to the corresponding definition-object. Said definition-object may not yet
	be fully populated / analyzed, but it will at least be the correct bag-of-holding
	for all future attributes corresponding to that symbol. At the end of this pass,
	you could forget the symbol-table dictionaries, except for the export list.
	
	This will not be able to handle field-access (or keyword-args, etc) in the first instance,
	because those depend on some measure of type resolution. And to keep things simple,
	I'm going to worry about that part in a separate pass.
	"""
	assert isinstance(module, syntax.Module)
	issues = []
	definer = WordDefiner(module, outside)
	if definer.redef:
		issues.append(_error_report(
			definer.redef,
			"Defining Words",
			"I see the same name defined earlier in the same scope:"
		))
	resolver = WordResolver(module)
	if resolver.undef:
		issues.append(_error_report(
			resolver.undef,
			"Finding Definitions",
			"I do not see an available definition for:",
		))
	return issues

def _error_report(guilty:list[slice], phase:str, description:str) -> Issue:
	evidence = {"": [Evidence(s, "") for s in guilty]}
	return Issue(phase, Severity.ERROR, description, evidence)

class WordDefiner(Visitor):
	"""
	Attaches NameSpace objects in key places and install definitions.
	Takes note of names with more than one definition in the same scope.
	"""
	def __init__(self, module:syntax.Module, outer:NameSpace):
		self.redef = []
		self.globals = module.namespace = outer.new_child(module)
		for td in module.types:
			assert isinstance(td, syntax.TypeDecl)
			self.visit(td)
		for fn in module.functions:
			self.visit(fn, self.globals)

	def _install(self, namespace:NameSpace, name:syntax.Token, item):
		assert isinstance(name, syntax.Token), name
		try: namespace[name.text] = item
		except SymbolAlreadyExists: self.redef.append(name.slice)
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		self._install(self.globals, td.name, td.body)
		if td.params is None:
			td.namespace = self.globals
		else:
			td.namespace = self.globals.new_child(td)
			for param_name in td.params:
				self._install(td.namespace, param_name, None)
		self.visit(td.body, td.name)
	
	def visit_UnionType(self, it:syntax.UnionType, name:syntax.Token):
		for summand in it.alternatives:
			if summand.body is not None:
				self._install(self.globals, summand.name, summand)
	
	def visit_ProductType(self, it:syntax.ProductType, name:syntax.Token):
		slots = NameSpace(place=self)
		for name, factor in it.factors:
			self._install(slots, name, None)
	
	def visit_ArrowType(self, it:syntax.ArrowType, name:syntax.Token):
		pass

	def visit_Token(self, it:syntax.Token, name:syntax.Token):
		pass

	def visit_TypeCall(self, it:syntax.TypeCall, name:syntax.Token):
		pass

	def visit_Function(self, fn:syntax.Function, env:NameSpace):
		self._install(env, fn.signature.name, fn)
		inner = fn.namespace = env.new_child(fn)
		for param in fn.signature.params or ():
			self._install(inner, param.name, param)
		fn.sub_fns = {}  # for simple evaluator
		for sub_fn in fn.where:
			sub_name = sub_fn.signature.name
			self.visit(sub_fn, inner)
			fn.sub_fns[sub_name.text] = sub_fn
		del fn.where  # Don't need this anymore.
		
class WordResolver(Visitor):
	"""
	Walk the tree looking for undefined words in each static scope.
	Report on every such occurrence.
	"""
	def __init__(self, module:syntax.Module):
		self.undef = []
		for td in module.types:
			assert isinstance(td, syntax.TypeDecl)
			self.visit(td.body, td.namespace)
		for fn in module.functions:
			self.visit(fn, module.namespace)
		for expr in module.main:
			self.visit(expr, module.namespace)
		
	def visit_UnionType(self, it:syntax.UnionType, env:NameSpace):
		for alt in it.alternatives:
			self.visit(alt, env)
	
	def visit_ProductType(self, it:syntax.ProductType, env:NameSpace):
		for name, factor in it.factors:
			self.visit(factor, env)
	
	def visit_TypeSummand(self, it:syntax.TypeSummand, env:NameSpace):
		if it.body is not None:
			self.visit(it.body, env)
	
	def visit_Token(self, token:syntax.Token, env:NameSpace):
		try:
			env.find(token.text)
		except NoSuchSymbol:
			self.undef.append(token.slice)
	
	def visit_TypeCall(self, it:syntax.TypeCall, env:NameSpace):
		self.visit(it.name, env)
		for p in it.params:
			self.visit(p, env)

	def visit_Function(self, fn:syntax.Function, env:NameSpace):
		inner = fn.namespace
		for key, item in inner.local.items():
			self.visit(item, inner)
		self.visit(fn.expr, inner)
	
	def visit_Parameter(self, param:syntax.Parameter, env:NameSpace):
		if param.type_expr is not None:
			self.visit(param.type_expr, env)
	
	def visit_Literal(self, it:syntax.Literal, env:NameSpace):
		pass
	
	def visit_ArrowType(self, it:syntax.ArrowType, env:NameSpace):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)

	def visit_ShortCutExp(self, it:syntax.ShortCutExp, env:NameSpace):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)

	def visit_BinExp(self, it:syntax.BinExp, env:NameSpace):
		self.visit(it.lhs, env)
		self.visit(it.rhs, env)

	def visit_UnaryExp(self, expr:syntax.UnaryExp, env:NameSpace):
		self.visit(expr.arg, env)
	
	def visit_Lookup(self, expr:syntax.Lookup, env:NameSpace):
		self.visit(expr.name, env)
	
	def visit_FieldReference(self, expr:syntax.FieldReference, env:NameSpace):
		self.visit(expr.lhs, env)
		# Save expr.field_name for once types are more of a thing.
	
	def visit_Call(self, expr:syntax.Call, env:NameSpace):
		self.visit(expr.fn_exp, env)
		for a in expr.args:
			self.visit(a, env)
	
	def visit_Cond(self, expr:syntax.Cond, env:NameSpace):
		self.visit(expr.if_part, env)
		self.visit(expr.then_part, env)
		self.visit(expr.else_part, env)

	def visit_ExplicitList(self, expr:syntax.ExplicitList, env:NameSpace):
		for e in expr.elts:
			self.visit(e, env)
