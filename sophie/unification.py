"""
The unification approach to type-inference
"""
from typing import NamedTuple
from boozetools.support.failureprone import Issue
from boozetools.support.foundation import Visitor, strongly_connected_components_hashable
from . import syntax, ontology, diagnostics
from .ontology import Cell, SophieType
from .primitive import literal_flag, literal_number, literal_string

PHASE_ASSIGN = "reading type declarations"
PHASE_PROBLEM = "preparing to infer types"
THE_LIST_TYPE:ontology.GenericType # The preamble writer fills this in.

def infer_types(module:syntax.Module) -> list[Issue]:
	report = diagnostics.Report()
	TypeAssigner(module, report)
	del module.types  # Don't need it anymore.
	solver = ConstraintSolver(report)
	if not report.issues:
		InferenceProblem(module, solver, report)
	# if not report.issues:
	# 	solver.solve()
	return report.issues


class ConstraintSolver:
	"""
	When this object is finished,
	either all the symbols are well-typed
	or else there are reports about conflicts.

	At the moment, these reports may be cryptic.
	That will change.
	"""
	
	def __init__(self, report: diagnostics.Report):
		self._report = report
		self.constraints = []
	
	def solve(self):
		while self.constraints:
			self.constraints.pop().visit(self)
	
	def reads(self, reader:Cell, message:Cell):
		self.constraints.append(Read(reader, message))

	def equate(self, senior, junior):
		self.constraints.append(Equation(senior, junior))
	
	def call_site(self, expr, fn_type: Cell, arg_types: tuple[Cell, ...]):
		arg = Cell(expr).assign(ontology.Product(arg_types))
		typ = Cell(expr)
		arrow = ontology.Arrow(arg, typ)
		self.constraints.append(Conformance(arrow, fn_type))
		return typ
	
	def must_specialize(self, variant_typ: Cell, template: Cell, case: Cell):
		self.constraints.append(Specialization(variant_typ, template, case))
	
	def field_access(self, inner: Cell, name: syntax.Name, outer: Cell):
		self.constraints.append(FieldAccess(inner, name, outer))


class Conformance(NamedTuple):
	target: ontology.Arrow
	template: Cell
	
	def visit(self, solver:ConstraintSolver):
		pass

class Equation(NamedTuple):
	senior: Cell
	junior: Cell
	def visit(self, solver:ConstraintSolver):
		s, j = self.senior.proxy(), self.junior.proxy()
		if s is j:
			return
		elif j.value is None or s.value is j.value:
			j.become(s)
		elif s.value is None:
			s.become(j)
		else:
			intersection = s.value.intersect(j.value)
			if intersection is None:
				raise NotImplementedError()
			else:
				s.value = intersection
				j.become(s)

class Read(NamedTuple):
	reader: Cell
	message: Cell

class Specialization(NamedTuple):
	variant_typ: Cell
	template: Cell
	case: Cell
	def visit(self, solver:ConstraintSolver):
		pass

class FieldAccess(NamedTuple):
	inner: Cell
	field: syntax.Name
	outer: Cell
	def visit(self, solver:ConstraintSolver):
		pass

########################################################

class Bind(NamedTuple):
	template: Cell
	args: list[Cell]
	def dependencies(self): return [self.template, *self.args]
	def evaluate(self, cell:Cell, on_error):
		form = self.template.value
		if form is None:
			assert cell is self.template
			on_error([cell], "This tells me nothing.")
			form = ontology.ErrorType()
		elif form.arity() != len(self.args):
			pattern = "%d type-arguments were given; %d are needed."
			on_error([cell], pattern % (len(self.args), form.arity()))
			form = ontology.ErrorType()
		if self.args and isinstance(form, ontology.GenericType):
			cell.assign(ontology.ConcreteType(form, self.args))
		else:
			cell.assign(form)

