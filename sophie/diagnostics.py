import sys, random
from typing import Sequence, Optional, Union, Any
from traceback import TracebackException, format_stack
from pathlib import Path
from boozetools.support.failureprone import SourceText, Issue, Evidence, Severity, illustration
from . import syntax
from .ontology import Expr, Nom, Symbol, TermSymbol
from .calculus import TYPE_ENV, SophieType
from .stacking import Frame

class TooManyIssues(Exception):
	pass

def _outburst():
	particle = ["Oh, ", "Well, ", "Aw, ", "", ""]
	
	minced_oaths = [
		'Ack', 'ARGH', 'Blargh', 'Blasted Thing',
		'Confound it', 'Crud', 'Crud', 'Curses', "Crikey", "Cheese and Rice all Friday", 
		'Dag Blammit', 'Dag Nabbit', 'Darkness Everywhere', 'Drat',
		'Fiddlesticks', 'Flaming Flamingos',
		'Gack', 'Good Grief', 'Golly Gee Willikers', 'Great Googly Moogly', "Great Scott",
		'SNAP', "Snot", "Sweet Cheese and Crackers",
		"Infernal Tarnation", 'Jeepers', 'Heavens', "Heavens to Betsy",
		"Mercy", 'Nuts', 'Rats',
		'Whiskey Tango ....', 'Wretch it all', 'Woe be unto me', 'Woe is me',
	]
	
	resignatons = [
		'I am undone.',
		'I cannot continue.',
		'The path before me fades into darkness.',
		'I have no idea what the right answer is.',
		'I need to ask for help.',
		'I need an adult!',
	]
	
	return "%s%s! %s"%tuple(map(random.choice, (particle, minced_oaths, resignatons)))

