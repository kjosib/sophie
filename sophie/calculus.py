"""
Part of the abstract-interpretation based type-checker.
These bits represent the data over which the type-checker operates.
To understand better, start by reading the "High-Order Type Checking"
section at https://sophie.readthedocs.io/en/latest/mechanics.html

I originally thought the type-numbering subsystem would mediate all interaction with concrete types.
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
from .ontology import Symbol, SELF
from .stacking import Frame, Activation

TYPE_ENV = Frame["SophieType"]

_type_numbering_subsystem = EquivalenceClassifier()

class SophieType:
	"""Value objects so they can play well with the classifier"""
	def visit(self, visitor:"TypeVisitor"): raise NotImplementedError(type(self))
	def expected_arity(self) -> int: raise NotImplementedError(type(self))
	def dispatch_signature(self) -> tuple[Symbol, ...]: raise NotImplementedError(type(self))
	def token(self) -> Symbol: pass

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

# Now, purely as an aid to understanding and recollection,
# I divide the space of types into:
# * Formal types, which exist independent of values in a simple Platonic algebra.
# * Computed types, the projection of value-domain code into the realm of types.

class FormalType(SophieType): pass
class ComputedType(SophieType): pass

class TypeVariable(FormalType):
	"""Did I say value-object? Not for type variables! These have identity."""
	def __init__(self):
		super().__init__(len(_type_numbering_subsystem.catalog))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_variable(self)
	def expected_arity(self) -> int: return -1  # Not callable


class OpaqueType(FormalType):
	def __init__(self, symbol:syntax.Opaque):
		assert type(symbol) is syntax.Opaque
		self.symbol = symbol
		super().__init__(symbol)
	def visit(self, visitor:"TypeVisitor"): return visitor.on_opaque(self)
	def expected_arity(self) -> int: return -1  # Not callable
	def token(self): return self.symbol

def _exemplargs(type_args: Iterable[SophieType], size) -> tuple[SophieType, ...]:
	them = tuple(a.exemplar() for a in type_args)
	assert len(them) == size, (len(them), size)
	return them

class RecordType(FormalType):
	def __init__(self, r:syntax.Record, type_args: Iterable[SophieType]):
		assert type(r) is syntax.Record
		self.symbol = r
		self.type_args = _exemplargs(type_args, len(r.type_params))
		super().__init__(self.symbol, *(a.number for a in self.type_args))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_record(self)
	def expected_arity(self) -> int: return -1  # Not callable. (There's a constructor arrow made.)
	def token(self): return self.symbol

class SumType(FormalType):
	""" Either a record directly, or a variant-type. Details are in the symbol table. """
	# NB: The arguments here are actual arguments, not formal parameters.
	#     The corresponding formal parameters are listed in the symbol,
	#     itself being either a TypeCase or a TypeDecl
	def __init__(self, variant: syntax.Variant, type_args: Iterable[SophieType]):
		assert isinstance(variant, syntax.Variant)
		self.variant = variant
		self.type_args = _exemplargs(type_args, len(variant.type_params))
		super().__init__(self.variant, *(a.number for a in self.type_args))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_sum(self)
	def expected_arity(self) -> int: return -1  # Not callable directly.
	def token(self): return self.variant

class SubType(FormalType):
	symbol: syntax.TypeCase
	def expected_arity(self) -> int: return -1  # Not callable. (There's a constructor arrow made.)

class EnumType(SubType):
	symbol: syntax.Tag
	def __init__(self, symbol: syntax.Tag):
		self.symbol = symbol
		super().__init__(symbol)
	def visit(self, visitor:"TypeVisitor"): return visitor.on_tag_enum(self)
	def token(self): return self.symbol.variant

class TaggedRecordType(SubType):
	symbol: syntax.TaggedRecord
	def __init__(self, symbol: syntax.TaggedRecord, type_args: Iterable[SophieType]):
		self.symbol = symbol
		self.type_args = _exemplargs(type_args, len(symbol.variant.type_params))
		super().__init__(symbol, *(a.number for a in self.type_args))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_tag_record(self)
	def token(self): return self.symbol.variant

class ProductType(FormalType):
	def __init__(self, fields: Iterable[SophieType]):
		self.fields = tuple(p.exemplar() for p in fields)
		super().__init__(*(p.number for p in self.fields))
	def visit(self, visitor:"TypeVisitor"): return visitor.on_product(self)
	def expected_arity(self) -> int: return -1  # Not callable

class ArrowType(FormalType):
	def __init__(self, arg: ProductType, res: SophieType):
		self.arg, self.res = arg.exemplar(), res.exemplar()
		super().__init__(self.arg, self.res)
	def visit(self, visitor:"TypeVisitor"): return visitor.on_arrow(self)
	def expected_arity(self) -> int: return len(self.arg.fields)
	def dispatch_signature(self) -> tuple[Symbol, ...]: return tuple(a.token() for a in self.arg.fields)

class MessageType(FormalType):
	def __init__(self, arg: ProductType):
		self.arg = arg
		super().__init__(self.arg)
	def visit(self, visitor: "TypeVisitor"): return visitor.on_message(self)
	def expected_arity(self) -> int:
		return len(self.arg.fields) or -1

class InterfaceType(FormalType):
	def __init__(self, symbol:syntax.Role, type_args: Iterable[SophieType]):
		assert type(symbol) is syntax.Role
		self.symbol = symbol
		self.type_args = _exemplargs(type_args, len(symbol.type_params))
		super().__init__(self.symbol, *(a.number for a in self.type_args))
	def visit(self, visitor: "TypeVisitor"): return visitor.on_interface(self)
	def expected_arity(self) -> int: return -1  # Not callable

class SubroutineType(ComputedType):
	"""
	Supertype for those of procedures and functions,
	because they have much structure in common.
	"""
	sub: syntax.Subroutine
	static_link: TYPE_ENV
	
	# Factoid: The static-link will contain a self-link in exactly the right cases,
	# and then there's no need for separate task and message types.
	# There's just a message type, always pointing to a UserProcType.
	
	def visit(self, visitor:"TypeVisitor"): return visitor.on_subroutine(self)
	def expected_arity(self) -> int: return len(self.sub.params)
	def __init__(self, sub:syntax.Subroutine, static_link:TYPE_ENV):
		self.sub = sub
		self.static_link = static_link
		# NB: The uniqueness notion here is excessive, but there's a plan to deal with that.
		#     Whatever instantiates a nested function must enter it in the static scope without duplication.
		#     Performance hacking may make for an even better cache than that.
		# TODO: It would be sufficient to key on the types captured in the lexical closure.
		#       Only DeductionEngine.visit_Lookup creates these, so it could provide the capture.
		super().__init__(object())

class UserFnType(SubroutineType):
	sub: syntax.UserFunction
	def __init__(self, sub:syntax.UserFunction, static_link:TYPE_ENV):
		assert isinstance(sub, syntax.UserFunction)
		super().__init__(sub, static_link)
	def dispatch_signature(self) -> tuple[Symbol, ...]:
		assert isinstance(self.sub, syntax.UserOperator)
		return self.sub.dispatch_vector()

class UserProcType(SubroutineType):
	sub: syntax.UserProcedure
	def __init__(self, sub:syntax.UserProcedure, static_link:TYPE_ENV):
		assert isinstance(sub, syntax.UserProcedure)
		super().__init__(sub, static_link)

class AdHocType(ComputedType):
	def __init__(self, glyph:str, arity:int):
		super().__init__(glyph, arity)
		self.glyph = glyph
		self._arity = arity
		self._cases = {}
	def visit(self, visitor:"TypeVisitor"): return visitor.on_ad_hoc(self)
	def expected_arity(self) -> int: return self._arity
	
	def dispatch(self, arg_types:Iterable[SophieType]) -> SophieType:
		arg_tokens = tuple(a.token() for a in arg_types)
		assert len(arg_tokens) == self._arity
		return self._cases.get(arg_tokens, ERROR)
		
	def append_case(self, case:SophieType, report):
		# FIXME: Cases need symbols so reporting can work right.
		#  The slightly larger picture might be to move the concept
		#  to the RoadMap object and make the resolver handle this.
		arg_tokens = case.dispatch_signature()
		if arg_tokens in self._cases: report.conflicting_overload()
		elif not all(arg_tokens): report.unsuported_overrload()
		elif len(arg_tokens) != self._arity: report.conflicting_overload()
		else: self._cases[arg_tokens] = case

class UserTaskType(ComputedType):
	""" The type of a task-ified user-defined (maybe-parametric) procedure. """
	def __init__(self, proc_type:UserProcType):
		assert isinstance(proc_type.sub, syntax.UserProcedure), type(proc_type.sub)
		self.proc_type = proc_type.exemplar()
		super().__init__(self.proc_type)
	def visit(self, visitor: "TypeVisitor"): return visitor.on_user_task(self)
	def expected_arity(self) -> int: return self.proc_type.expected_arity()

class _ActorDerived(ComputedType):
	args:tuple[SophieType, ...]
	
	def __init__(self, uda:syntax.UserActor, args:ProductType, global_env:TYPE_ENV):
		assert isinstance(args, ProductType), type(args)
		self.uda = uda
		self.args = args.fields
		self.global_env = global_env
		super().__init__(uda, args)

class ParametricTemplateType(_ActorDerived):
	def visit(self, visitor:"TypeVisitor"): return visitor.on_parametric_template(self)
	def expected_arity(self) -> int: return len(self.uda.members)

class ConcreteTemplateType(_ActorDerived):
	def visit(self, visitor:"TypeVisitor"): return visitor.on_concrete_template(self)
	def expected_arity(self) -> int: return -1  # Not callable; instantiable.
	def state_pairs(self):
		return zip(self.uda.members, self.args)

class UDAType(ComputedType):
	"""
	Has much in common with a subroutine type,
	except that the environment link here is going to contain
	the state of the actor itself. This is necessary because
	assignment statements can possibly cause state to promote.
	""" 
	def __init__(self, template:ConcreteTemplateType, dynamic_link:TYPE_ENV):
		self.uda = template.uda
		frame = Activation(template.global_env, dynamic_link, None)
		frame.assign(SELF, self)
		frame.update(template.state_pairs())
		self.frame = frame
		super().__init__(template)
		
	def visit(self, visitor:"TypeVisitor"): return visitor.on_uda(self)
	def expected_arity(self) -> int: return -1  # Not callable

class _Bottom(FormalType):
	"""
	The completely unrestricted type:
	It unifies with anything to become that other thing.
	This does double duty as "I don't know" and "I don't care".
	"""
	def visit(self, visitor:"TypeVisitor"): return visitor.on_bottom()

class _Error(FormalType):
	""" The type of things that make no sense or otherwise do not compute. """
	def visit(self, visitor:"TypeVisitor"): return visitor.on_error_type()

BOTTOM = _Bottom(None)
ERROR = _Error(None)
EMPTY_PRODUCT = ProductType(())
READY_MESSAGE = MessageType(EMPTY_PRODUCT).exemplar()

###################
#

class TypeVisitor:
	def on_variable(self, v:TypeVariable): raise NotImplementedError(type(self))
	def on_opaque(self, o: OpaqueType): raise NotImplementedError(type(self))
	def on_record(self, r:RecordType): raise NotImplementedError(type(self))
	def on_sum(self, s:SumType): raise NotImplementedError(type(self))
	def on_tag_enum(self, e: EnumType): raise NotImplementedError(type(self))
	def on_tag_record(self, t: TaggedRecordType): raise NotImplementedError(type(self))
	def on_arrow(self, a:ArrowType): raise NotImplementedError(type(self))
	def on_product(self, p:ProductType): raise NotImplementedError(type(self))
	def on_subroutine(self, sub:SubroutineType): raise NotImplementedError(type(self))
	def on_ad_hoc(self, f:AdHocType): raise NotImplementedError(type(self))
	def on_interface(self, it:InterfaceType): raise NotImplementedError(type(self))
	def on_parametric_template(self, t:ParametricTemplateType): raise NotImplementedError(type(self))
	def on_concrete_template(self, t:ConcreteTemplateType): raise NotImplementedError(type(self))
	def on_uda(self, a:UDAType): raise NotImplementedError(type(self))
	def on_message(self, m:MessageType): raise NotImplementedError(type(self))
	def on_user_task(self, t:UserTaskType): raise NotImplementedError(type(self))
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
	def _generic(self, params:tuple[SophieType, ...]):
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
	def on_tag_record(self, t: TaggedRecordType):
		return t.st.nom.text+self._generic(t.type_args)
	def on_arrow(self, a: ArrowType):
		return a.arg.visit(self)+"->"+a.res.visit(self)
	def on_product(self, p: ProductType):
		return self._args(p.fields)
	def _args(self, args:Iterable[SophieType]):
		return "(%s)"%(",".join(a.visit(self) for a in args))
	def on_subroutine(self, sub: SubroutineType):
		try:
			layer = sub.static_link.chase(SELF)
		except KeyError:
			return "<%s/%d>"%(sub.sub.nom.text, sub.expected_arity())
		else:
			uda_type = layer.fetch(SELF)
			return "<%s:%s/%d>" % (uda_type.uda.nom.text, sub.sub.nom.text, sub.expected_arity())
			
	def on_ad_hoc(self, f: AdHocType):
		return "<%s/%d>"%(f.glyph, f.expected_arity())
	def on_interface(self, it:InterfaceType):
		return "<interface:%s>"%it.symbol.nom.text
	def on_parametric_template(self, t: ParametricTemplateType):
		return "<template:%s/%d>"%(t.uda.nom.text, t.expected_arity())
	def on_concrete_template(self, t: ConcreteTemplateType):
		return "<template:%s%s>"%(t.uda.nom.text, self._args(t.args))
	def on_uda(self, a: UDAType):
		return "<actor:%s%s>"%(a.uda.nom.text, self._args(a.args))
	def on_message(self, m: MessageType):
		return "<message:%s>"%m.arg.visit(self)
	def on_user_task(self, t: UserTaskType):
		return "<task:%s>"%t.proc_type.visit(self)
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