class TypeAssigner(Visitor):
	"""
	At the end of this pass:
		All named derived types are properly defined with reference to the ontology.
		All aliases are properly expanded.
		All function-signature type annotations have been connected.
	Or else,
		Circular aliasing will be found out and reported.
	"""
	def __init__(self, module:syntax.Module, report:diagnostics.Report):
		def on_error(cells, message) -> None:
			report.error([c.blame() for c in cells], PHASE_ASSIGN, message)
		self.non_types = []
		self.aliases : dict[Cell:Bind] = {}
		for td in module.types:
			self.visit(td)
		for fn in module.functions:
			self.visit(fn)
		if self.non_types:
			report.error(self.non_types, PHASE_ASSIGN, "Need a type-name here; found a value-name instead.")
			return
		for scc in strongly_connected_components_hashable({
			cell: bind.dependencies()
			for cell, bind in self.aliases.items()
		}):
			if len(scc) == 1:
				cell = scc[0]
				self.aliases[cell].evaluate(cell, on_error)
			else:
				on_error(scc, "This is a circular definition.")
				
	
	def visit_TypeDecl(self, td:syntax.TypeDecl):
		params = []
		cell = td.name.entry.typ
		for name in td.parameters:
			params.append(name.entry.typ.assign(ontology.ExplicitParameter(name.text)))
		if params:
			result = ontology.GenericType(params, Cell(td.name))
			self.visit(td.body, td.name.text, result.body)
			cell.assign(result)
		else:
			self.visit(td.body, td.name.text, cell)

	def visit_VariantType(self, expr:syntax.VariantType, name, host:Cell):
		assert isinstance(name, str)
		variant = ontology.Variant(name)
		host.assign(variant)
		for summand in expr.alternatives:
			assert isinstance(summand, syntax.TypeSummand)
			if isinstance(summand.tag, syntax.Name):
				name = summand.tag.text
				case = ontology.TypeCase(name)
				variant.cases[name] = case
				summand.tag.entry.typ.assign(case)
			elif isinstance(summand.tag, syntax.NilToken):
				variant.cases["NIL"] = ontology.NilCase(variant)
			else:
				raise ValueError(summand.tag)
			pass

	def visit_RecordType(self, expr:syntax.RecordType, name, host:Cell):
		record = ontology.Record(name)
		host.assign(record)
		for name, type_expr in expr.fields:
			field = name.entry.typ
			record.fields[name.text] = field
			self.visit(type_expr, name.text, field)
		return record

	def visit_TypeCall(self, expr:syntax.TypeCall, name, host:Cell):
		entry = expr.name.entry
		if entry.kind == ontology.KIND_TYPE:
			args = []
			for actual_parameter in expr.arguments:
				param_cell = Cell(actual_parameter)
				self.visit(actual_parameter, name, param_cell)
				args.append(param_cell)
			self.aliases[host] = Bind(entry.typ, args)
		else:
			assert entry.kind == ontology.KIND_VALUE
			self.non_types.append(expr.name.slice)
	
	def visit_ArrowType(self, expr:syntax.ArrowType, name, host:Cell):
		args, rtn = [], Cell(host.stem)
		for a in expr.lhs:
			cell = Cell(host.stem)
			self.visit(a, name, cell)
			args.append(cell)
		argument = Cell(host.stem).assign(ontology.Product(args))
		arrow = ontology.Arrow(argument, rtn)
		host.assign(arrow)
	
	def visit_Function(self, fn: syntax.Function):
		self.visit(fn.signature, fn.name.entry.typ)
		for sub_fn in fn.sub_fns.values():
			self.visit(sub_fn)

	def visit_FunctionSignature(self, sig: syntax.FunctionSignature, typ: Cell):
		args = tuple(self.visit(a) for a in sig.params)
		# The type of the symbol is that of a function.
		arg_cell = Cell(typ.stem).assign(ontology.Product(args))
		sig.expr_type = Cell(typ.stem)
		if sig.return_type:
			self.visit(sig.return_type, "-return type-", sig.expr_type)
		typ.assign(ontology.Arrow(arg_cell, sig.expr_type))
		
	def visit_AbsentSignature(self, sig: syntax.AbsentSignature, typ: Cell):
		# The symbol's type is that of the given expression
		sig.expr_type = typ
		
	def visit_Parameter(self, param:syntax.Parameter):
		typ = param.name.entry.typ
		if param.type_expr is not None:
			self.visit(param.type_expr, param.name.text, typ)
		return typ


