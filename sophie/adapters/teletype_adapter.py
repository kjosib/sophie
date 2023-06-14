import sys
import random

NIL : dict

def sophie_init(force, nil):
	global NIL
	NIL = force(nil)
	return {
		'done':run_app,
		'echo':run_app,
		'read':run_app,
		'random':run_app,
	}

def run_app(force, env, app):
	while True:
		tag = app[""]
		if tag == 'done': return
		elif tag == 'echo':
			emit(force, force(app['text']))
			app = force(app['next'])
		elif tag == 'read':
			proc = force(app['next'])
			app = force(proc.apply(env, [input()]))
		elif tag == 'random':
			proc = force(app['next'])
			app = force(proc.apply(env, [random.random()]))

def emit(force, text):
	while text is not NIL:
		sys.stdout.write(force(text['head']))
		text = force(text['tail'])
	sys.stdout.flush()
	
