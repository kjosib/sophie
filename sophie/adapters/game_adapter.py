"""
Native driver to bind Sophie with the graphics and sound capabilities of SDL via PyGame.

Eventually.

For the moment, it's just a spike.
"""
import sys, pygame
pygame.init()

size = width, height = 800, 600
display = pygame.display.set_mode(size)

clock = pygame.time.Clock()

NIL : dict

def sophie_init(force, nil):
	global NIL
	NIL = force(nil)
	return {
		'screen': run_game,
	}

def run_game(force, screen):
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

