import sys
import random
from ..tree_walker.values import ParametricMessage
from ..tree_walker.runtime import iterate_list
from ..tree_walker.scheduler import NativeObjectProxy

class Console:
	@staticmethod
	def echo(text):
		for fragment in iterate_list(text):
			sys.stdout.write(fragment)
		sys.stdout.flush()

	@staticmethod
	def read(target:ParametricMessage):
		target.dispatch_with(input())

	@staticmethod
	def random(target:ParametricMessage):
		target.dispatch_with(random.random())

console = NativeObjectProxy(Console(), pin=False)