class InferenceProblem(Visitor):
	"""
	At the end of this pass,
	1. A constraint solver object has all the relations between types of expressions.
	2. The names associated with function definitions are given an arrow archetype.
	3. The names associated with constant definitions reflect the same.
	
	The pattern here is that visiting an expression yields a cell for that expression's type.
	Term definitions (i.e. functions and constants) will get defined in this process.
	"""
	
	def __init__(self, module: syntax.Module, solver:ConstraintSolver, report: diagnostics.Report):
		self._solver = solver
		self._report = report
		for fn in module.functions:
			self.visit(fn)
		for expr in module.main:
			self.visit(expr, {})
	
	def visit_Function(self, fn: syntax.Function):
		self._solver.equate(fn.signature.expr_type, self.visit(fn.expr, {}))
		for sub_fn in fn.sub_fns.values():
			self.visit(sub_fn)
	
	def visit_BinExp(self, expr:syntax.BinExp, hypo:dict[Cell:Cell]):
		lhs = self.visit(expr.lhs, hypo)
		rhs = self.visit(expr.rhs, hypo)
		return self._solver.call_site(expr, expr.op_typ, (lhs, rhs))
	
	# Behold: not-quite-coincidental duplication. Sort of.
	visit_ShortCutExp = visit_BinExp
	
	def visit_UnaryExp(self, expr:syntax.UnaryExp, hypo:dict[Cell:Cell]):
		arg = self.visit(expr.arg, hypo)
		return self._solver.call_site(expr, expr.op_typ, (arg,))

	def visit_Call(self, expr:syntax.Call, hypo:dict[Cell:Cell]):
		fn_type = self.visit(expr.fn_exp, hypo)
		arg_types = tuple(self.visit(a, hypo) for a in expr.args)
		return self._solver.call_site(expr, fn_type, arg_types)
	
	def visit_Cond(self, expr: syntax.Cond, hypo: dict[Cell:Cell]):
		if_typ = self.visit(expr.if_part, hypo)
		then_typ = self.visit(expr.then_part, hypo)
		else_type = self.visit(expr.else_part, hypo)
		expr_typ = Cell(expr)
		self._solver.equate(literal_flag, if_typ)
		self._solver.reads(expr_typ, then_typ)
		self._solver.reads(expr_typ, else_type)
		return expr_typ
	
	def visit_Literal(self, expr:syntax.Literal, hypo:dict[Cell:Cell]):
		if isinstance(expr.value, str):
			return literal_string
		if isinstance(expr.value, bool):
			return literal_flag
		if isinstance(expr.value, (int, float)):
			return literal_number
		if expr.value is None:
			return Cell(expr).assign(ontology.just_nil)
		raise TypeError(expr.value)
	
	def visit_Lookup(self, expr:syntax.Lookup, hypo:dict[Cell:Cell]):
		typ = expr.name.entry.typ
		return hypo.get(typ, typ)

	def visit_MatchExpr(self, expr:syntax.MatchExpr, hypo:dict[Cell:Cell]):
		typ = Cell(expr)
		variant_typ = expr.name.entry.typ
		if variant_typ in hypo:
			guilty = [expr.name.slice, hypo[variant_typ].stem.slice]
			self._report.error(guilty, PHASE_PROBLEM, "This type is already constrained.")
		else:
			for alt in expr.alternatives:
				self._solver.reads(typ, self.visit(alt, variant_typ, hypo))
		return typ
	
	def visit_Alternative(self, alt:syntax.Alternative, variant_typ:Cell, hypo:dict[Cell:Cell]):
		case = Cell(alt.pattern)
		if isinstance(alt.pattern, syntax.Name):
			template = alt.pattern.entry.typ
			if not isinstance(template.value, ontology.TypeCase):
				self._report.error([alt.pattern.slice], PHASE_PROBLEM, "This does not look like a variant case.")
				raise ValueError(template.value)
		elif isinstance(alt.pattern, syntax.NilToken):
			template = Cell(alt.pattern).assign(ontology.just_nil)
		else:
			assert False, alt.pattern
		self._solver.must_specialize(variant_typ, template, case)
		return self.visit(alt.expr, {**hypo, variant_typ:case})


	def visit_FieldReference(self, expr:syntax.FieldReference, hypo:dict[Cell:Cell]):
		inner = self.visit(expr.lhs, hypo)
		outer = Cell(expr.field_name)
		self._solver.field_access(inner, expr.field_name, outer)
		return outer
	
	def visit_ExplicitList(self, expr:syntax.ExplicitList, hypo:dict[Cell:Cell]):
		typ = Cell(expr)
		for e in expr.elts:
			self._solver.reads(typ, self.visit(e, hypo))
		concrete = ontology.ConcreteType(THE_LIST_TYPE, [typ])
		return Cell(expr).assign(concrete)
