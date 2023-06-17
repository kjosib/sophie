from pathlib import Path
import unittest
from unittest import mock

from sophie.front_end import parse_file
from sophie import syntax, diagnostics, modularity, resolution

REPORT = diagnostics.Report(verbose=True)

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_fail = base_folder/"zoo/fail"

def _parse(path):
	REPORT.reset()
	assert path.exists(), path
	REPORT.set_path(path)
	REPORT.complain_to_console = mock.Mock()
	with mock.patch("boozetools.macroparse.runtime.print", lambda *x, file=None: None):
		sut = parse_file(path, REPORT)
		assert 0 == REPORT.complain_to_console.call_count
	if sut is None:
		assert REPORT.sick()
	else:
		REPORT.assert_no_issues()
		assert isinstance(sut, syntax.Module), sut
	return sut
	

class ZooOfFail(unittest.TestCase):
	""" Tests that assert about failure modes. """
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.loader = modularity.Loader(REPORT, experimental=True)
	
	def expect(self, folder, cases):
		for basename in cases:
			with self.subTest(basename):
				path = zoo_fail / folder / (basename + ".sg")
				sut = _parse(path)
				self.loader._enter(path)
				phase_at_failure = self.loader._prepare_module(sut, self.loader._preamble.globals)
				self.loader._exit()
				self.assertEqual(folder, phase_at_failure)
	
	def test_00_syntax_error(self):
		self.expect("parse", (
			"syntax_error",
			"mismatched_where",
			"generic_opaque",
		))

	def test_01_define(self):
		self.expect("define", [
			"defined_twice",
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
			"circular_function_mutually",
			"circular_function_trivially",
			"has_no_fields",
			"lacks_field",
			"mismatched_case_when",
			"num_plus_string",
			"omega",
			"wrong_arity",
		])
	
	
	def test_07_import(self):
		for basename in [
			"circular_import",
			"missing_import",
			"broken_import",
		]:
			with self.subTest(basename):
				# Given
				report = diagnostics.Report(verbose=False)
				loader = modularity.Loader(report)
				# When
				module = loader.need_module(zoo_fail/"import"/ (basename + ".sg"))
				# Then
				assert type(module) is syntax.Module
				assert report.sick()
	


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
