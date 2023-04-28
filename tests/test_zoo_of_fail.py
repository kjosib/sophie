from pathlib import Path
import unittest
from unittest import mock

from sophie.front_end import parse_file
from sophie import syntax, diagnostics, modularity, resolution

REPORT = diagnostics.Report()

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_fail = base_folder/"zoo/fail"
zoo_ok = base_folder/"zoo/ok"

def _parse(folder, basename):
	REPORT.reset()
	path = zoo_fail/folder/(basename+".sg")
	assert path.exists(), path
	REPORT.set_path(path)
	REPORT.complain_to_console = mock.Mock()
	with mock.patch("boozetools.macroparse.runtime.print", lambda *x, file=None: None):
		sut = parse_file(path, REPORT)
		assert 0 == REPORT.complain_to_console.call_count
	if sut is None:
		assert REPORT.issues
	else:
		REPORT.assert_no_issues()
		assert isinstance(sut, syntax.Module), (basename, sut)
	return sut
	

class ZooOfFail(unittest.TestCase):
	""" Tests that assert about failure modes. """
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.loader = modularity.Loader(REPORT, verbose=True, experimental=True)
	
	def expect(self, what, cases):
		for basename in cases:
			with self.subTest(basename):
				sut = _parse(what, basename)
				outer = self.loader._preamble.globals
				result = self.loader._prepare_module(sut, outer)
				self.assertEqual(what, result)
	
	def test_00_syntax_error(self):
		self.expect("parse", (
			"syntax_error",
			"mismatched_where",
		))

	def test_01_define(self):
		self.expect("define", [
			"defined_twice",
			"generic_opaque",
		])
	
	def test_02_resolve(self):
		self.expect("resolve", [
			"bad_type_alias",
			"bad_typecase_name",
			"bogus_type_alias",
			"undefined_symbol",
		])
	
	def test_03_alias(self):
		self.expect("alias", [
			"alias_as_nominal_parameter",
			"alias_as_structural_component",
			"alias_circular_mutually",
			"alias_circular_trivially",
			"alias_subtype",
			"alias_switcheroo",
			"function_as_manifest_type",
			"parameter_as_generic",
			"parameter_to_opaque",
		])
	
	def test_04_constructors(self):
		self.expect("constructors", [
			"construct_variant",
			"instantiate_opaque",
			"instantiate_variant",
			"instantiate_variant_indirect",
		])
	
	def test_05_match_check(self):
		self.expect("match_check", [
			"not_exhaustive",
			"confused",
			"bad_else",
			"duplicate_case",
		])
	
	def test_06_type_check(self):
		self.expect("type_check", [
			"mismatched_case_when",
			"num_plus_string",
			"wrong_arity",
		])
	
	
	def test_07_import(self):
		for basename in ["missing_import", "broken_import", "circular_import"]:
			with self.subTest(basename):
				# Given
				report = diagnostics.Report()
				loader = modularity.Loader(report, verbose=False)
				# When
				module = loader.need_module(zoo_fail/"import", basename + ".sg")
				# Then
				assert type(module) is syntax.Module
				assert report.issues
	



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
