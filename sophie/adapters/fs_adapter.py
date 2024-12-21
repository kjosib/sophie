from ..tree_walker.values import ParametricMessage
from ..tree_walker.runtime import as_sophie_list
from ..tree_walker.scheduler import NativeObjectProxy

class FileSystem:
	@staticmethod
	def read_lines(path, target:ParametricMessage):
		with open(path, "r") as fh: lines = list(fh)
		target.dispatch_with(as_sophie_list(lines))
	
	@staticmethod
	def read_file(path, target:ParametricMessage):
		with open(path, "r") as fh: text = fh.read()
		target.dispatch_with(text)

filesystem = NativeObjectProxy(FileSystem(), pin=False)