class Report:
	""" Might this end up participating in a result-monad? """
	_issues : list[Union[Issue, "Pic", "Redefined", "Undefined"]]
	_path : Optional[Path]
	
	def __init__(self, *, verbose:int, max_issues=3):
		self._verbose = verbose or 0   # Because None is incomparable.
		self._issues = []
		self._redefined = {}
		self._already_complained_about = set()
		self._undefined = None
		self._path = None
		self._max_issues = max_issues
	
	def ok(self): return not self._issues
	def sick(self): return bool(self._issues)
	
	def issue(self, it:Any):
		self._issues.append(it)
		if len(self._issues) == self._max_issues:
			raise TooManyIssues(self)
	
	def reset(self):
		self._issues.clear()
	
	def info(self, *args):
		if self._verbose:
			print(*args, file=sys.stderr)
	
	def trace(self, *args):
		if self._verbose > 1:
			print(*args, file=sys.stderr)
	
	def set_path(self, path:Optional[Path]):
		""" Let the report know which file is under consideration, for in case of error. """
		# Yes, it's a temporal coupling. But it's a small worry, at least for now.
		self._path = path
		
	def error(self, phase: str, guilty: Sequence[slice], msg: str):
		""" Actually make an entry of an issue """
		for g in guilty:
			assert isinstance(g, slice), type(g)
		if guilty:
			assert self._path is not None
			for s in guilty:
				assert isinstance(s, slice), s
		evidence = {self._path: [Evidence(s, "") for s in guilty]}
		self.issue(Issue(phase, Severity.ERROR, msg, evidence))

	def complain_to_console(self):
		""" Emit all the issues to the console. """
		_bemoan(self._issues)
			
	def assert_no_issues(self, message):
		""" Does what it says on the tin """
		if self._issues:
			self.complain_to_console()
			assert False, "This is supposed to be impossible. "+message
	
	# Methods the front-end is likely to call:
	def generic_parse_error(self, path: Path, lookahead, node:Nom, hint: str):
		intro = "Sophie got confused by %s." % lookahead
		problem = [Annotation(path, node, "Sophie got confused here")]
		self.issue(Pic(intro, problem))
		self.issue(Pic(hint, []))

	# Methods the package / import mechanism invokes:

	def _file_error(self, path:Path, cause:Expr, prefix:str):
		intro = prefix+" "+str(path)
		if cause:
			problem = [Annotation(self._path, cause)]
		else:
			problem = []
		self.issue(Pic(intro, problem))
		
	def no_such_file(self, path:Path, cause:Expr):
		self._file_error(path, cause, "I see no file called")
	
	def broken_file(self, path:Path, cause:Expr):
		self._file_error(path, cause, "Something went pear-shaped while trying to read")
	
	def cyclic_import(self, cause, cycle):
		intro = "Here begins a cycle of imports. Sophie considers that an error."
		problem = [Annotation(self._path, cause)]
		footer = [" - The full cycle is:"]
		footer.extend('     '+str(path) for path in cycle)
		self.issue(Pic(intro, problem, footer))

	def no_such_package(self, cause:Nom):
		intro = "There's no such package:"
		problem = [Annotation(self._path, cause)]
		footer = ["(At the moment, there is only sys.)"]
		self.issue(Pic(intro, problem, footer))

	# Methods the resolver passes might call:
	def broken_foreign_module(self, source, tbx:TracebackException):
		msg = "Attempting to import this module threw an exception."
		text = ''.join(tbx.format())
		self.issue((Pic(text, [])))
		self.error("Defining words", [source.head()], msg)
	
	def missing_foreign_module(self, source):
		intro = "Missing Foreign Module"
		caption = "This module could not be found."
		self.issue(Pic(intro, [Annotation(self._path, source, caption)]))

	def missing_foreign_linkage(self, source):
		intro = "Missing Foreign Linkage Function"
		caption = "This module has no 'sophie_init'."
		self.issue(Pic(intro, [Annotation(self._path, source, caption)]))
		
	def wrong_linkage_arity(self, d:syntax.ImportForeign, arity:int):
		intro = "Disagreeable Foreign Linkage Function"
		caption = "This module's 'sophie_init' expects %d argument(s) but got %d instead."
		ann = Annotation(self._path, d.source, caption%(arity, len(d.linkage)))
		self.issue(Pic(intro, [ann]))

	def redefined(self, text:str, first:slice, guilty:slice):
		key = text, first
		if key not in self._redefined:
			issue = Redefined(_fetch(self._path), first)
			self.issue(issue)
			self._redefined[key] = issue
		self._redefined[key].note(guilty)

	def undefined_name(self, guilty:slice):
		assert isinstance(guilty, slice)
		if self._undefined is None:
			self._undefined = Undefined(_fetch(self._path))
			self.issue(self._undefined)
		self._undefined.note(guilty)

	def opaque_generic(self, guilty:Sequence[syntax.TypeParameter]):
		admonition = "Opaque types are not to be made generic."
		where = [g.head() for g in guilty]
		self.error("Defining Types", where, admonition)
	
	def can_only_see_member_within_behavior(self, nom:Nom):
		intro = "You can only refer to an actor's state within that actor's own behaviors."
		self.issue(Pic(intro, [Annotation(self._path, nom)]))
	
	def use_my_instead(self, env: TYPE_ENV, fr: syntax.FieldReference):
		intro = "To read an actor's own private state, use `my %s` here." % fr.field_name.text
		problem = [Annotation(env.path(), fr)]
		self.issue(Pic(intro, problem))
	
	def called_a_type_parameter(self, tc:syntax.TypeCall):
		pattern = "'%s' is a type-parameter, which cannot take type-arguments itself."
		intro = pattern % (tc.ref.nom.text)
		problem = [Annotation(self._path, tc)]
		self.issue(Pic(intro, problem))
	
	def wrong_type_arity(self, tc:syntax.TypeCall, given:int, needed:int):
		pattern = "%d type-arguments were given; %d are needed."
		intro = pattern % (given, needed)
		problem = [Annotation(self._path, tc)]
		self.issue(Pic(intro, problem))
	
	# Methods the Alias-checker calls
	def these_are_not_types(self, non_types:Sequence[syntax.TypeCall]):
		intro = "Words that get used like types, but refer to something else (e.g. variants, functions, or actors)."
		problem = [Annotation(self._path, tc) for tc in non_types]
		self.issue(Pic(intro, problem))
	
	def circular_type(self, scc:Sequence):
		intro = "What we have here is a circular type-definition."
		problem = [Annotation(self._path, node) for node in scc]
		self.issue(Pic(intro, problem))
	
	# Methods the match-checker calls
	def not_a_variant(self, ref:syntax.Reference):
		intro = "That's not a variant-type name"
		ann = Annotation(self._path, ref)
		self.issue(Pic(intro, [ann]))
	
	def not_a_case_of(self, nom:Nom, variant:syntax.Variant):
		# pattern = "This case is not a member of the variant-type <%s>."
		# intro = pattern%variant.nom.text
		self.undefined_name(nom.head())
		pass
	
	def not_a_case(self, nom:Nom):
		intro = "This needs to refer to one case of a variant-type."
		ann = Annotation(self._path, nom)
		self.issue(Pic(intro, [ann]))
	
	def not_exhaustive(self, mx:syntax.MatchExpr):
		pattern = "This case-block does not cover all the cases of <%s> and lacks an else-clause."
		intro = pattern % mx.variant.nom.text
		ann = Annotation(self._path, mx)
		self.issue(Pic(intro, [ann]))
	
	def redundant_pattern(self, prior:syntax.Alternative, new:syntax.Alternative):
		intro = "These two patterns are the same, or overlap, or are redundant."
		problem = [
			Annotation(self._path, prior.pattern, "First"),
			Annotation(self._path, new.pattern, "Not First")
		]
		footer = ["That's probably an oversight."]
		self.issue(Pic(intro, problem, footer))

	def redundant_else(self, mx:syntax.MatchExpr):
		intro = "This case-block has an extra else-clause."
		problem = [
			Annotation(self._path, mx, "covers every case"),
			Annotation(self._path, mx.otherwise, "cannot happen")
		]
		footer = ["That's probably an oversight."]
		self.issue(Pic(intro, problem, footer))

	# Methods specific to report type-checking issues.
	
	def type_mismatch(self, env:TYPE_ENV, x1:syntax.ValExpr, t1:SophieType, x2:syntax.ValExpr, t2:SophieType):
		intro = "Types for these expressions need to match, but they do not."
		path = env.path()
		problem = [
			Annotation(path, x1, str(t1)),
			Annotation(path, x2, str(t2)),
		]
		self.issue(Pic(intro, problem))
		self.issue(Pic("Here's how that happens:", trace_stack(env)))
	
	def wrong_arity(self, env:TYPE_ENV, site:syntax.ValExpr, callee_type:SophieType, args:Sequence[syntax.ValExpr]):
		arity = callee_type.expected_arity()
		if site not in self._already_complained_about:
			self._already_complained_about.add(site)
			if arity < 0:
				intro = "This %s is not callable."%callee_type
			else:
				plural = '' if arity == 1 else 's'
				pattern = "This %s takes %d argument%s, but got %d instead."
				intro = pattern % (callee_type, arity, plural, len(args))
			problem = [Annotation(env.path(), site, intro)]
			self.issue(Pic(intro, trace_stack(env) + problem))
	
	def bad_argument(self, env: TYPE_ENV, term:TermSymbol, param:syntax.FormalParameter, actual:SophieType, why:str):
		assert isinstance(term, TermSymbol)
		assert isinstance(param, syntax.FormalParameter)
		assert isinstance(why, str)
		intro = "Type-checking found a square peg in a round hole:"
		caption = str(actual) + " does not apply because " + why
		problem = [Annotation(term.source_path, param, caption)]
		self.issue(Pic(intro, trace_stack(env)+problem))
	
	def bad_result(self, env: TYPE_ENV, fn:syntax.UserFunction, result_type, why):
		intro = "Type-checking found a problematic result:"
		produced = Annotation(fn.source_path, fn.expr, "Produced "+str(result_type))
		caption = "Did not match because " + why
		needed = Annotation(fn.source_path, fn.result_type_expr, caption)
		self.issue(Pic(intro, trace_stack(env)+[produced, needed]))

	def bad_type(self, env: TYPE_ENV, expr: syntax.ValExpr, need, got, why):
		intro = "Type-checking found a problem. Here's how it happens:"
		complaint = "This %s needs to be a(n) %s."%(got, need)
		problem = [Annotation(env.path(), expr, complaint)]
		self.issue(Pic(intro, trace_stack(env)+problem, (why,)))
	
	def bad_task(self, env: TYPE_ENV, expr: syntax.ValExpr, got):
		intro = "I don't know how to convert %s into a task." % got
		footer = "Typically you'll want a procedure here."
		problem = [Annotation(env.path(), expr)]
		self.issue(Pic(intro, trace_stack(env)+problem, (footer,)))

	
	def does_not_express_behavior(self, env: TYPE_ENV, procedure:syntax.UserProcedure, got):
		intro = "This definition expresses %s instead of behavior"%got
		problem = [Annotation(env.path(), procedure)]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def must_not_express_behavior(self, env: TYPE_ENV, fn:syntax.UserFunction):
		intro = "Procedural steps cannot happen within a pure function."
		problem = [Annotation(env.path(), fn)]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def bad_message(self, env:TYPE_ENV, expr:syntax.BindMethod, actor_type:SophieType):
		intro = "This %s does not understand..." % actor_type
		problem = [Annotation(env.path(), expr.method_name, "this message")]
		self.issue(Pic(intro, trace_stack(env)+problem))
	
	def type_has_no_fields(self, env:TYPE_ENV, fr:syntax.FieldReference, lhs_type):
		field = fr.field_name.text
		intro = "Type-checking found an unsuitable source for field '%s' access."%field
		complaint = "%s has no fields; in particular not '%s'."%(lhs_type, field)
		problem = [Annotation(env.path(), fr, complaint)]
		self.issue(Pic(intro, trace_stack(env)+problem))
	
	def no_telepathy_allowed(self, env:TYPE_ENV, fr:syntax.FieldReference, lhs_type):
		intro = "You cannot read the private state of actor %s."%lhs_type
		problem = [Annotation(env.path(), fr)]
		self.issue(Pic(intro, trace_stack(env)+problem))
	
	def record_lacks_field(self, env:TYPE_ENV, fr:syntax.FieldReference, lhs_type:SophieType):
		field = fr.field_name.text
		intro = "Type-checking found an unsuitable source for field '%s' access."%field
		complaint = "Type '%s' has fields, but not one called '%s'."%(lhs_type, field)
		problem = [Annotation(env.path(), fr, complaint)]
		self.issue(Pic(intro, trace_stack(env)+problem))
	
	def ill_founded_function(self, env:TYPE_ENV, sub:syntax.Subroutine):
		intro = "This definition turned up circular, as in a=a."
		problem = [Annotation(sub.source_path, sub, "This one.")]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def no_applicable_method(self, env:TYPE_ENV, actual_types):
		intro = "A type-directed operation goes off the rails. Here's how:"
		footer = [
			"This operator has no method for "+str(tuple(actual_types))+".",
			"If these are the types you mean to operate on,",
			"then please define the operator for these types.",
		]
		self.issue(Pic(intro, trace_stack(env), footer))
	
	def bogus_operator_arity(self, udf):
		intro = "Define most operators for two arguments. Negation (-) can also be defined for only one."
		problem = [Annotation(udf.source_path, udf, "This one.")]
		self.issue(Pic(intro, problem))

	# Some things for just in case:
	
	def drat(self, env:TYPE_ENV, hint):
		intro = "This code hits an unfinished part of the type-checker."
		python_frames = map(str.rstrip, format_stack(limit=8)[:-1])
		footer = [
			"",
			"Hint: "+str(hint),
			"",
			"Recent Python frames:",
			*python_frames,
		]
		self.issue(Pic(intro, trace_stack(env), footer))
		# self.complain_to_console()

