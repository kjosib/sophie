from pathlib import Path
import unittest

from sophie.diagnostics import Report
from sophie.resolution import RoadMap
from sophie.type_evaluator import DependencyPass

base_folder = Path(__file__).parent.parent
specimen_path = base_folder/"examples/hello_world.sg"

class DependencyPassTests(unittest.TestCase):
	def test_map_depends_on_both_parameters(self):
		report = Report(verbose=False)
		roadmap = RoadMap(specimen_path, report)
		report.assert_no_issues("Test is subverted.")
		sut = DependencyPass()
		sut.visit(roadmap.preamble)
		scope = roadmap.module_scopes[roadmap.preamble]
		udf = scope['map']
		self.assertSetEqual(set(udf.params), sut.depends[udf])
		
		
if __name__ == '__main__':
	unittest.main()
