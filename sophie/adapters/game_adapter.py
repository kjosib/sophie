"""
Native driver to bind Sophie with the graphics and sound capabilities of SDL via PyGame.

For the moment, it's just a spike.

There is a constraint, which is that the display and event loop are constrained to a single thread.
However, the clock does not seem to need to be on that same thread.
The tricky bit will be multiplexing a pygame event loop with the actor mailbox.

I think the concept is one thread will initialize the display and then enter an event loop.
That loop will route pygame events into the Sophie queue as messages to whatever configured procedure.
Probably nine times in ten, the configured procedure will in fact be a bound message connected to some actor.

It appears to be safe to run the clock on the same thread as the event queue,
on account of we're unlikely to overflow that queue in the time between clock ticks.
I'm unhappy with PyGame's native approach of emitting an event every N milliseconds,
because N must be integer and the interesting display rates are not compatible with that.

It also appears that, once initialized, you can operate the display from a different thread.
Right now PyGame appears to hold the GIL more than it might, but this is far from relevant.

"""
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import sys, pygame
from typing import Optional
from pygame import gfxdraw

from ..runtime import iterate_list, force, Message, Action
from ..scheduler import NativeObjectProxy, MAIN_QUEUE

linkage = {}

def sophie_init(rect, mouse_event, button_event, key_event):
	linkage['rect'] = rect
	linkage['mouse_event'] = mouse_event
	linkage['button_event'] = button_event
	linkage['key_event'] = key_event
	return { 'screen': run_game, }

def run_game(env, screen):
	pygame.init()
	_size = force(screen['size'])
	size = width, height = force(_size['x']), force(_size['y'])
	display = pygame.display.set_mode(size)
	
	clock = pygame.time.Clock()
	while True:
		for event in pygame.event.get():
			# Give Sophie code a chance to update the model based on an event.
			if event.type == pygame.QUIT:
				sys.exit()
		
		clock.tick(40)  # frames per second, I think.
		# Send Sophie code a clock event; update the model.
		
		# Use updated model to compute a new view
		
		# Display the view
		bg = force(screen['background'])
		r,g,b = force(bg['red']), force(bg['green']), force(bg['blue'])
		display.fill((r,g,b))
		
		pygame.display.flip()

def rect(x,y):
	return linkage['rect'].apply([x,y], None)

def mouse_event(e):
	args = [rect(*e.pos), rect(*e.rel), e.buttons[0], e.buttons[1], e.buttons[2], e.touch, ]
	return linkage['mouse_event'].apply(args, None)

def button_event(e):
	args = [rect(*e.pos), e.button, e.touch]
	return linkage['button_event'].apply(args, None)

def key_event(e):
	args = [e.unicode, e.key, e.mod, e.scancode]
	return linkage['key_event'].apply(args, None)

class GameLoop:
	"""
	I think I'd like to try exposing a game loop as a system-defined actor similar in spirit to the console.
	In concept you'd configure behavior by sending this messages.
	A distinguished "play" message starts an event-loop on a dedicated thread.
	
	For now I'll stick to physical events, not logical ones like double-click or dragon-drop.
	The alt-F4 quit-key combination comes across as a quit event, though.
	"""
	def __init__(self):
		self._on_quit:Optional[Action] = None
		self._on_mouse:Optional[Message] = None
		self._on_button_down:Optional[Message] = None
		self._on_button_up:Optional[Message] = None
		self._on_key_down:Optional[Message] = None
		self._on_key_up:Optional[Message] = None
		self._on_tick:Optional[Message] = None
	pass
	
	def on_quit(self, action:Action): self._on_quit = action
	def on_mouse(self, message:Message): self._on_mouse = message
	def on_button_down(self, message:Message): self._on_button_down = message
	def on_button_up(self, message:Message): self._on_button_up = message
	def on_key_down(self, message:Message): self._on_key_down = message
	def on_key_up(self, message:Message): self._on_key_up = message
	def on_tick(self, message:Message): self._on_tick = message

	def play(self, size, fps):
		pygame.init()
		width, height = force(size['x']), force(size['y'])
		display = pygame.display.set_mode((width, height))
		display_actor = NativeObjectProxy(DisplayProxy(display))

		clock = pygame.time.Clock()
		while True:
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					if self._on_quit is not None:
						self._on_quit.perform()
					return
				elif event.type == pygame.MOUSEMOTION and self._on_mouse is not None:
					self._on_mouse.dispatch_with(mouse_event(event))
				elif event.type == pygame.MOUSEBUTTONDOWN and self._on_button_down is not None:
					self._on_button_down.dispatch_with(button_event(event))
				elif event.type == pygame.MOUSEBUTTONUP and self._on_button_down is not None:
					self._on_button_up.dispatch_with(button_event(event))
				elif event.type == pygame.KEYDOWN and self._on_key_down is not None:
					self._on_key_down.dispatch_with(key_event(event))
				elif event.type == pygame.KEYUP and self._on_key_up is not None:
					self._on_key_up.dispatch_with(key_event(event))

			clock.tick(fps)
			if self._on_tick is not None:
				self._on_tick.dispatch_with(display_actor)
		pass
		

class DisplayProxy:
	
	def __init__(self, display):
		self._display = display
	
	def draw(self, pic):
		for step in iterate_list(pic):
			tag = step.pop("")
			getattr(self, "_"+tag)(*map(force, step.values()))
		pygame.display.flip()
	
	def _fill(self, color):
		r,g,b = force(color["red"]), force(color["green"]), force(color["blue"])
		self._display.fill((r,g,b))
	
	def _hlin(self, x1, x2, y, color):
		r, g, b = force(color["red"]), force(color["green"]), force(color["blue"])
		gfxdraw.hline(self._display, force(x1), force(x2), force(y), (r,g,b))
		
	def _vlin(self, x, y1, y2, color):
		r, g, b = force(color["red"]), force(color["green"]), force(color["blue"])
		gfxdraw.vline(self._display, force(x), force(y1), force(y2), (r,g,b))
		

events = NativeObjectProxy(GameLoop())
events.TASK_QUEUE = MAIN_QUEUE.main_thread

