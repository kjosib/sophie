#define SDL_MAIN_HANDLED
#include <SDL.h>

#include "common.h"

/***********************************************************************************/

typedef enum {
	FIELD_DISPLAY,
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
	L_CARTESIAN,
	L_MOUSE_EVENT,
	L_BUTTON_EVENT,
	L_KEY_EVENT,
} LINKAGE;

static Value *linkage;

#define GAME AS_ACTOR(args[0])
#define DISPLAY GAME->fields[FIELD_DISPLAY]
#define DISPLAY_PTR ((Display*)AS_PTR(DISPLAY))

static Value game_on_mouse(Value *args) {
	GAME->fields[ON_MOUSE] = args[1];
	printValue(args[1]);
	return NIL_VAL;
}

static Value game_on_tick(Value *args) {
	GAME->fields[ON_TICK] = args[1];
	return NIL_VAL;
}

static void compose(LINKAGE what) {
	push(linkage[what]);
	apply_constructor();
}

static void push_cartesian(Sint32 x, Sint32 y) {
	// cartesian is (x:number, y:number);
	push(NUMBER_VAL(x));
	push(NUMBER_VAL(y));
	compose(L_CARTESIAN);
}

static void push_motion_event(SDL_MouseMotionEvent *ev) {
	/*
	mouse_event is (
		pos : cartesian, rel : cartesian,
		left : flag, middle : flag, right : flag,
		is_touch : flag,
	);
	*/
	push_cartesian(ev->x, ev->y);
	push_cartesian(ev->xrel, ev->yrel);
	Uint32 buttons = SDL_GetMouseState(NULL, NULL);
	push(BOOL_VAL(buttons & SDL_BUTTON_LMASK));
	push(BOOL_VAL(buttons & SDL_BUTTON_MMASK));
	push(BOOL_VAL(buttons & SDL_BUTTON_RMASK));
	push(BOOL_VAL(ev->which == SDL_TOUCH_MOUSEID));
	compose(L_MOUSE_EVENT);
}

static void push_button_event(SDL_MouseButtonEvent *ev) {
	/*  button_event is (pos:rect, button:number, is_touch:flag);  */
	push_cartesian(ev->x, ev->y);
	push(NUMBER_VAL(ev->button));
	push(BOOL_VAL(ev->which == SDL_TOUCH_MOUSEID));
	compose(L_BUTTON_EVENT);
}

static bool is_running = false;

typedef struct {
	GC header;
	SDL_Renderer *renderer;
	SDL_Window *window;
} Display;

static void blacken_display(Display *display) {}  // ... in the GC sense.

static void finalize_display(Display *display) {
	if (display->renderer) {
		SDL_DestroyRenderer(display->renderer);
		display->renderer = NULL;
	}
	if (display->window) {
		SDL_DestroyWindow(display->window);
		display->window = NULL;
	}
}

static size_t size_display(Display *display) {
	return sizeof(Display);
}

GC_Kind KIND_Display = {
	.blacken = blacken_display,
	.size = size_display,
	.finalize = finalize_display,
};

static Display *init_display(int width, int height) {
	Display *display = gc_allocate(&KIND_Display, sizeof(Display));
	display->window = NULL;
	display->renderer = NULL;
	gc_must_finalize((GC*)display);
	display->window = SDL_CreateWindow("Sophie Game Window", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, width, height, SDL_WINDOW_SHOWN);
	if (display->window == NULL) {
		fprintf(stderr, "Failed to create window: %s\n", SDL_GetError());
		SDL_Quit();
		exit(1);
	}
	display->renderer = SDL_CreateRenderer(display->window, -1, SDL_RENDERER_ACCELERATED);
	if (display->renderer == NULL) {
		fprintf(stderr, "Failed to create renderer: %s\n", SDL_GetError());
		SDL_DestroyWindow(display->window);
		SDL_Quit();
		exit(1);
	}
	return display;
}

static Value game_play(Value *args) {
	if (is_running) {
		crashAndBurn("Sophie does not know what it means to start a game while one is still playing");
	}

	SDL_SetMainReady();
	if (SDL_Init(SDL_INIT_EVERYTHING) < 0) {
		fprintf(stderr, "Failed to init SDL: %s\n", SDL_GetError());
		exit(1);
	}
	SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "linear");

	Record *size = AS_RECORD(args[1]);
	int width = (int)AS_NUMBER(force(size->fields[0]));
	int height = (int)AS_NUMBER(force(size->fields[1]));

	int fps = (int)AS_NUMBER(args[2]);

	int frame_ticks = 1000 / fps;
	int frame_wobble = 1000 % fps;

	GAME->fields[FIELD_DISPLAY] = GC_VAL(init_display(width, height));

	SDL_SetRenderDrawColor(DISPLAY_PTR->renderer, 96, 128, 255, 255);
	SDL_RenderClear(DISPLAY_PTR->renderer);

	Uint64 next_tick = SDL_GetTicks64();
	int wobble = 0;

	for (;;) {
		if (!IS_NIL(GAME->fields[ON_TICK])) {
			fputs("Tick ", stdout);
		}

		SDL_Event ev;
		while (SDL_PollEvent(&ev)) {
			switch (ev.type) {
			case SDL_QUIT:
				finalize_display(DISPLAY_PTR);
				SDL_Quit();
				return NIL_VAL;
			case SDL_KEYDOWN:
				printf("Key Symbol: %d\n", ev.key.keysym.sym);
				break;
			case SDL_MOUSEMOTION:
				if (!IS_NIL(GAME->fields[ON_MOUSE])) {
					push_motion_event(&ev.motion);
					push(GAME->fields[ON_MOUSE]);
					apply_bound_method();
					enqueue_message(pop());
				}
				break;
			case SDL_MOUSEBUTTONDOWN:
				if (!IS_NIL(GAME->fields[ON_BUTTON_DOWN])) {
					push_button_event(&ev.button);
					push(GAME->fields[ON_BUTTON_DOWN]);
					apply_bound_method();
					enqueue_message(pop());
				}
				break;
			case SDL_MOUSEBUTTONUP:
				if (!IS_NIL(GAME->fields[ON_BUTTON_UP])) {
					push_button_event(&ev.button);
					push(GAME->fields[ON_BUTTON_UP]);
					apply_bound_method();
					enqueue_message(pop());
				}
				break;
			default:
				printf("Event %d\n", ev.type);
				break;
			}
		}
		drain_the_queue();
		SDL_RenderPresent(DISPLAY_PTR->renderer);


		/*
		And how not to peg the CPU?
		Ideally, something about vertical blanking intervals, but that seems to require OpenGL.
		Next best is SDL_Delay. This is imprecise but generally workable. There is an FPS goal.
		The question is how many milliseconds until the current frame's time slice expires?
		The trick is to work in units of milliframes. There are 1,000 milli-frames per frame.
		Each millisecond is fps milliframes. This will evenly spread the frames, and compensate
		for clocks that don't quite tick in phase.
		*/
		next_tick += frame_ticks;
		wobble += frame_wobble;
		if (wobble > 1000) {
			wobble -= 1000;
			next_tick++;
		}
		Uint64 now = SDL_GetTicks64();
		if (now < next_tick) SDL_Delay((Uint32)(next_tick - now));
	}
}

/***********************************************************************************/

Value game_sophie_init(Value *args) {
	// Current concept is to pass needed pure-Sophie symbols on the stack.
	assert(args + 5 == vm.stackTop);
	linkage = args;

	// Push additional field names here...
	// Works much like defining a constructor.
	push_C_string("display");
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

