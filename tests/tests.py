from pathlib import Path
import unittest
from unittest import mock
from boozetools.support.failureprone import Issue

from sophie.front_end import parse_file, parse_text, complain
from sophie.resolution import resolve_words
from sophie.preamble import static_root
from sophie.unification import infer_types, PHASE_ASSIGN
from sophie import syntax, simple_evaluator

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_folder = base_folder/"zoo_of_fail"

def _load_good_example(which) -> syntax.Module:
	module = parse_file(example_folder / (which+".sg"))
	if isinstance(module, syntax.Module):
		errors = resolve_words(module, static_root)
	else:
		assert isinstance(module, Issue)
		errors = [module]
	if not errors:
		errors = infer_types(module)
	if errors:
		complain(errors)
		assert False
	else:
		return module


class ExampleSmokeTests(unittest.TestCase):
	""" Run all the examples; Test for no smoke. """
	
	def test_other_examples(self):
		for name in ["hello_world", "some_arithmetic", "primes", "newton"]:
			with self.subTest(name=name):
				module = _load_good_example(name)
				simple_evaluator.run_module(module)
	
	def test_alias(self):
		module = _load_good_example("alias")
		self.assertIsInstance(module.namespace["album_tree"].dfn, syntax.TypeCall)
		self.assertEqual(7, simple_evaluator.run_module(module))
	
	def test_turtle_compiles(self):
		module = _load_good_example("turtle")

class ZooOfFailTests(unittest.TestCase):
	""" Tests that assert about failure modes. """
	
	def test_mismatched_where(self):
		sut = parse_file(zoo_folder/"mismatched_where.sg")
		self.assertIsInstance(sut, Issue)
		self.assertIn("Mismatched", sut.description)
		
		
	@mock.patch("boozetools.support.failureprone.SourceText.complain")
	def test_defined_twice(self, complain):
		module = parse_file(zoo_folder/"defined_twice.sg")
		self.assertEqual(complain.call_count, 0)
		errors = resolve_words(module, static_root)
		assert errors

	@mock.patch("boozetools.macroparse.runtime.print", lambda *x,file=None:None)
	@mock.patch("boozetools.support.failureprone.SourceText.complain")
	def test_syntax_error(self, complain):
		self.assertIsInstance(parse_file(zoo_folder/"syntax_error.sg"), Issue)
		self.assertEqual(complain.call_count, 0)

	def test_00_unresolved_names(self):
		for fn in ("undefined_symbol", "bad_typecase_name", ):
			with self.subTest(fn):
				sut = parse_file(zoo_folder/(fn+".sg"))
				errors = resolve_words(sut, static_root)
				self.assertTrue(errors)
				
	def test_01_things_type_assignment_should_reject(self):
		for bogon in [
			"define: bogus(arg:yes) = arg; end.",  # "yes" is not a type.
			"type: a is a; end.",
			"type: a is b; b is a; end.",
			"type: a is list[a]; end.",
			# "type: a[x] is x; end.",  # I'm not sure if this is erroneous.
			"type: a[x] is x[a]; end.",  # This definitely is.
			"type: a[x] is x[list]; end.",  # This would imply second-order types, which .. no. Not now, anyway.
		]:
			with self.subTest(bogon):
				module = parse_text(bogon, __file__)
				assert isinstance(module, syntax.Module)
				issues = resolve_words(module, static_root)
				assert not issues, "The problem should be more subtle than what name resolution can find."
				issues = infer_types(module)
				assert any(i.phase == PHASE_ASSIGN for i in issues), issues
		
	def test_02_does_not_type(self):
		for fn in ("num_plus_string", "wrong_arity"):
			with self.subTest(fn):
				# Given
				sut = parse_file(zoo_folder/(fn+".sg"))
				errors = resolve_words(sut, static_root)
				self.assertFalse(errors)
				# When
				type_errors = infer_types(sut)
				# Then
				self.assertTrue(len(type_errors))

if __name__ == '__main__':
	unittest.main()
