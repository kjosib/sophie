"""
Part of the abstract-interpretation based type-checker.
These bits represent the data over which the type-checker operates.
To understand better, start by reading the "High-Order Type Checking"
section at https://sophie.readthedocs.io/en/latest/mechanics.html

This file is enumerates all kinds of types, which include first-order types like:
	Type Variables (i.e. known-unknowns)
	Nominal types (which refer back to symbols, and do by definition have exactly however many arguments as the symbol)
	Arrow types (which generally have a product on the left)
	Product types (which are generally found on the left side of an arrow)
	Bottom (about which the algebraic laws are written at the link above)
	Error: The type that means something went off the rails.
	
and also some additional type-operators:
	FieldType: represents field-access as a function-like type.
	UnionType: represents selection points which depend on run-time data, and a related concept with list syntax.
	UDFType: Deals with user-defined functions which may be polymorphic in weird ways.
	CallSiteType: Combines an arrow-type (or UDF) with an argument to get a result.

I originally thought he type-numbering subsystem would mediate all interaction with concrete types.
Clients would call for what they mean to compose, and the subsystem would give back a type-number.
Or, given a type-number, the subsystem could return a smart object.
But then I remembered the rest of the world is only readable in terms of smart objects.
Therefore, the present design maps all type-parameters to their exemplars,
and uses type-numbering internally to make hash-checks and equality comparisons go fast.

Conveniently, type-numbering is just an equivalence classification scheme.
I can reuse the one from booze-tools.

"""
from typing import Iterable
from boozetools.support.foundation import EquivalenceClassifier
from . import syntax
from .ontology import Symbol
from .stacking import Frame

TYPE_ENV = Frame["SophieType"]

_type_numbering_subsystem = EquivalenceClassifier()

class SophieType:
	"""Value objects so they can play well with the classifier"""
	def visit(self, visitor:"TypeVisitor"): raise NotImplementedError(type(self))
	def expected_arity(self) -> int: raise NotImplementedError(type(self))

	def __init__(self, *key):
		self._key = key
		self._hash = hash(key)
		self.number = _type_numbering_subsystem.classify(self)
	def __hash__(self): return self._hash
	def __eq__(self, other: "SophieType"): return type(self) is type(other) and self._key == other._key
	def exemplar(self) -> "SophieType": return _type_numbering_subsystem.exemplars[self.number]
	def __repr__(self) -> str:
		it = self.visit(Render())
		assert isinstance(it, str), (it, type(self))
		return it

class TypeVariable(SophieType):
	"""Did I say value-object? Not for type variables! These have identity."""
	def __init__(self):
		super().__init__(len(_type_numbering_subsystem.catalog))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_variable(self)
	def expected_arity(self) -> int: return -1  # Not callable

class OpaqueType(SophieType):
	def __init__(self, symbol:syntax.Opaque):
		assert type(symbol) is syntax.Opaque
		self.symbol = symbol
		super().__init__(symbol)
	def visit(self, visitor:"TypeVisitor"): return visitor.on_opaque(self)
	def expected_arity(self) -> int: return -1  # Not callable

class RecordType(SophieType):
	def __init__(self, r:syntax.Record, type_args: Iterable[SophieType]):
		assert type(r) is syntax.Record
		self.symbol = r
		self.type_args = tuple(a.exemplar() for a in type_args)
		assert len(self.type_args) == len(r.type_params)
		super().__init__(self.symbol, *(a.number for a in self.type_args))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_record(self)
	def expected_arity(self) -> int: return -1  # Not callable. (There's a constructor arrow made.)

class SumType(SophieType):
	""" Either a record directly, or a variant-type. Details are in the symbol table. """
	# NB: The arguments here are actual arguments, not formal parameters.
	#     The corresponding formal parameters are listed in the symbol,
	#     itself being either a SubTypeSpec or a TypeDecl
	def __init__(self, variant: syntax.Variant, type_args: Iterable[SophieType]):
		assert isinstance(variant, syntax.Variant)
		self.variant = variant
		self.type_args = tuple(a.exemplar() for a in type_args)
		assert len(self.type_args) == len(variant.type_params)
		super().__init__(self.variant, *(a.number for a in self.type_args))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_sum(self)
	def expected_arity(self) -> int: return -1  # Not callable directly.

class SubType(SophieType):
	st : syntax.SubTypeSpec
	def expected_arity(self) -> int: return -1  # Not callable. (There's a constructor arrow made.)