class Annotation:
	path: Path
	slice: slice
	caption: str
	def __init__(self, path:Path, node, caption:str=""):
		self.path = path
		self.slice = node.head()
		self.caption = caption
		assert isinstance(self.slice, slice), (type(node), "head method fails to return a slice.")

def illustrate(source, span:slice, caption):
	row, col = source.find_row_col(span.start)
	single_line = source.line_of_text(row)
	width = span.stop - span.start
	return illustration(single_line, col, width, prefix='% 6d |' % row, caption=caption)

class Tracer:
	def __init__(self):
		self.trace = []
	def called_from(self, path, pc):
		self.trace.append(Annotation(path, pc))
	def hit_bottom(self):
		pass
	def trace_frame(self, path, breadcrumb, bindings):
		args = {
			k:v for k,v in bindings.items()
			if isinstance(k, (syntax.FormalParameter, syntax.Subject))
		}
		if args:
			bind_text = ', '.join("%s:%s" % (p.nom.text, t) for p, t in args.items())
			self.trace.append(Annotation(path, breadcrumb, bind_text))

		

def trace_stack(env:Frame) -> list[Annotation]:
	tracer = Tracer()
	env.trace(tracer)
	return tracer.trace

class Pic:
	def __init__(self, intro:str, trace:list[Annotation], footer=()):
		source, path = ..., ...
		self.lines = [intro, ""]
		for ann in trace:
			if ann.path != path:
				path = ann.path
				self.lines.append(str(path))
				source = _fetch(path)
			self.lines.append(illustrate(source, ann.slice, ann.caption))
		self.lines.extend(footer)
	def as_text(self, fetch):
		return '\n'.join(self.lines)
		
