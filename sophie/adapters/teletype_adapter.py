import sys

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

def run_app(force, app):
	while True:
		tag = app[""]
		if tag == 'done': return
		elif tag == 'echo':
			emit(force, force(app['text']))
			app = app['next']
		elif tag == 'read':
			raise NotImplementedError
		elif tag == 'random':
			raise NotImplementedError

def emit(force, text):
	while text is not NIL:
		sys.stdout.write(force(text['head']))
		text = force(text['tail'])
	sys.stdout.flush()
	