class EnumType(SubType):
	def __init__(self, st: syntax.SubTypeSpec):
		assert st.body is None
		self.st = st
		super().__init__(st)
	def visit(self, visitor:"TypeVisitor"): return visitor.on_tag_enum(self)
	def family(self) -> Symbol: return self.st.variant

class TaggedRecord(SubType):
	def __init__(self, st: syntax.SubTypeSpec, type_args: Iterable[SophieType]):
		assert isinstance(st, syntax.SubTypeSpec)
		assert isinstance(st.body, syntax.RecordSpec)
		self.st = st
		self.type_args = tuple(a.exemplar() for a in type_args)
		assert len(self.type_args) == len(st.variant.type_params)
		super().__init__(st, *(a.number for a in self.type_args))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_tag_record(self)
	def family(self) -> Symbol: return self.st.variant

class ProductType(SophieType):
	def __init__(self, fields: Iterable[SophieType]):
		self.fields = tuple(p.exemplar() for p in fields)
		super().__init__(*(p.number for p in self.fields))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_product(self)
	def expected_arity(self) -> int: return -1  # Not callable

class ArrowType(SophieType):
	def __init__(self, arg: ProductType, res: SophieType):
		self.arg, self.res = arg.exemplar(), res.exemplar()
		super().__init__(self.arg, self.res)
	def visit(self, visitor:"TypeVisitor"): return visitor.on_arrow(self)
	def expected_arity(self) -> int: return len(self.arg.fields)

class MessageType(SophieType):
	def __init__(self, arg: ProductType):
		assert arg.fields
		self.arg = arg
		super().__init__(self.arg)
	def visit(self, visitor: "TypeVisitor"): return visitor.on_message(self)
	def expected_arity(self) -> int: return -1  # Not callable; sendable.

class UDFType(SophieType):
	fn: syntax.UserFunction
	static_link: TYPE_ENV
	def visit(self, visitor:"TypeVisitor"): return visitor.on_udf(self)
	def expected_arity(self) -> int: return len(self.fn.params)
	def __init__(self, fn:syntax.UserFunction, static_link:TYPE_ENV):
		self.fn = fn
		self.static_link = static_link
		# NB: The uniqueness notion here is excessive, but there's a plan to deal with that.
		#     Whatever instantiates a nested function must enter it in the static scope without duplication.
		#     Performance hacking may make for an even better cache than that.
		# TODO: It would be sufficient to key on the types captured in the lexical closure.
		#       Only DeductionEngine.visit_Lookup creates these, so it could provide the capture.
		super().__init__(object())

class UserTaskType(SophieType):
	""" The type of a task-ified user-defined (parametric) function. """
	def __init__(self, udf_type:UDFType):
		assert udf_type.fn.params
		self.udf_type = udf_type.exemplar()
		super().__init__(self.udf_type)
	def visit(self, visitor: "TypeVisitor"): return visitor.on_user_task(self)
	def expected_arity(self) -> int: return self.udf_type.expected_arity()

class InterfaceType(SophieType):
	def __init__(self, symbol:syntax.Interface, type_args: Iterable[SophieType]):
		assert type(symbol) is syntax.Interface
		self.symbol = symbol
		self.type_args = tuple(a.exemplar() for a in type_args)
		assert len(self.type_args) == len(symbol.type_params)
		super().__init__(self.symbol, *(a.number for a in self.type_args))
	def visit(self, visitor: "TypeVisitor"): return visitor.on_interface(self)
	def expected_arity(self) -> int: return -1  # Not callable

class _AgentDerived(SophieType):
	def __init__(self, uda:syntax.UserAgent, args:ProductType, frame:TYPE_ENV):
		self.uda = uda
		self.args = args
		# By definition the static link for a template is its own module's global scope.
		# For a UDAType the proper static link should be an extension with a SELF link.
		self.frame = frame
		super().__init__(uda, args)

class ParametricTemplateType(_AgentDerived):
	def visit(self, visitor:"TypeVisitor"): return visitor.on_parametric_template(self)
	def expected_arity(self) -> int: return len(self.uda.fields)

class ConcreteTemplateType(_AgentDerived):
	def visit(self, visitor:"TypeVisitor"): return visitor.on_concrete_template(self)
	def expected_arity(self) -> int: return -1  # Not callable; instantiable.

class UDAType(_AgentDerived):
	def visit(self, visitor:"TypeVisitor"): return visitor.on_uda(self)
	def expected_arity(self) -> int: return -1  # Not callable; instantiable.

