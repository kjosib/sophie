import sys
import random
from ..runtime import iterate_list, force

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
			app = force(proc.apply(env, [input()]))
		elif tag == 'random':
			proc = force(app['next'])
			app = force(proc.apply(env, [random.random()]))
	
	
