from pathlib import Path
import unittest
from unittest import mock

from sophie.front_end import parse_file
from sophie.resolution import resolve_words, AliasChecker, check_all_match_expressions
from sophie import syntax, primitive, diagnostics, modularity

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_fail = base_folder/"zoo/fail"
zoo_ok = base_folder/"zoo/ok"


def _expect_issue(report, reason=""):
	assert any(reason in issue.description for issue in report.issues), reason

def _parse(basename, report):
	path = zoo_fail/(basename+".sg")
	report.set_path(str(path))
	return parse_file(path, report)

def _should_not_parse(basename, reason=""):
	"""Syntax error should register with the report, but not dump to console; that's a different responsibility."""
	report = diagnostics.Report()
	report.complain_to_console = mock.Mock()
	with mock.patch("boozetools.macroparse.runtime.print", lambda *x,file=None:None):
		assert _parse("parse/"+basename, report) is None
	_expect_issue(report, reason)
	assert 0 == report.complain_to_console.call_count

class ZooOfFail(unittest.TestCase):
	""" Tests that assert about failure modes. """
	
	def test_00_syntax_error(self):
		_should_not_parse("syntax_error")

	def test_01_mismatched_where(self):
		_should_not_parse("mismatched_where", "Mismatched")
		
	def test_02_should_not_resolve(self):
		for basename in (
				"undefined_symbol",
				"bad_typecase_name",
				"construct_variant",
				"defined_twice",
				"generic_opaque",
		):
			with self.subTest(basename):
				report = diagnostics.Report()
				sut = _parse("resolve/" + basename, report)
				assert isinstance(sut, syntax.Module), (basename, sut)
				report.assert_no_issues()
				resolve_words(sut, primitive.root_namespace, report)
				_expect_issue(report)
	
	def test_03_bad_type_aliasing(self):
		for basename in (
			"alias_as_nominal_parameter",
			"alias_as_structural_component",
			"alias_circular_mutually",
			"alias_circular_trivially",
			"alias_subtype",
			"alias_switcheroo",
			"function_as_manifest_type",
			"parameter_as_generic",
			"parameter_to_opaque",
		):
			with self.subTest(basename):
				report = diagnostics.Report()
				sut = _parse("type_alias/"+basename, report)
				assert isinstance(sut, syntax.Module), (basename, sut)
				report.assert_no_issues()
				resolve_words(sut, primitive.root_namespace, report)
				report.assert_no_issues()
				AliasChecker(sut, report)
				_expect_issue(report)
		
	def test_04_bad_type_cases(self):
		for basename in (
			"not_exhaustive",
			"confused",
			"bad_else",
		):
			with self.subTest(basename):
				report = diagnostics.Report()
				sut = _parse("type_case_match/"+basename, report)
				assert isinstance(sut, syntax.Module), (basename, sut)
				report.assert_no_issues()
				resolve_words(sut, primitive.root_namespace, report)
				report.assert_no_issues()
				AliasChecker(sut, report)
				report.assert_no_issues()
				check_all_match_expressions(sut, report)
				_expect_issue(report)

	def test_05_module_breakage(self):
		for bogon in ["missing_import", "broken_import", "circular_import"]:
			with self.subTest(bogon):
				# Given
				report = diagnostics.Report()
				loader = modularity.Loader(report, verbose=False)
				# When
				module = loader.need_module(zoo_fail/"import", bogon + ".sg")
				# Then
				assert type(module) is syntax.Module
				_expect_issue(report)
	
# def test_02_does_not_type(self):
# 	for fn in ("num_plus_string", "wrong_arity", "mismatched-case-when", "omega"):
# 		with self.subTest(fn):
# 			# Given
# 			report = diagnostics.Report()
# 			sut = parse_file(zoo_fail/(fn+".sg"), report)
# 			assert not report.issues
# 			resolve_words(sut, static_root, report)
# 			assert not report.issues
# 			manifest.type_module(sut, report)
# 			assert not report.issues
# 			# When
# 			type_inference.infer_types(sut, report)
# 			# Then
# 			assert len(report.issues)

# class ThingsThatShouldConverge(unittest.TestCase):
# 	""" These assert that things which should converge, do. For the contrapositive, see the ZooOfFail. """
#
# 	def setUp(self) -> None:
# 		algebra.TypeVariable._counter = 0
# 		self.report = diagnostics.Report()
#
# 	def load(self, folder, which):
# 		report = self.report
# 		loader = modularity.Loader(report, verbose=False)
# 		module = loader.need_module(folder, which + ".sg")
# 		if report.issues:
# 			report.complain_to_console()
# 			assert False
# 		else:
# 			type_inference.infer_types(module, self.report, verbose=True)
# 			return module
#
# 	def test_Newton(self):
# 		module = self.load(example_folder, "Newton")
# 		assert not self.report.issues, self.report.complain_to_console()
# 		assert_convergent(module.globals['iterate_four_times'])
# 		root = module.globals['root']
# 		assert_convergent(root)
# 		assert isinstance(root.typ, algebra.Arrow)
# 		arg = root.typ.arg
# 		assert isinstance(arg, algebra.Product)
# 		assert len(arg.fields) == 1
# 		a0 = arg.fields[0]
# 		assert isinstance(a0, algebra.Nominal)
# 		assert a0.dfn is primitive.literal_number.dfn
#
# 	def test_bipartite(self):
# 		module = self.load(zoo_ok, "bipartite_list")
# 		assert not self.report.issues, self.report.complain_to_console()
# 		cmap = module.globals['cmap']
# 		assert_convergent(cmap)
# 		assert isinstance(cmap.typ, algebra.Arrow)
# 		res = cmap.typ.res
# 		assert isinstance(res, algebra.Nominal)
# 		assert res.dfn.nom.text == "critter"
# 		assert res.params[0] != res.params[1]
#
# 	def test_recur(self):
# 		""" (number, number) -> list[<a>] is the wrong type for a recurrence relation. """
# 		module = self.load(zoo_ok, "recur")
# 		assert not self.report.issues, self.report.complain_to_console()
# 		assert_convergent(module.globals['recur'])
#
# 	def test_sequence(self):
# 		""" Structural recursion should do the right thing. """
# 		module = self.load(zoo_ok, "sequence")
# 		assert not self.report.issues, self.report.complain_to_console()
# 		assert_convergent(module.globals['m1'])
# 		assert_convergent(module.globals['m2'])
#
#
# def assert_convergent(sym):
# 	# Maybe a function's type is "convergent" when it has no free variables in the result.
# 	# In other words, all the type-variables in the result appear somewhere in a binding context:
# 	# either its own parameters, or those of its parent functions.
# 	assert isinstance(sym, syntax.Function)
# 	typ = sym.typ
# 	assert isinstance(typ, algebra.Arrow), typ
# 	arg = set()
# 	typ.arg.poll(arg)
#
# 	res = set()
# 	typ.res.poll(res)
#
# 	free = res - arg
#
# 	assert not free, (typ.visit(algebra.Render()), free)

if __name__ == '__main__':
	unittest.main()
