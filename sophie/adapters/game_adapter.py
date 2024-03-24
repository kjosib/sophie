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
import pygame
from typing import Optional
from pygame import draw, gfxdraw

from ..runtime import iterate_list, force, Message, Action
from ..scheduler import NativeObjectProxy

linkage = {}

def sophie_init(xy, mouse_event, button_event, key_event):
	linkage['xy'] = xy
	linkage['mouse_event'] = mouse_event
	linkage['button_event'] = button_event
	linkage['key_event'] = key_event

def xy(x, y):
	return linkage['xy'].apply([x,y], None)

def mouse_event(e):
	args = [xy(*e.pos), xy(*e.rel), e.buttons[0], e.buttons[1], e.buttons[2], e.touch, ]
	return linkage['mouse_event'].apply(args, None)

def button_event(e):
	args = [xy(*e.pos), e.button, e.touch]
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
		
def _force_rgb(color):
	f = lambda field: int(force(color[field])) & 255
	return f("red"), f("green"), f("blue")

def _force_xy(xy):
	return force(xy["x"]), force(xy["y"])

class DisplayProxy:
	
	def __init__(self, display):
		self._display = display
	
	def draw(self, pic):
		for step in iterate_list(pic):
			tag = step.pop("").nom.text
			getattr(self, "_"+tag)(*map(force, step.values()))
		pygame.display.flip()
	
	def _fill(self, color):
		self._display.fill(_force_rgb(color))
	
	def _stroke(self, color, strokes):
		rgb = _force_rgb(color)
		for stroke in iterate_list(strokes):
			tag = stroke.pop("").nom.text
			getattr(self, "_stroke_"+tag)(rgb, *map(force, stroke.values()))
	
	def _stroke_line(self, color, start, stop):
		draw.line(self._display, color, _force_xy(start), _force_xy(stop))
	
	def _stroke_polyline(self, color, xys):
		draw.lines(self._display, color, False, *map(_force_xy, iterate_list(xys)))
	
	def _stroke_box(self, color, corner, measure):
		draw.rect(self._display, color, pygame.Rect(_force_xy(corner), _force_xy(measure)), width=1)
	
	def _stroke_fill_box(self, color, corner, measure):
		self._display.fill(color, pygame.Rect(_force_xy(corner), _force_xy(measure)))
	
	def _stroke_circle(self, color, center, radius):
		draw.circle(self._display, color, _force_xy(center), radius, width=1)
	
	def _stroke_ellipse(self, color, corner, measure):
		draw.ellipse(self._display, color, pygame.Rect(_force_xy(corner), _force_xy(measure)))
	
	def _stroke_arc(self, color, corner, measure, start_angle, stop_angle):
		rect = pygame.Rect(_force_xy(corner), _force_xy(measure))
		draw.arc(self._display, color, rect, start_angle, stop_angle)
	
	def _stroke_hlin(self, color, x1, x2, y):
		gfxdraw.hline(self._display, force(x1), force(x2), force(y), color)
		
	def _stroke_vlin(self, color, x, y1, y2):
		gfxdraw.vline(self._display, force(x), force(y1), force(y2), color)
		

events = NativeObjectProxy(GameLoop(), pin=True)

