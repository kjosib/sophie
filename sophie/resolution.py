"""
All the definition resolution stuff goes here.
By the time this pass is finished, every name points to its symbol table entry,
from which we can find the kind, type, and definition.
"""

from boozetools.support.symtab import NameSpace, NoSuchSymbol, SymbolAlreadyExists
from boozetools.support.failureprone import Issue, Evidence, Severity
from boozetools.support.foundation import Visitor
from . import syntax, diagnostics
from .ontology import SymbolTableEntry, Cell, KIND_VALUE, KIND_TYPE

def resolve_words(module:syntax.Module, outside:NameSpace[SymbolTableEntry]) -> list[Issue]:
	"""
	At the end of this action, every name-reference in the source text is visible where it's used.
	That is, a corresponding definition-object is in scope. It may not make sense,
	or be the right kind of name, but at least it's not an obvious misspelling.
	
	This will not be able to handle field-access (or keyword-args, etc) in the first instance,
	because those depend on some measure of type resolution. And to keep things simple,
	I'm going to worry about that part in a separate pass.
	"""
	assert isinstance(module, syntax.Module)
	report = diagnostics.Report()
	definer = WordDefiner(module, outside)
	if definer.redef:
		report.error(
			definer.redef,
			"Defining Words",
			"I see the same name defined earlier in the same scope:"
		)
	resolver = WordResolver(module)
	if resolver.undef:
		report.error(
			resolver.undef,
			"Finding Definitions",
			"I do not see an available definition for:",
		)
	for guilty in resolver.duptags:
		report.error(
			guilty,
			"Checking type-match expressions",
			"The same type-case appears more than once in a single type-matching expression."
		)
	return report.issues

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

	def _install(self, namespace:NameSpace, name:syntax.Key, dfn, kind:str):
		cell = Cell(name)
		name.entry = SymbolTableEntry(kind, dfn, cell)
		try: namespace[name.text] = name.entry
		except SymbolAlreadyExists: self.redef.append(name.slice)
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		self._install(self.globals, td.name, td.body, KIND_TYPE)
		if not td.parameters:
			td.namespace = self.globals
		else:
			td.namespace = self.globals.new_child(td)
			for param_name in td.parameters:
				self._install(td.namespace, param_name, None, KIND_TYPE)
		self.visit(td.body)
	
	def visit_VariantType(self, it:syntax.VariantType):
		for summand in it.alternatives:
			self._install(self.globals, summand.tag, summand, KIND_TYPE)
	
	def visit_RecordType(self, it:syntax.RecordType):
		# This only checks for overlapping field names.
		seen = NameSpace(place=it)
		for name, factor in it.fields:
			self._install(seen, name, factor, KIND_TYPE)
	
	def visit_ArrowType(self, it:syntax.ArrowType):
		pass

	def visit_Name(self, it:syntax.Name):
		pass

	def visit_TypeCall(self, it:syntax.TypeCall):
		pass

	def visit_Function(self, fn:syntax.Function, env:NameSpace):
		self._install(env, fn.name, fn, KIND_VALUE)
		inner = fn.namespace = env.new_child(fn)
		self.visit(fn.signature, inner)
		fn.sub_fns = {}  # for simple evaluator
		for sub_fn in fn.where:
			sub_name = sub_fn.name
			self.visit(sub_fn, inner)
			fn.sub_fns[sub_name.text] = sub_fn
		del fn.where  # Don't need this anymore.
	
	def visit_FunctionSignature(self, sig:syntax.FunctionSignature, inner:NameSpace):
		for param in sig.params:
			self._install(inner, param.name, param, KIND_VALUE)
	
	def visit_AbsentSignature(self, sig:syntax.AbsentSignature, inner:NameSpace):
		pass

class WordResolver(Visitor):
	"""
	Walk the tree looking for undefined words in each static scope.
	Report on every such occurrence.
	"""
	def __init__(self, module:syntax.Module):
		self.undef = []
		self.duptags = []
		self.globals = module.namespace
		for td in module.types:
			assert isinstance(td, syntax.TypeDecl)
			self.visit(td.body, td.namespace)
		for fn in module.functions:
			self.visit(fn)
		for expr in module.main:
			self.visit(expr, module.namespace)
		
	def visit_VariantType(self, it:syntax.VariantType, env:NameSpace):
		for alt in it.alternatives:
			self.visit(alt, env)
	
	def visit_RecordType(self, it:syntax.RecordType, env:NameSpace):
		for name, factor in it.fields:
			self.visit(factor, env)
			
	def visit_TypeSummand(self, it:syntax.TypeSummand, env:NameSpace):
		if it.body is not None:
			self.visit(it.body, env)
	
	def visit_Name(self, name:syntax.Name, env:NameSpace):
		try:
			name.entry = env[name.text]
		except NoSuchSymbol:
			self.undef.append(name.slice)
	
	def visit_TypeCall(self, it:syntax.TypeCall, env:NameSpace):
		self.visit(it.name, env)
		for p in it.arguments:
			self.visit(p, env)

	def visit_Function(self, fn:syntax.Function):
		self.visit(fn.signature)
		inner = fn.namespace
		for key, item in inner.local.items():
			self.visit(item.dfn)
		self.visit(fn.expr, inner)
	
	def visit_FunctionSignature(self, sig:syntax.FunctionSignature):
		for p in sig.params:
			self.visit(p)
		if sig.return_type is not None:
			self.visit(sig.return_type, self.globals)
	
	def visit_AbsentSignature(self, sig:syntax.AbsentSignature):
		pass
	
	def visit_Parameter(self, param:syntax.Parameter):
		if param.type_expr is not None:
			self.visit(param.type_expr, self.globals)
	
	def visit_Literal(self, it:syntax.Literal, env:NameSpace):
		pass
	
	def visit_ArrowType(self, it:syntax.ArrowType, env:NameSpace):
		for a in it.lhs:
			self.visit(a, env)
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
	
	def visit_MatchExpr(self, expr:syntax.MatchExpr, env:NameSpace):
		# Maybe ought to be in a separate pass,
		# but it seems sensible to check for duplicate tags here.
		self.visit(expr.name, env)
		expr.dispatch = {}
		seen = {}
		for item in expr.alternatives:
			assert isinstance(item, syntax.Alternative)
			tag = item.pattern.tag()
			if tag in seen:
				self.duptags.append((seen[tag], item.pattern.slice))
			else:
				seen[tag] = item.pattern.slice
				expr.dispatch[tag] = item.expr
			self.visit(item.pattern, env)
			self.visit(item.expr, env)
		if expr.otherwise is not None:
			self.visit(expr.otherwise, env)
	
	def visit_NilToken(self, nil:syntax.NilToken, env:NameSpace):
		pass
