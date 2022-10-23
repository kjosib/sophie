from pathlib import Path
import unittest
from unittest import mock

from sophie.compiler import parse_file
from sophie import syntax, simple_evaluator

base_folder = Path(__file__).parent.parent
example_folder = base_folder/"examples"
zoo_folder = base_folder/"zoo_of_fail"

class ExampleSmokeTests(unittest.TestCase):
	""" Super-simple tests that test for no smoke. """
	def test_alias(self):
		sut = parse_file(example_folder / "alias.sg")
		assert isinstance(sut, syntax.Module)
		assert isinstance(sut.namespace["album_tree"], syntax.TypeDecl)
		self.assertEqual(7, simple_evaluator.run_module(sut))
		
	
	def test_primes(self):
		sut = parse_file(example_folder / "primes.sg")
		assert isinstance(sut, syntax.Module)
		primes = simple_evaluator.run_module(sut)
		print(primes)


class ZooOfFailTests(unittest.TestCase):
	""" Tests that assert about failure modes. """
	
	@mock.patch("boozetools.support.failureprone.SourceText.complain")
	def test_mismatched_where(self, complain):
		self.assertIsNone(parse_file(zoo_folder/"mismatched_where.sg"))
		self.assertEqual(complain.call_count, 1)

	@mock.patch("boozetools.macroparse.runtime.print", lambda *x,file=None:None)
	@mock.patch("boozetools.support.failureprone.SourceText.complain")
	def test_syntax_error(self, complain):
		self.assertIsNone(parse_file(zoo_folder/"syntax_error.sg"))
		self.assertEqual(complain.call_count, 1)

if __name__ == '__main__':
	unittest.main()
