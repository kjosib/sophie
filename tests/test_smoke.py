from pathlib import Path
import unittest
from sophie import executive, diagnostics, resolution, type_evaluator
from sophie.intermediate import translate

base_folder = Path(__file__).parent.parent
examples = base_folder/"examples"
zoo_ok = base_folder/"zoo/ok"


def _good(folder, which) -> resolution.RoadMap:
	report = diagnostics.Report(verbose=False)
	try:
		roadmap = resolution.RoadMap(folder / (which + ".sg"), report)
		type_evaluator.DeductionEngine(roadmap, report)
		report.assert_no_issues()
		translate(roadmap)
		return roadmap
	except resolution.Yuck as ex:
		assert report.sick()
		report.complain_to_console()
		assert False, "Test failed %s phase"%ex.args[0]

class ExampleSmokeTests(unittest.TestCase):
	""" Run all the examples; Test for no smoke. """
	
	def test_alias(self):
		""" The result of running a program is the value of its last expression. """
		roadmap = _good(examples, "tutorial/alias")
		result = executive.run_program(roadmap)
		self.assertEqual(7, result)
	
	def test_turtle_examples_compile(self):
		for name in ["turtle", "color_spiral", "simple_designs"]:
			with self.subTest(name):
				_good(examples, "turtle/"+name)

	def test_game_examples_compile(self):
		for name in ["guess_the_number", "99 bottles", "mouse_print", "mouse"]:
			with self.subTest(name):
				_good(examples, "games/"+name)
		with self.subTest("Mandelbrot"):
			_good(examples, "mathematics/Mandelbrot")

	def test_other_examples(self):
		for name in [
			"hello_actors",
			"hello_world",
			"algorithm",
			"tutorial/patron",
			"tutorial/simple_calculations",
			"tutorial/explicit_list_construction",
			"mathematics/Newton",
			"mathematics/Newton_2",
			"mathematics/Newton_3",
			"tutorial/case_when",
			"tutorial/some_arithmetic",
			"mathematics/Fibonacci",
			"mathematics/primes",
			"tutorial/generic_parameter",
		]:
			with self.subTest(name):
				roadmap = _good(examples, name)
				executive.run_program(roadmap)

	def test_zoo_of_ok(self):
		for name in [
			"arrows",
		]:
			with self.subTest(name):
				roadmap = _good(zoo_ok, name)
				executive.run_program(roadmap)


if __name__ == '__main__':
	unittest.main()
