from pathlib import Path
import unittest
from unittest import mock

from sophie.diagnostics import Report
from sophie.resolution import RoadMap, Yuck
from sophie.static.check import TypeChecker

class Silence(Report):
	def __init__(self):
		super().__init__(verbose=False, max_issues=30)
		self.complain_to_console = mock.Mock()
	pass

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_fail = base_folder/"zoo/fail"

def _identify_problem(folder:Path, filename:str):
	specimen_path = folder / filename
	assert specimen_path.exists(), specimen_path
	report = Silence()
	try:
		roadmap = RoadMap(specimen_path, report)
	except Yuck as ex:
		assert 0 == report.complain_to_console.call_count
		assert report.sick()
		return ex.args[0]
	else:
		report.assert_no_issues("Roadmap generated errors, but failed to fail properly.")
		TypeChecker(report).check_program(roadmap)
		if report.sick(): return "type_check"
		else: return "failed to fail"

class ZooOfFail(unittest.TestCase):
	""" Tests that assert about failure modes. """

	def expect(self, folder, cases):
		for basename in cases:
			with self.subTest(basename):
				self.assertEqual(folder, _identify_problem(zoo_fail / folder, basename + ".sg"))

	def test_00_syntax_error(self):
		self.expect("parse", (
			"syntax_error",
			"mismatched_where",
		))

	def test_01_resolve(self):
		self.expect("resolve", [
			"defined_twice",
			"generic_opaque",
			"bad_type_alias",
			"bad_typecase_name",
			"bogus_type_alias",
			"undefined_symbol",
			"not_exhaustive",
			"confused",
			"bad_else",
			"duplicate_case",
			"construct_variant",
			"instantiate_opaque",
			"instantiate_variant",
			"instantiate_variant_indirect",
			"alias_subtype",
			"function_as_manifest_type",
			"parameter_to_opaque",
			"alias_switcheroo",
			"parameter_as_generic",
		])
	
	def test_02_alias(self):
		self.expect("alias", [
			"alias_as_nominal_parameter",
			"alias_as_structural_component",
			"alias_circular_mutually",
			"alias_circular_trivially",
		])
	
	def test_03_type_check(self):
		self.expect("type_check", [
			"circular_function_mutually",
			"circular_function_trivially",
			"has_no_fields",
			"lacks_field",
			"mismatched_case_when",
			"mismatched_type_case",
			"num_plus_string",
			"bad_message",
			"omega",
			"undefined_comparison",
			"wrong_arity",
			"signature_violation_1",
			"assume_incorrectly",
		])
	
	def test_04_import(self):
		self.expect("import", [
			"circular_import",
			"missing_import",
		])



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
# 	def test_sequence(self):
# 		""" Structural recursion should do the right thing. """
# 		module = self.load(zoo_ok, "sequence")
# 		assert not self.report.issues, self.report.complain_to_console()
# 		assert_convergent(module.globals['m1'])
# 		assert_convergent(module.globals['m2'])
#

if __name__ == '__main__':
	unittest.main()
