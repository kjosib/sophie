import sys
import random
from ..runtime import iterate_list, force, Procedure, AsyncTask
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
	def read(target:Procedure):
		print(target)
		message = target.apply([input()])
		# FIXME: In principle, the target could be a bound-method,
		#  in which case the "message" here would be for sure a MessageAction
		#  instead of a thunk to an action. In such cases, it might be worth
		#  delivering such a message directly rather than sending it around
		#  the mulberry bush to get trivially forced.
		MAIN_QUEUE.insert_task(AsyncTask(message))

	@staticmethod
	def random(target:Procedure):
		message = target.apply([random.random()])
		# FIXME: Same issue as above.
		MAIN_QUEUE.insert_task(AsyncTask(message))

console = NativeObjectProxy(Console())