def _fetch(path) -> SourceText:
	if path is None:
		return SourceText("")
	with open(path, "r", encoding="utf-8") as fh:
		return SourceText(fh.read(), filename=str(path))

class Redefined:
	def __init__(self, source:SourceText, earliest:slice):
		self._source = source
		self._lines = [
			"This symbol is defined more than once in the same scope.",
			illustrate(source, earliest, "Earliest definition"),
		]
	def note(self, span:slice):
		self._lines.append(illustrate(self._source, span, ""))
	def as_text(self, fetch):
		return '\n'.join(self._lines)

class Undefined:
	def __init__(self, source:SourceText):
		self._source = source
		self._lines = ["In file: "+str(source.filename), "I don't see what this refers to."]
	def note(self, span:slice):
		self._lines.append(illustrate(self._source, span, ""))
	def as_text(self, fetch):
		return '\n'.join(self._lines)

def trace_absurdity(env:Frame, absurdity:syntax.Absurdity):
	intro = "Absurd thing happened:"
	problem = [Annotation(env.path(), absurdity)]
	_bemoan([Pic(intro, trace_stack(env) + problem)])

def _bemoan(issues):
	""" Emit all the issues to the console. """
	if issues:
		print("*"*60, file=sys.stderr)
		print(_outburst(), file=sys.stderr)
	for i in issues:
		print("  -"*20, file=sys.stderr)
		print(i.as_text(_fetch), file=sys.stderr)
