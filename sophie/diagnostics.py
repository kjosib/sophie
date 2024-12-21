import sys, random
from collections import defaultdict
from functools import lru_cache
from typing import Sequence, Any, Iterable
from traceback import TracebackException, format_stack
from pathlib import Path
from boozetools.support.failureprone import SourceText, illustration

from .location import lookup_span
from .ontology import Phrase, Nom
from .stacking import Frame
from . import syntax
from .static.domain import SophieType

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
	
	resignations = [
		'I am undone.',
		'I cannot continue.',
		'The path before me fades into darkness.',
		'I have no idea what the right answer is.',
		'I need to ask for help.',
		'I need an adult!',
	]
	
	return "%s%s! %s"%tuple(map(random.choice, (particle, minced_oaths, resignations)))

class Report:
	""" Might this end up participating in a result-monad? """
	_issues : list["Pic"]
	
	def __init__(self, *, verbose:int, max_issues=3):
		self._verbose = verbose or 0   # Because None is incomparable.
		self._issues = []
		self._redefined = {}
		self._already_complained_about = set()
		self._undefined = None
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
	
	@staticmethod
	def trace(message, site):
		ann = Annotation(site, message)
		print(ann.illustrate(), ann.path, file=sys.stderr)
	
	def error(self, guilty: Sequence[Phrase], msg: str):
		""" Actually make an entry of an issue """
		for g in guilty: assert isinstance(g, Phrase), g
		problem = [Annotation(g, "") for g in guilty]
		self.issue(Pic(msg, problem))

	def complain_to_console(self):
		""" Emit all the issues to the console. """
		_bemoan(self._issues)
			
	def assert_no_issues(self, message):
		""" Does what it says on the tin """
		if self._issues:
			self.complain_to_console()
			raise AssertionError(_outburst()+" "+message)
	
	# Methods the front-end is likely to call:
	def generic_parse_error(self, kind, token:Phrase, hint:str):
		intro = "Sophie got confused by %s." % kind
		problem = [Annotation(token, "Sophie got confused here")]
		self.issue(Pic(intro, problem, [hint]))
	
	def ran_out_of_tokens(self, path:Path, hint:str):
		intro = "Ran out of words in %s"%path
		self.issue(Pic(intro, [], [hint]))

	# Methods the package / import mechanism invokes:

	def _file_error(self, path:Path, cause:Phrase, prefix:str):
		intro = prefix+" "+str(path)
		if cause:
			problem = [Annotation(cause)]
		else:
			problem = []
		self.issue(Pic(intro, problem))
		
	def no_such_file(self, path:Path, cause:Phrase):
		self._file_error(path, cause, "I see no file called")
	
	def broken_file(self, path:Path, cause:Phrase):
		self._file_error(path, cause, "Something went pear-shaped while trying to read")
	
	def cyclic_import(self, cause, cycle):
		intro = "Here begins a cycle of imports. Sophie considers that an error."
		problem = [Annotation(cause)]
		footer = [" - The full cycle is:"]
		footer.extend('     '+str(path) for path in cycle)
		self.issue(Pic(intro, problem, footer))

	def no_such_package(self, cause:Nom):
		intro = "There's no such package:"
		problem = [Annotation(cause)]
		footer = ["(At the moment, there is only sys.)"]
		self.issue(Pic(intro, problem, footer))

	# Methods the resolver passes might call:
	def broken_foreign_module(self, source, tbx:TracebackException):
		msg = "Attempting to import this module threw an exception."
		text = ''.join(tbx.format())
		self.issue((Pic(text, [])))
		self.error([source], msg)
	
	def missing_foreign_module(self, source):
		intro = "Missing Foreign Module"
		caption = "This module could not be found."
		self.issue(Pic(intro, [Annotation(source, caption)]))

	def missing_foreign_linkage(self, source):
		intro = "Missing Foreign Linkage Function"
		caption = "This module has no 'sophie_init'."
		self.issue(Pic(intro, [Annotation(source, caption)]))
		
	def wrong_linkage_arity(self, d:syntax.ImportForeign, arity:int):
		intro = "Disagreeable Foreign Linkage Function"
		caption = "This module's 'sophie_init' expects %d argument(s) but got %d instead."
		ann = Annotation(d.source, caption%(arity, len(d.linkage)))
		self.issue(Pic(intro, [ann]))

	def redefined(self, text:str, first:Phrase, guilty:Phrase):
		key = text, first
		if key not in self._redefined:
			intro = "This symbol is defined more than once in the same scope."
			issue = Pic(intro, [Annotation(first, "Earliest definition")])
			self.issue(issue)
			self._redefined[key] = issue
		self._redefined[key].also(guilty)

	def undefined_name(self, guilty:Phrase):
		assert isinstance(guilty, Phrase)
		if self._undefined is None:
			intro = "I don't see what this refers to."
			self._undefined = Pic(intro, [])
			self.issue(self._undefined)
		self._undefined.also(guilty)

	def opaque_generic(self, guilty:Sequence[syntax.TypeParameter]):
		admonition = "Opaque types are not to be made generic."
		self.error([guilty], admonition)
	
	def can_only_see_member_within_behavior(self, nom:Nom):
		intro = "You can only refer to an actor's state within that actor's own behaviors."
		self.issue(Pic(intro, [Annotation(nom)]))
	
	def use_my_instead(self, fr: syntax.FieldReference):
		intro = "To read an actor's own private state, use `my %s` here." % fr.field_name.text
		problem = [Annotation(fr)]
		self.issue(Pic(intro, problem))
	
	def called_a_type_parameter(self, tc:syntax.TypeCall):
		pattern = "'%s' is a type-parameter, which cannot take type-arguments itself."
		intro = pattern % tc.ref.nom.text
		problem = [Annotation(tc)]
		self.issue(Pic(intro, problem))
	
	def wrong_type_arity(self, tc:syntax.TypeCall, given:int, needed:int):
		pattern = "%d type-arguments were given; %d are needed."
		intro = pattern % (given, needed)
		problem = [Annotation(tc)]
		self.issue(Pic(intro, problem))
	
	# Methods the Alias-checker calls
	def these_are_not_types(self, non_types:Sequence[syntax.TypeCall]):
		intro = "Words that get used like types, but refer to something else (e.g. variants, functions, or actors)."
		problem = [Annotation(tc) for tc in non_types]
		self.issue(Pic(intro, problem))
	
	def circular_type(self, scc:Sequence):
		intro = "What we have here is a circular type-definition."
		problem = [Annotation(node) for node in scc]
		self.issue(Pic(intro, problem))
	
	# Methods the match-checker calls
	def not_a_variant(self, ref:syntax.Reference):
		intro = "That's not a variant-type name"
		ann = Annotation(ref)
		self.issue(Pic(intro, [ann]))
	
	def not_a_case_of(self, nom:Nom, variant:syntax.VariantSymbol):
		pattern = "This case is not a member of the variant-type <%s>."
		intro = pattern%variant.nom.text
		ann = Annotation(nom)
		self.issue(Pic(intro, [ann]))
	
	def not_a_case(self, nom:Nom):
		intro = "This needs to refer to one case of a variant-type."
		ann = Annotation(nom)
		self.issue(Pic(intro, [ann]))
	
	def not_exhaustive(self, mx:syntax.MatchExpr):
		pattern = "This case-block does not cover all the cases of <%s> and lacks an else-clause."
		intro = pattern % mx.variant.nom.text
		ann = Annotation(mx)
		self.issue(Pic(intro, [ann]))
	
	def redundant_pattern(self, prior:syntax.Alternative, new:syntax.Alternative):
		intro = "These two patterns are the same, or overlap, or are redundant."
		problem = [
			Annotation(prior.pattern, "First"),
			Annotation(new.pattern, "Not First")
		]
		footer = ["That's probably an oversight."]
		self.issue(Pic(intro, problem, footer))

	def redundant_else(self, mx:syntax.MatchExpr):
		intro = "This case-block has an extra else-clause."
		problem = [
			Annotation(mx, "covers every case"),
			Annotation(mx.otherwise, "cannot happen")
		]
		footer = ["That's probably an oversight."]
		self.issue(Pic(intro, problem, footer))

	# # Methods specific to report type-checking issues.
	# 
	def type_mismatch(self, env:Frame, x1:syntax.ValueExpression, t1, x2:syntax.ValueExpression, t2):
		intro = "Types for these expressions need to match, but they do not."
		problem = [
			Annotation(x1, str(t1)),
			Annotation(x2, str(t2)),
		]
		self.issue(Pic(intro, problem))
		self.issue(Pic("Here's how that happens:", trace_stack(env)))
	
	def not_callable(self, frame:Frame, site:syntax.ValueExpression, callee:SophieType):
		intro = "Dunno how to call %s as a function." % callee
		ann = Annotation(site, "Found to be "+str(callee))
		self.issue(Pic(intro, trace_stack(frame) + [ann]))
	
	def wrong_arity(self, frame:Frame, site:syntax.ValueExpression, need:int, got:int):
		intro = "Type-checking found a disagreement over arguments."
		if site not in self._already_complained_about:
			self._already_complained_about.add(site)
			plural = '' if need == 1 else 's'
			pattern = "This takes %d argument%s, but got %d instead."
			caption = pattern % (need, plural, got)
			problem = [Annotation(site, caption)]
			self.issue(Pic(intro, trace_stack(frame) + problem))

	def bad_argument(self, env: Frame, expr, mismatch):
		self.bad_type(env, expr, mismatch.need, mismatch.got)

	def bad_result(self, env: Frame, sub:syntax.Subroutine, mismatch):
		intro = "Type-checking found a problematic result:"
		need = Annotation(sub.result_type_expr, "Declared this")
		got = Annotation(sub.expr, "Produced " + str(mismatch.got))
		self.issue(Pic(intro, trace_stack(env)+[need, got]))

	def bad_type(self, env: Frame, expr: syntax.ValueExpression, need, got):
		intro = "Type-checking found %s where %s was expected:"%(got, need)
		complaint = "This %s needs to be a(n) %s."%(got, need)
		problem = [Annotation(expr, complaint)]
		self.issue(Pic(intro, trace_stack(env) + problem))

	def bad_task(self, env: Frame, expr: syntax.ValueExpression, got):
		intro = "I don't know how to make this %s into a task." % got
		footer = "Typically you'll refer to a procedure here."
		problem = [Annotation(expr, "judged to be "+str(got))]
		self.issue(Pic(intro, trace_stack(env)+problem, (footer,)))
	
	def does_not_express_behavior(self, env: Frame, procedure:syntax.Subroutine, got):
		intro = "This definition expresses %s instead of behavior"%got
		problem = [Annotation(procedure)]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def must_not_express_behavior(self, env: Frame, fn:syntax.Subroutine):
		intro = "Procedural steps cannot happen within a pure function."
		problem = [Annotation(fn)]
		self.issue(Pic(intro, trace_stack(env)+problem))
	
	def not_an_actor(self, env:Frame, expr:syntax.ValueExpression, got):
		intro = "Tried to send a message to not-an-actor:"
		problem = [Annotation(expr, "Seems to be "+str(got))]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def bad_message(self, env:Frame, method_name:Nom, actor_type):
		intro = "This %s does not understand..." % actor_type
		problem = [Annotation(method_name, "this message")]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def type_has_no_fields(self, env:Frame, fr:syntax.FieldReference, lhs_type):
		field = fr.field_name.text
		intro = "Type-checking found an unsuitable source for field '%s' access."%field
		complaint = "%s has no fields; in particular not '%s'."%(lhs_type, field)
		problem = [Annotation(fr, complaint)]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def no_telepathy_allowed(self, env:Frame, fr:syntax.FieldReference, lhs_type):
		intro = "You cannot read the private state of actor %s."%lhs_type
		problem = [Annotation(fr)]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def record_lacks_field(self, env:Frame, fr:syntax.FieldReference, lhs_type):
		field = fr.field_name.text
		intro = "Type-checking found an unsuitable source for field '%s' access."%field
		complaint = "Type '%s' has fields, but not one called '%s'."%(lhs_type, field)
		problem = [Annotation(fr, complaint)]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def ill_founded_function(self, env:Frame, sub:syntax.Subroutine):
		intro = "This definition turned up circular, as in a=a."
		problem = [Annotation(sub, "This one.")]
		self.issue(Pic(intro, trace_stack(env)+problem))

	def no_applicable_method(self, env:Frame, actual_types):
		intro = "A type-directed operation goes off the rails. Here's how:"
		footer = [
			"This operator has no method for "+str(tuple(actual_types))+".",
			"If these are the types you mean to operate on,",
			"then please define the operator for these types.",
		]
		self.issue(Pic(intro, trace_stack(env), footer))

	def bogus_operator_arity(self, udf):
		intro = "Define most operators for two arguments. Negation (-) can also be defined for only one."
		problem = [Annotation(udf, "This one.")]
		self.issue(Pic(intro, problem))

	# Some things for just in case:

	def drat(self, env:Frame, hint):
		intro = "This code hits an unfinished part of the type-checker."
		python_frames = map(str.rstrip, format_stack(limit=8)[:-1])
		footer = [
			"",
			"Recent Python frames:",
			*python_frames,
			"",
			"Hint: "+str(hint),
		]
		self.issue(Pic(intro, trace_stack(env), footer))
		self.complain_to_console()
		# import os
		# os._exit(9)
		raise AssertionError(hint)