class BehaviorType(SophieType):
	def __init__(self, uda_type:UDAType, behavior:syntax.Behavior):
		self.uda_type = uda_type
		self.behavior = behavior
		super().__init__(uda_type, behavior)
	def visit(self, visitor:"TypeVisitor"): return visitor.on_behavior(self)
	def expected_arity(self) -> int: return len(self.behavior.params)


class _Bottom(SophieType):
	def visit(self, visitor:"TypeVisitor"): return visitor.on_bottom()

class _Error(SophieType):
	def visit(self, visitor:"TypeVisitor"): return visitor.on_error_type()

BOTTOM = _Bottom(None)
ERROR = _Error(None)
EMPTY_PRODUCT = ProductType(())

###################
#

class TypeVisitor:
	def on_variable(self, v:TypeVariable): raise NotImplementedError(type(self))
	def on_opaque(self, o: OpaqueType): raise NotImplementedError(type(self))
	def on_record(self, r:RecordType): raise NotImplementedError(type(self))
	def on_sum(self, s:SumType): raise NotImplementedError(type(self))
	def on_tag_enum(self, e: EnumType): raise NotImplementedError(type(self))
	def on_tag_record(self, t: TaggedRecord): raise NotImplementedError(type(self))
	def on_arrow(self, a:ArrowType): raise NotImplementedError(type(self))
	def on_product(self, p:ProductType): raise NotImplementedError(type(self))
	def on_udf(self, f:UDFType): raise NotImplementedError(type(self))
	def on_interface(self, it:InterfaceType): raise NotImplementedError(type(self))
	def on_parametric_template(self, t:ParametricTemplateType): raise NotImplementedError(type(self))
	def on_concrete_template(self, t:ConcreteTemplateType): raise NotImplementedError(type(self))
	def on_uda(self, a:UDAType): raise NotImplementedError(type(self))
	def on_message(self, m:MessageType): raise NotImplementedError(type(self))
	def on_user_task(self, t:UserTaskType): raise NotImplementedError(type(self))
	def on_behavior(self, t:BehaviorType): raise NotImplementedError(type(self))
	def on_bottom(self): raise NotImplementedError(type(self))
	def on_error_type(self): raise NotImplementedError(type(self))


class Render(TypeVisitor):
	""" Return a string representation of the term. """
	def __init__(self):
		self._var_names = {}
	def on_variable(self, v: TypeVariable):
		if v not in self._var_names:
			self._var_names[v] = "?%s" % _name_variable(len(self._var_names) + 1)
		return self._var_names[v]
	def on_opaque(self, o: OpaqueType):
		return o.symbol.nom.text
	def _generic(self, params:tuple[SophieType]):
		if params:
			return "[%s]"%(",".join(t.visit(self) for t in params))
		else:
			return ""
	def on_record(self, r: RecordType):
		return r.symbol.nom.text+self._generic(r.type_args)
	def on_sum(self, s: SumType):
		return s.variant.nom.text+self._generic(s.type_args)
	def on_tag_enum(self, e: EnumType):
		return e.st.nom.text
	def on_tag_record(self, t: TaggedRecord):
		return t.st.nom.text+self._generic(t.type_args)
	def on_arrow(self, a: ArrowType):
		return a.arg.visit(self)+"->"+a.res.visit(self)
	def on_product(self, p: ProductType):
		return "(%s)"%(",".join(t.visit(self) for t in p.fields))
	def on_udf(self, f: UDFType):
		return "<%s/%d>"%(f.fn.nom.text, f.expected_arity())
	def on_interface(self, it:InterfaceType):
		return "<interface:%s>"%it.symbol.nom.text
	def on_parametric_template(self, t: ParametricTemplateType):
		return "<template:%s/%d>"%(t.uda.nom.text, t.expected_arity())
	def on_concrete_template(self, t: ConcreteTemplateType):
		return "<template:%s%s>"%(t.uda.nom.text, t.args.visit(self))
	def on_uda(self, a: UDAType):
		return "<agent:%s%s>"%(a.uda.nom.text, a.args.visit(self))
	def on_message(self, m: MessageType):
		return "<message:%s>"%m.arg.visit(self)
	def on_user_task(self, t: UserTaskType):
		return "<task:%s>"%t.udf_type.visit(self)
	def on_behavior(self, t: BehaviorType):
		return "<%s:%s/%d>"%(t.uda_type.uda.nom.text, t.behavior.nom.text, t.expected_arity())
	def on_bottom(self):
		return "?"
	def on_error_type(self):
		return "-/error/-"
	
def _name_variable(n):
	name = ""
	while n:
		n, remainder = divmod(n-1, 26)
		name = chr(97+remainder) + name
	return name

