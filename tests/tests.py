from pathlib import Path
import unittest
from unittest import mock

from sophie.front_end import parse_file, parse_text
from sophie.resolution import resolve_words
from sophie.preamble import static_root
from sophie import syntax, primitive, simple_evaluator, manifest, diagnostics, algebra, type_inference, modularity

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_fail = base_folder/"zoo/fail"
zoo_ok = base_folder/"zoo/ok"

def _load_good_example(which) -> list[syntax.Module]:
	report = diagnostics.Report()
	loader = modularity.Loader(static_root, report, verbosity=0)
	loader.need_module(example_folder, which+".sg")
	if report.issues:
		report.complain_to_console()
		assert False
	else:
		return loader.module_sequence

class ExampleSmokeTests(unittest.TestCase):
	""" Run all the examples; Test for no smoke. """
	
	def test_other_examples(self):
		for name in ["hello_world", "some_arithmetic", "primes", "Newton", "patron"]:
			with self.subTest(name=name):
				each_module = _load_good_example(name)
				simple_evaluator.run_program(each_module)
	
	def test_alias(self):
		each_module = _load_good_example("alias")
		self.assertIsInstance(each_module[-1].globals["album_tree"].body, syntax.TypeCall)
		self.assertEqual(7, simple_evaluator.run_program(each_module))
	
	def test_turtle_compiles(self):
		_load_good_example("turtle")

class ZooOfFail(unittest.TestCase):
	""" Tests that assert about failure modes. """
	
	def test_mismatched_where(self):
		report = diagnostics.Report()
		parse_file(zoo_fail/"mismatched_where.sg", report)
		self.assertIn("Mismatched", report.issues[0].description)
		
		
	def test_defined_twice(self):
		report = diagnostics.Report()
		module = parse_file(zoo_fail/"defined_twice.sg", report)
		assert not report.issues
		resolve_words(module, static_root, report)
		assert len(report.issues)

	@mock.patch("boozetools.macroparse.runtime.print", lambda *x,file=None:None)
	def test_syntax_error(self):
		report = diagnostics.Report()
		report.complain_to_console = mock.Mock()
		parse_file(zoo_fail/"syntax_error.sg", report)
		assert len(report.issues)
		self.assertEqual(report.complain_to_console.call_count, 0)

	def test_00_unresolved_names(self):
		for fn in ("undefined_symbol", "bad_typecase_name", "construct_variant", ):
			with self.subTest(fn):
				report = diagnostics.Report()
				sut = parse_file(zoo_fail/(fn+".sg"), report)
				assert not report.issues
				resolve_words(sut, static_root, report)
				assert len(report.issues)
				
	def test_01_well_founded(self):
		for bogon in [
			"define: bogus(arg:yes) = arg; end.",  # "yes" is not a type.
			"type: a is a; end.",
			"type: a is b; b is a; end.",
			"type: a is list[a]; end.",
			# "type: a[x] is x; end.",  # Strange, but not strictly erroneous.
			"type: a[x] is x[a]; end.",  # This definitely is.
			"type: a[x] is x[list]; end.",  # This would imply second-order types, which .. no. Not now, anyway.
			"define: i = i; end.",
			"define: i = 1 + i; end.",
			"define: i = j; j=k; k=i; end.",
			"type: L is list[number]; begin: L; end.",
			"begin: number; end.",
		]:
			with self.subTest(bogon):
				report = diagnostics.Report()
				module = parse_text(bogon, __file__, report)
				assert not report.issues
				resolve_words(module, static_root, report)
				assert len(report.issues)
		
	def test_02_does_not_type(self):
		for fn in ("num_plus_string", "wrong_arity", "mismatched-case-when", "omega"):
			with self.subTest(fn):
				# Given
				report = diagnostics.Report()
				sut = parse_file(zoo_fail/(fn+".sg"), report)
				assert not report.issues
				resolve_words(sut, static_root, report)
				assert not report.issues
				manifest.type_module(sut, report)
				assert not report.issues
				# When
				type_inference.infer_types(sut, report)
				# Then
				assert len(report.issues)
	
	def test_03_module_breakage(self):
		for bogon in ["missing_import", "broken_import", "circular_import"]:
			with self.subTest(bogon):
				# Given
				report = diagnostics.Report()
				loader = modularity.Loader(static_root, report, verbosity=0)
				# When
				module = loader.need_module(zoo_fail, bogon + ".sg")
				# Then
				assert len(report.issues)
				assert type(module) is syntax.Module

class ThingsThatShouldConverge(unittest.TestCase):
	""" These assert that things which should converge, do. For the contrapositive, see the ZooOfFail. """
	
	def setUp(self) -> None:
		algebra.TypeVariable._counter = 0
		self.report = diagnostics.Report()
	
	def load(self, folder, which):
		report = self.report
		loader = modularity.Loader(static_root, report, verbosity=0)
		module = loader.need_module(folder, which + ".sg")
		if report.issues:
			report.complain_to_console()
			assert False
		else:
			type_inference.infer_types(module, self.report, verbose=True)
			return module
	
	def test_Newton(self):
		module = self.load(example_folder, "Newton")
		assert not self.report.issues, self.report.complain_to_console()
		assert_convergent(module.globals['iterate_four_times'])
		root = module.globals['root']
		assert_convergent(root)
		assert isinstance(root.typ, algebra.Arrow)
		arg = root.typ.arg
		assert isinstance(arg, algebra.Product)
		assert len(arg.fields) == 1
		a0 = arg.fields[0]
		assert isinstance(a0, algebra.Nominal)
		assert a0.dfn is primitive.literal_number.dfn
	
	def test_bipartite(self):
		module = self.load(zoo_ok, "bipartite_list")
		assert not self.report.issues, self.report.complain_to_console()
		cmap = module.globals['cmap']
		assert_convergent(cmap)
		assert isinstance(cmap.typ, algebra.Arrow)
		res = cmap.typ.res
		assert isinstance(res, algebra.Nominal)
		assert res.dfn.nom.text == "critter"
		assert res.params[0] != res.params[1]
	
	def test_recur(self):
		""" (number, number) -> list[<a>] is the wrong type for a recurrence relation. """
		module = self.load(zoo_ok, "recur")
		assert not self.report.issues, self.report.complain_to_console()
		assert_convergent(module.globals['recur'])

def assert_convergent(sym):
	# Maybe a function's type is "convergent" when it has no free variables in the result.
	# In other words, all the type-variables in the result appear somewhere in a binding context:
	# either its own parameters, or those of its parent functions.
	assert isinstance(sym, syntax.Function)
	typ = sym.typ
	assert isinstance(typ, algebra.Arrow), typ
	arg = set()
	typ.arg.poll(arg)
	
	res = set()
	typ.res.poll(res)
	
	free = res - arg
	
	assert not free, (typ.visit(algebra.Render()), free)

if __name__ == '__main__':
	unittest.main()
