import sys
import random
from ..runtime import iterate_list, Message
from ..scheduler import NativeObjectProxy

NIL : dict

class Console:
	@staticmethod
	def echo(text):
		for fragment in iterate_list(text):
			sys.stdout.write(fragment)
		sys.stdout.flush()

	@staticmethod
	def read(target:Message):
		target.dispatch_with(input())

	@staticmethod
	def random(target:Message):
		target.dispatch_with(random.random())

console = NativeObjectProxy(Console(), pin=False)

