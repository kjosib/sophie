from pathlib import Path
import unittest
from unittest import mock

from sophie.front_end import parse_file, parse_text
from sophie.resolution import resolve_words
from sophie.preamble import static_root
from sophie import syntax, simple_evaluator, manifest, diagnostics, experimental, modularity

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_fail = base_folder/"zoo/fail"

def _load_good_example(which) -> syntax.Module:
	report = diagnostics.Report()
	loader = modularity.Loader(static_root, report, experimental=True)
	module = loader.need_module(example_folder, which+".sg")
	if report.issues:
		report.complain_to_console()
		assert False
	else:
		return module


class ExampleSmokeTests(unittest.TestCase):
	""" Run all the examples; Test for no smoke. """
	
	def test_other_examples(self):
		for name in ["hello_world", "some_arithmetic", "primes", "Newton"]:
			with self.subTest(name=name):
				module = _load_good_example(name)
				simple_evaluator.run_module(module)
	
	def test_alias(self):
		module = _load_good_example("alias")
		self.assertIsInstance(module.globals["album_tree"].body, syntax.TypeCall)
		self.assertEqual(7, simple_evaluator.run_module(module))
	
	def test_turtle_compiles(self):
		_load_good_example("turtle")

	def test_patron_compiles(self):
		""" it fails to execute at the moment, but that will soon fix. """
		_load_good_example("patron")

class ZooOfFailTests(unittest.TestCase):
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
		for fn in ("num_plus_string", "wrong_arity", "mismatched-case-when"):
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
				experimental.Experiment(sut, report.on_error("Type Checking"))
				# Then
				assert len(report.issues)
	
	def test_03_module_breakage(self):
		for bogon in ["missing_import", "broken_import", "circular_import"]:
			with self.subTest(bogon):
				# Given
				report = diagnostics.Report()
				loader = modularity.Loader(static_root, report, experimental=False)
				# When
				module = loader.need_module(zoo_fail, bogon + ".sg")
				# Then
				assert len(report.issues)
				assert type(module) is syntax.Module

class TypeInferenceTests(unittest.TestCase):
	def test_01(self):
		text = """
		type:
			A[x,y] is case: bc(h:x, t:A[y,x]); na; esac;
		define:
			biMap(fa, fb, xs) = case xs:
				na -> na;
				bc -> bc(fa(xs.h), biMap(fb, fa, xs.tail));
			esac;
		end.
		"""
		report = diagnostics.Report()
		module = parse_text(text, __file__, report)
		assert not report.issues
		resolve_words(module, static_root, report)
		assert not report.issues
		manifest.type_module(module, report)
		

if __name__ == '__main__':
	unittest.main()
