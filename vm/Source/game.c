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

	NR_GAME_FIELDS
} GAME_FIELD;

typedef enum {
	DP_DISPLAY,

	NR_DP_FIELDS
} DISPLAY_PROXY_FIELD;

typedef enum {
	PIC_FILL,
	PIC_HLIN,
	PIC_VLIN,
} TAG_PIC;

typedef enum {
	L_CARTESIAN,
	L_MOUSE_EVENT,
	L_BUTTON_EVENT,
	L_KEY_EVENT,
	LL_DISPLAY_PROXY,  // Local Linakge made here and saved for later.

	NR_LINKAGES
} LINKAGE;

static Value *linkage;

#define SELF AS_ACTOR(args[0])

#define DISPLAY_PTR ((Display*)AS_PTR(SELF->fields[DP_DISPLAY]))

static Value game_on_mouse(Value *args) {
	SELF->fields[ON_MOUSE] = args[1];
	return FALSE_VAL;
}

static Value game_on_tick(Value *args) {
	SELF->fields[ON_TICK] = args[1];
	return FALSE_VAL;
}

static void compose(LINKAGE what) {
	push(linkage[what]);
	push(construct_record());
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
	.name = "SDL Display",
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

/***********************************************************************************/

// New rule: Sub-functions of the display-proxy will *NOT* refer to the VM stack.

static void set_sdl_color(SDL_Renderer *renderer, Record *color) {
	Uint8 red = (Uint8)(AS_NUMBER(color->fields[0]));
	Uint8 green = (Uint8)(AS_NUMBER(color->fields[1]));
	Uint8 blue = (Uint8)(AS_NUMBER(color->fields[2]));
	SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
}

static void dp_draw_fill(SDL_Renderer *renderer, Record *fill) {
	set_sdl_color(renderer, AS_RECORD(fill->fields[0]));
	SDL_RenderClear(renderer);
}

static void dp_hlin(SDL_Renderer *renderer, Record *hlin) {
	set_sdl_color(renderer, AS_RECORD(hlin->fields[3]));
	int x1 = (int)(AS_NUMBER(hlin->fields[0]));
	int x2 = (int)(AS_NUMBER(hlin->fields[1]));
	int y  = (int)(AS_NUMBER(hlin->fields[2]));
	SDL_RenderDrawLine(renderer, x1, y, x2, y);
}

static void dp_vlin(SDL_Renderer *renderer, Record *vlin) {
	set_sdl_color(renderer, AS_RECORD(vlin->fields[3]));
	int x  = (int)(AS_NUMBER(vlin->fields[0]));
	int y1 = (int)(AS_NUMBER(vlin->fields[1]));
	int y2 = (int)(AS_NUMBER(vlin->fields[2]));
	SDL_RenderDrawLine(renderer, x, y1, x, y2);
}

static Value dp_draw(Value *args) {
	assert(vm.stackTop == args + 2);
	FOR_LIST(args[1]) {
		push(LIST_HEAD(args[1]));  // Becomes args[2]
		assert(VAL_GC == TOP.type);
		force_deeply();
		switch (AS_RECORD(TOP)->constructor->tag) {
		case PIC_FILL:
			dp_draw_fill(DISPLAY_PTR->renderer, AS_RECORD(TOP)); break;
		case PIC_HLIN:
			dp_hlin(DISPLAY_PTR->renderer, AS_RECORD(TOP)); break;
		case PIC_VLIN:
			dp_vlin(DISPLAY_PTR->renderer, AS_RECORD(TOP)); break;
		default:
			printf("Draw %d ", AS_RECORD(TOP)->constructor->tag);
		}
		pop();
		assert(vm.stackTop == args + 2);
	}
	
	SDL_RenderPresent(DISPLAY_PTR->renderer);
	return FALSE_VAL;
}

static Value dp_close(Value *args) {
	finalize_display(DISPLAY_PTR);
	return FALSE_VAL;
}

/***********************************************************************************/

static void push_display_proxy(int width, int height) {
	push(GC_VAL(init_display(width, height)));
	push(linkage[LL_DISPLAY_PROXY]);
	push(make_template_from_dfn());
	make_actor_from_template();
}

static Value game_play(Value *args) {  // ( SELF size fps -- )
	if (is_running) {
		crashAndBurn("Sophie does not know what it means to start a game while one is still playing");
	}

	Record *size = AS_RECORD(args[1]);
	int width = (int)AS_NUMBER(force(size->fields[0]));
	int height = (int)AS_NUMBER(force(size->fields[1]));

	int fps = (int)AS_NUMBER(args[2]);

	int frame_ticks = 1000 / fps;
	int frame_wobble = 1000 % fps;

	push_display_proxy(width, height);  // Becomes args[3]
	assert(is_actor(args[3]));

	Uint64 next_tick = SDL_GetTicks64();
	int wobble = 0;

	for (;;) {
		if (!IS_ENUM(SELF->fields[ON_TICK])) {
			push(args[3]);
			push(SELF->fields[ON_TICK]);
			enqueue_message(apply());
		}

		SDL_Event ev;
		while (SDL_PollEvent(&ev)) {
			switch (ev.type) {
			case SDL_QUIT:
				push(args[3]);
				push_C_string("close");
				bind_method_by_name();
				enqueue_message(pop());
				return FALSE_VAL;
			case SDL_KEYDOWN:
				printf("Key Down: %d\n", ev.key.keysym.sym);
				break;
			case SDL_KEYUP:
				printf("Key Up: %d\n", ev.key.keysym.sym);
				break;
			case SDL_MOUSEMOTION:
				if (!IS_ENUM(SELF->fields[ON_MOUSE])) {
					push_motion_event(&ev.motion);
					push(SELF->fields[ON_MOUSE]);
					enqueue_message(apply());
				}
				break;
			case SDL_MOUSEBUTTONDOWN:
				if (!IS_ENUM(SELF->fields[ON_BUTTON_DOWN])) {
					push_button_event(&ev.button);
					push(SELF->fields[ON_BUTTON_DOWN]);
					enqueue_message(apply());
				}
				break;
			case SDL_MOUSEBUTTONUP:
				if (!IS_ENUM(SELF->fields[ON_BUTTON_UP])) {
					push_button_event(&ev.button);
					push(SELF->fields[ON_BUTTON_UP]);
					enqueue_message(apply());
				}
				break;
			default:
				printf("Event %d\n", ev.type);
				break;
			}
		}
		drain_the_queue();
		


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

static void define_display_proxy_as_linkage() {
	push_C_string("display");

	push_C_string("DisplayProxy");
	define_actor(NR_DP_FIELDS);

	create_native_method("draw", 2, dp_draw);
	create_native_method("close", 1, dp_close);

	// Leave on stack for linkage.
	assert(is_actor_dfn(linkage[LL_DISPLAY_PROXY]));
}

static void define_event_loop_as_global() {
	// Push field names here...
	// Works much like defining a constructor.
	push_C_string("on_quit");
	push_C_string("on_mouse");
	push_C_string("on_button_down");
	push_C_string("on_button_up");
	push_C_string("on_key_down");
	push_C_string("on_key_up");
	push_C_string("on_tick");

	push_C_string("SDL_GameLoop"); // Implements the GameLoop interface.
	define_actor(NR_GAME_FIELDS);  // Will need fields soon enough at least for main display.

	// Continue to follow the trail forged by the console-actor:

	create_native_method("on_mouse", 2, game_on_mouse);
	create_native_method("on_tick", 2, game_on_tick);
	create_native_method("play", 3, game_play);

	Value dfn = pop();
	for (int i = 0; i < NR_GAME_FIELDS; i++) push(FALSE_VAL);
	push(dfn);
	push(make_template_from_dfn());
	make_actor_from_template();

	push_C_string("events");
	defineGlobal();
}

Value game_sophie_init(Value *args) {
	// Current concept is to pass needed pure-Sophie symbols on the stack.
	assert(args + LL_DISPLAY_PROXY == vm.stackTop);
	linkage = args;

	define_display_proxy_as_linkage();
	define_event_loop_as_global();

	SDL_SetMainReady();
	if (SDL_Init(SDL_INIT_EVERYTHING) < 0) {
		fprintf(stderr, "Failed to init SDL: %s\n", SDL_GetError());
		exit(1);
	}
	if (atexit(SDL_Quit)) {
		fprintf(stderr, "Failed to schedule SDL shut-down\n");
		exit(1);
	}
	SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "linear");

	assert(args + NR_LINKAGES == vm.stackTop);
	assert(is_actor_dfn(linkage[LL_DISPLAY_PROXY]));

	return BOOL_VAL(true);
}

