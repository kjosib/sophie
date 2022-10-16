from pathlib import Path
import unittest
from sophie.compiler import main
from sophie import forms

example_folder = Path(__file__).parent.parent/"examples"

class ExampleSmokeTests(unittest.TestCase):
	"""
	Super-simple tests that
	"""
	def test_alias(self):
		sut = main(example_folder / "alias.sg")
		assert isinstance(sut, forms.Module)
		assert sut.types
	
	def test_primes(self):
		sut = main(example_folder/"primes.sg")
		assert isinstance(sut, forms.Module)
		assert sut.functions

if __name__ == '__main__':
	unittest.main()
