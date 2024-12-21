from ..tree_walker.runtime import force, iterate_list
from ..tree_walker.scheduler import NativeObjectProxy, MAIN_QUEUE, SimpleTask
import turtle, tkinter

def sophie_init(drawing):
	return {drawing.key:some_turtle_graphics}

def some_turtle_graphics(drawing):
	worker.accept_message("draw", (drawing))

class Worker:
	@staticmethod
	def draw(env, drawing):
		tortoise.accept_message("begin", ())
		stepCount = 0
		block = []
		for record in iterate_list(drawing["steps"]):
			stepCount += 1
			step = dict(record)  # Make a copy because of (deliberate) aliasing.
			tag = step.pop("")
			block.append((tag, *map(force, step.values())))  # Insertion-order is assured.
			if len(block) == 100:
				tortoise.accept_message("block", (block,))
				block = []
		if len(block):
			tortoise.accept_message("block", (block,))
		tortoise.accept_message("finish", (stepCount,))
			
class TurtleGraphics:
	root = None
	yertle = None
	def begin(self):
		self.root = root = tkinter.Tk()
		root.focus_force()
		root.title("Sophie: Turtle Graphics")
		screen = tkinter.Canvas(root, width=1000, height=1000)
		screen.pack()
		self.yertle = t = turtle.RawTurtle(screen)
		t.hideturtle()
		t.speed(0)
		t.screen.tracer(2 ^ 31)
		t.screen.delay(0)
		t.setheading(90)
		
	def block(self, steps):
		t = self.yertle
		for (tag, *args) in steps:
			getattr(t, tag.nom.text)(*args)
		t.screen.update()
	
	def finish(self, stepCount):
		text = str(stepCount) + " turtle steps. Click the drawing or press any key to dismiss it."
		print(text)
		root = self.root
		label = tkinter.Label(root, text=text)
		label.pack()
		root.bind("<ButtonRelease>", lambda event:root.destroy())
		root.bind("<KeyPress>", lambda event:root.destroy())
		tkinter.mainloop()

tortoise = NativeObjectProxy(TurtleGraphics(), pin=True)
worker = NativeObjectProxy(Worker())
