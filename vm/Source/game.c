#define SDL_MAIN_HANDLED
#include <SDL.h>

#include "common.h"

/***********************************************************************************/

typedef enum {
	ON_QUIT,
	ON_MOUSE,
	ON_BUTTON_DOWN,
	ON_BUTTON_UP,
	ON_KEY_DOWN,
	ON_KEY_UP,
	ON_TICK,

	NR_FIELDS,
} EVENT_FIELD;

typedef enum {
	L_RECT,
	L_MOUSE_EVENT,
	L_BUTTON_EVENT,
	L_KEY_EVENT,
} LINKAGE;

static Value *linkage;

#define GAME ((Actor *)AS_ACTOR(args[0]))

static Value game_on_mouse(Value *args) {
	GAME->fields[ON_MOUSE] = args[1];
	printValue(args[1]);
	return NIL_VAL;
}

static Value game_on_tick(Value *args) {
	Actor *game = AS_ACTOR(args[0]);
	game->fields[ON_TICK] = args[1];
	return NIL_VAL;
}

static void compose(LINKAGE what) {
	push(linkage[what]);
	apply_constructor();
}

static void push_rect(Sint32 x, Sint32 y) {
	// rect is (x:number, y:number);
	push(NUMBER_VAL(x));
	push(NUMBER_VAL(y));
	compose(L_RECT);
}

static void push_motion_event(SDL_MouseMotionEvent *ev) {
	/*
	mouse_event is (
		pos : rect, rel : rect,
		# This next part doesn't really line up with SDL.
		left : flag, middle : flag, right : flag,
		is_touch : flag,
	);
	*/
	push_rect(ev->x, ev->y);
	push_rect(ev->xrel, ev->yrel);
	Uint32 buttons = SDL_GetMouseState(NULL, NULL);
	push(BOOL_VAL(buttons & SDL_BUTTON_LMASK));
	push(BOOL_VAL(buttons & SDL_BUTTON_MMASK));
	push(BOOL_VAL(buttons & SDL_BUTTON_RMASK));
	push(BOOL_VAL(ev->which == SDL_TOUCH_MOUSEID));
	compose(L_MOUSE_EVENT);
}

static bool is_running = false;

static Value game_play(Value *args) {
	if (is_running) {
		crashAndBurn("Sophie does not know what it means to start a game while one is still playing");
	}
	SDL_SetMainReady();
	if (SDL_Init(SDL_INIT_EVERYTHING) < 0) {
		fprintf(stderr, "Failed to init SDL: %s\n", SDL_GetError());
	}
	else {
		SDL_Window *window = SDL_CreateWindow("Sophie Game Window", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, 800, 600, SDL_WINDOW_SHOWN);
		if (window == NULL) {
			fprintf(stderr, "Failed to create window: %s\n", SDL_GetError());
		}
		else {
			SDL_Event ev;

			for (is_running = true; is_running;) {
				while (SDL_PollEvent(&ev)) {
					switch (ev.type) {
					case SDL_QUIT: is_running = false; break;
					case SDL_KEYDOWN: printf("Key Symbol: %d\n", ev.key.keysym.sym); break;
					case SDL_MOUSEMOTION:
						if (!IS_NIL(GAME->fields[ON_MOUSE])) {
							push_motion_event(&ev.motion);
							push(GAME->fields[ON_MOUSE]);
							apply_bound_method();
							enqueue_message(pop());
							drain_the_queue();
						}
						break;
					case SDL_MOUSEBUTTONDOWN: printf("Click %d: %d, %d\n", ev.button.button, ev.button.x, ev.button.y); break;
					default: printf("Event %d\n", ev.type); break;
					}
					SDL_UpdateWindowSurface(window);
				}
			}
			SDL_DestroyWindow(window);
		}
	}

	SDL_Quit();

	return NIL_VAL;
}

/***********************************************************************************/

Value game_sophie_init(Value *args) {
	// Current concept is to pass needed pure-Sophie symbols on the stack.
	assert(args + 5 == vm.stackTop);
	linkage = args;

	// Push additional field names here...
	// Works much like defining a constructor.
	push_C_string("on_quit");
	push_C_string("on_mouse");
	push_C_string("on_button_down");
	push_C_string("on_button_up");
	push_C_string("on_key_down");
	push_C_string("on_key_up");
	push_C_string("on_tick");

	push_C_string("SDL_GameLoop"); // Implements the GameLoop interface.
	define_actor(NR_FIELDS);  // Will need fields soon enough at least for main display.

	// Continue to follow the trail forged by the console-actor:

	native_create_method("on_mouse", 1, game_on_mouse);
	native_create_method("on_tick", 1, game_on_tick);
	native_create_method("play", 2, game_play);

	Value dfn = pop();
	for (int i = 0; i < NR_FIELDS; i++) push(NIL_VAL);
	push(dfn);
	make_template_from_dfn();
	make_actor_from_template();

	push_C_string("events");
	defineGlobal();

	return BOOL_VAL(true);
}