class Annotation:
	path: Path
	slice: slice
	caption: str
	def __init__(self, node:Phrase, caption:str=""):
		span = lookup_span(*node.span())
		self.path = span.path
		self.slice = span.slice
		self.caption = caption
	def illustrate(self):
		source = _fetch(self.path)
		row, col = source.find_row_col(self.slice.start)
		single_line = source.line_of_text(row)
		width = self.slice.stop - self.slice.start
		return illustration(single_line, col, width, prefix='% 6d |' % row, caption=self.caption)

class Tracer:
	def __init__(self):
		self.trace = []
	def called_from(self, pc:Phrase):
		self.trace.append(Annotation(pc))
	def hit_bottom(self):
		pass
	def trace_frame(self, breadcrumb, bindings):
		args = {
			k:v for k,v in bindings.items()
			if isinstance(k, (syntax.FormalParameter, syntax.Subject))
		}
		if args:
			bind_text = ', '.join("%s:%s" % (p.nom.text, t) for p, t in args.items())
			self.trace.append(Annotation(breadcrumb, bind_text))

		

def trace_stack(frame:Frame) -> list[Annotation]:
	tracer = Tracer()
	frame.trace(tracer)
	return tracer.trace

class Pic:
	def __init__(self, intro:str, anns:list[Annotation], footer=()):
		self._intro, self._anns, self._footer = intro, anns, footer
	def also(self, node, caption:str=""): self._anns.append(Annotation(node, caption))
	def as_text(self):
		# Hey! This has precisely the algorithm it does so that stack traces make sense!
		lines = [self._intro, ""]
		path = None
		for ann in self._anns:
			if ann.path != path:
				path = ann.path
				lines.append(str(path))
			lines.append(ann.illustrate())
		lines.extend(self._footer)
		return '\n'.join(lines)

@lru_cache(5)
def _fetch(path) -> SourceText:
	if path is None:
		return SourceText("")
	with open(path, "r", encoding="utf-8") as fh:
		return SourceText(fh.read(), filename=str(path))

def trace_absurdity(env:Frame, absurdity:syntax.Absurdity):
	intro = "Absurd thing happened:"
	problem = [Annotation(absurdity)]
	_bemoan([Pic(intro, trace_stack(env) + problem)])

def _bemoan(issues):
	""" Emit all the issues to the console. """
	if issues:
		print("*"*60, file=sys.stderr)
		print(_outburst(), file=sys.stderr)
	for i in issues:
		print("  -"*20, file=sys.stderr)
		print(i.as_text(), file=sys.stderr)
	sys.stderr.flush()
