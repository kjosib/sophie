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
import sys, pygame
import pygame.gfxdraw
from ..runtime import iterate_list, force, Function
from ..scheduler import Actor, NativeObjectProxy, MAIN_QUEUE

def sophie_init():
	return {
		'screen': run_game,
	}

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


class GameLoop:
	"""
	I think I'd like to try exposing a game loop as a system-defined actor similar in spirit to the console.
	In concept you'd configure behavior by sending this messages.
	A distinguished "play" message starts an event-loop on a dedicated thread.
	
	For now I'll stick to physical events, not logical ones like double-click or dragon-drop.
	The alt-F4 quit-key combination comes across as a quit event, though.
	"""
	def __init__(self):
		self._on_quit = None
		self._on_mouse = None
		self._on_button_down = None
		self._on_button_up = None
		self._on_key_down = None
		self._on_key_up = None
		self._on_tick = None
	pass

	def play(self, size, fps):
		pygame.init()
		width, height = force(size['x']), force(size['y'])
		display = pygame.display.set_mode((width, height))

		clock = pygame.time.Clock()
		while True:
			for event in pygame.event.get():
				# Give Sophie code a chance to update the model based on an event.
				if event.type == pygame.QUIT:
					return

			clock.tick(fps)
			if self._on_tick is not None:
				self._on_tick.dispatch_with(display)
			
		pass
		

class Display(Actor):
	""" For now, wraps parts of gfxdraw because gfxdraw releases the gil. """
	pass

game_loop = NativeObjectProxy(GameLoop())
game_loop.TASK_QUEUE = MAIN_QUEUE.main_thread
display = NativeObjectProxy(Display())
