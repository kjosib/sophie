import sys
import random
from ..runtime import iterate_list, force, Message
from ..scheduler import NativeObjectProxy, MAIN_QUEUE

NIL : dict

def sophie_init():
	return {
		'done':run_app,
		'echo':run_app,
		'read':run_app,
		'random':run_app,
	}

def run_app(env, app):
	while True:
		tag = app[""]
		if tag == 'done': return
		elif tag == 'echo':
			for fragment in iterate_list(app['text']):
				sys.stdout.write(fragment)
			sys.stdout.flush()
			app = force(app['next'])
		elif tag == 'read':
			proc = force(app['next'])
			app = force(proc.apply([input()]))
		elif tag == 'random':
			proc = force(app['next'])
			app = force(proc.apply([random.random()]))
	
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

console = NativeObjectProxy(Console())

