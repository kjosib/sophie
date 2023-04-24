def _init():
	from pathlib import Path
	from . import front_end, diagnostics, primitive, resolution
	preamble_path = Path(__file__).parent/"preamble.sg"
	report = diagnostics.Report()
	report.set_path(preamble_path)
	module = front_end.parse_file(preamble_path, report)
	report.assert_no_issues()
	resolution.resolve_words(module, primitive.root_namespace, report)
	report.assert_no_issues()
	resolution.AliasChecker(module, report)
	report.assert_no_issues()
	resolution.check_all_match_expressions(module, report)
	report.assert_no_issues()
	primitive.LIST = module.globals['list']
	return module

def do_turtle_graphics(force, NIL, drawing):
	import turtle, tkinter
	root = tkinter.Tk()
	root.focus_force()
	root.title("Sophie: Turtle Graphics")
	screen = tkinter.Canvas(root, width=1000, height=1000)
	screen.pack()
	t = turtle.RawTurtle(screen)
	t.hideturtle()
	t.speed(0)
	t.screen.tracer(2^31)
	t.screen.delay(0)
	t.setheading(90)
	stepCount = 0
	steps = force(drawing["steps"])
	while steps is not NIL:
		stepCount += 1
		s = force(steps['head'])
		steps = force(steps['tail'])
		args = dict(s)  # Make a copy because of (deliberate) aliasing.
		tag = args.pop("")
		fn = getattr(t, tag)
		fn(*map(force, args.values()))  # Insertion-order is assured.
	t.screen.update()
	text = str(stepCount)+" turtle steps. Click the drawing or press any key to dismiss it."
	print(text)
	label = tkinter.Label(root, text=text)
	label.pack()
	root.bind("<ButtonRelease>", lambda event: root.destroy())
	root.bind("<KeyPress>", lambda event: root.destroy())
	tkinter.mainloop()

module = _init()
