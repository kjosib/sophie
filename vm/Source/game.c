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
	TIE_FILL,
	TIE_STROKE,
} TAG_IMAGE_ELEMENT;

typedef enum {
	STROKE_HLIN,
	STROKE_VLIN,
	STROKE_LINE,
	STROKE_POLYLINE,
	STROKE_BOX,
	STROKE_FILL_BOX,
	STROKE_CIRCLE,
	STROKE_ELLIPSE,
	STROKE_ARC,
} TAG_STROKE_ELEMENT;

typedef enum {
	L_CARTESIAN,
	L_MOUSE_EVENT,
	L_BUTTON_EVENT,
	L_KEY_EVENT,
	LL_DISPLAY_PROXY,  // Local Linakge made here and saved for later.

	NR_LINKAGES
} LINKAGE;

static Value *linkage;

#define NR_SCRATCH 256   // Must be a multiple of 8. Ought to be plenty to overcome alleged API-call overhead.
static SDL_Point scratch_points[NR_SCRATCH];

#define SELF AS_ACTOR(args[0])

#define DISPLAY_PTR ((Display*)AS_PTR(SELF->fields[DP_DISPLAY]))

static Value game_on_quit(Value *args) {
	gc_mutate(&SELF->fields[ON_QUIT], args[1]);
	return UNSET_VAL;
}

static Value game_on_mouse(Value *args) {
	gc_mutate(&SELF->fields[ON_MOUSE], args[1]);
	return UNSET_VAL;
}

static Value game_on_tick(Value *args) {
	gc_mutate(&SELF->fields[ON_TICK], args[1]);
	return UNSET_VAL;
}

static Value game_on_button_down(Value *args) {
	gc_mutate(&SELF->fields[ON_BUTTON_DOWN], args[1]);
	return UNSET_VAL;
}

static Value game_on_button_up(Value *args) {
	gc_mutate(&SELF->fields[ON_BUTTON_UP], args[1]);
	return UNSET_VAL;
}

static Value game_on_key_down(Value *args) {
	gc_mutate(&SELF->fields[ON_KEY_DOWN], args[1]);
	return UNSET_VAL;
}

static Value game_on_key_up(Value *args) {
	gc_mutate(&SELF->fields[ON_KEY_UP], args[1]);
	return UNSET_VAL;
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
#if USE_FINALIZERS
	gc_please_finalize((GC*)display);
#endif
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

// Sub-functions of the display-proxy *MUST* refer to the VM stack because I'm not forcing anything just yet.
// Some day perhaps I'll solve the pre-forcing problem but for now it's online.

static void set_sdl_color(SDL_Renderer *renderer) { // COLOR --
	TOP = force(TOP);
	Uint8 red = (Uint8)(AS_NUMBER(force(FIELD(TOP, 0))));
	Uint8 green = (Uint8)(AS_NUMBER(force(FIELD(TOP, 1))));
	Uint8 blue = (Uint8)(AS_NUMBER(force(FIELD(TOP, 2))));
	pop();
	SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
}


static void stroke_hlin(SDL_Renderer *renderer) {
	int x1 = (int)(AS_NUMBER(force(FIELD(TOP, 0))));
	int x2 = (int)(AS_NUMBER(force(FIELD(TOP, 1))));
	int y  = (int)(AS_NUMBER(force(FIELD(TOP, 2))));
	SDL_RenderDrawLine(renderer, x1, y, x2, y);
}

static void stroke_vlin(SDL_Renderer *renderer) {
	int x  = (int)(AS_NUMBER(force(FIELD(TOP, 0))));
	int y1 = (int)(AS_NUMBER(force(FIELD(TOP, 1))));
	int y2 = (int)(AS_NUMBER(force(FIELD(TOP, 2))));
	SDL_RenderDrawLine(renderer, x, y1, x, y2);
}

static SDL_Point force_xy() {
	SDL_Point it = {
		.x = (int)(AS_NUMBER(force(FIELD(TOP, 0)))),
		.y = (int)(AS_NUMBER(force(FIELD(TOP, 1)))),
	};
	pop();
	return it;
}

static void stroke_line(SDL_Renderer *renderer) {
	push(force(FIELD(TOP, 0)));
	SDL_Point start = force_xy();
	push(force(FIELD(TOP, 1)));
	SDL_Point stop = force_xy();
	SDL_RenderDrawLine(renderer, start.x, start.y, stop.x, stop.y);
}

static void stroke_polyline(SDL_Renderer *renderer) {
	push(force(FIELD(TOP, 0)));
	if (!IS_ENUM(TOP)) {
		push(LIST_HEAD(TOP));
		SDL_Point start = force_xy();
		TOP = LIST_TAIL(TOP);
		FOR_LIST(TOP) {
			push(LIST_HEAD(TOP));
			SDL_Point stop = force_xy();
			SDL_RenderDrawLine(renderer, start.x, start.y, stop.x, stop.y);
			start = stop;
		}
	}
	pop();
}

static void stroke_box(SDL_Renderer *renderer) {
	push(force(FIELD(TOP, 0)));
	SDL_Point corner = force_xy();
	push(force(FIELD(TOP, 1)));
	SDL_Point measure = force_xy();
	SDL_Rect rect = { corner.x, corner.y, measure.x, measure.y };
	SDL_RenderDrawRect(renderer, &rect );
}

static void stroke_fill_box(SDL_Renderer *renderer) {
	push(force(FIELD(TOP, 0)));
	SDL_Point corner = force_xy();
	push(force(FIELD(TOP, 1)));
	SDL_Point measure = force_xy();
	SDL_Rect rect = { corner.x, corner.y, measure.x, measure.y };
	SDL_RenderFillRect(renderer, &rect );
}

static void stroke_circle(SDL_Renderer *renderer) {
	// See the description in the docs at tech/graphics.
	// I'm doing this clean-room from my own understanding of the math.

	push(force(FIELD(TOP, 0)));
	SDL_Point center = force_xy();
	int radius = (int)AS_NUMBER(force(FIELD(TOP, 1)));

	int x = radius, y = 0, err = -(radius);

	int cp = 0;  // count of points
	while (x >= y) {
		// Plot points with eightfold symmetry:
		scratch_points[cp++] = (SDL_Point){ center.x + x, center.y + y };
		scratch_points[cp++] = (SDL_Point){ center.x - x, center.y + y };
		scratch_points[cp++] = (SDL_Point){ center.x + x, center.y - y };
		scratch_points[cp++] = (SDL_Point){ center.x - x, center.y - y };
		scratch_points[cp++] = (SDL_Point){ center.x + y, center.y + x };
		scratch_points[cp++] = (SDL_Point){ center.x - y, center.y + x };
		scratch_points[cp++] = (SDL_Point){ center.x + y, center.y - x };
		scratch_points[cp++] = (SDL_Point){ center.x - y, center.y - x };
		// Must we flush?
		if (cp == NR_SCRATCH) {
			SDL_RenderDrawPoints(renderer, scratch_points, cp);
			cp = 0;
		}
		// Increment the fast axis (and bump the error term accordingly).
		err += y + y + 1;
		y++;
		// If outside the circle, go left one (and update the error term).
		if (err > 0) {
			x--;
			err -= x + x + 1;
		}
	}
	// Likely need to flush some points:
	if (cp) SDL_RenderDrawPoints(renderer, scratch_points, cp);
}

static void dp_stroke(SDL_Renderer *renderer) { // list of stroke elements --
	FOR_LIST(TOP) {
		push(LIST_HEAD(TOP));
		assert(INDICATOR(TOP) == IND_GC);
		switch (AS_RECORD(TOP)->constructor->tag) {
		case STROKE_HLIN: stroke_hlin(renderer); break;
		case STROKE_VLIN: stroke_vlin(renderer); break;
		case STROKE_LINE: stroke_line(renderer); break;
		case STROKE_POLYLINE: stroke_polyline(renderer); break;
		case STROKE_BOX: stroke_box(renderer); break;
		case STROKE_FILL_BOX: stroke_fill_box(renderer); break;
		case STROKE_CIRCLE: stroke_circle(renderer); break;
		case STROKE_ELLIPSE:
		case STROKE_ARC:
			break;
		}
		pop();
	}
	pop();
}

static Value dp_draw(Value *args) {
	assert(vm.stackTop == args + 2);
	FOR_LIST(args[1]) {
		push(LIST_HEAD(args[1]));  // Becomes args[2]
		assert(INDICATOR(TOP) == IND_GC);
		switch (AS_RECORD(TOP)->constructor->tag) {
		case TIE_FILL:
			push(FIELD(TOP,0));  // The fill color
			set_sdl_color(DISPLAY_PTR->renderer);  // consume/set it
			SDL_RenderClear(DISPLAY_PTR->renderer);
			break;
		case TIE_STROKE:
			push(FIELD(TOP, 0));  // The fill color
			set_sdl_color(DISPLAY_PTR->renderer);  // consume/set it
			push(FIELD(TOP, 1));  // The fill color
			dp_stroke(DISPLAY_PTR->renderer);
			break;
		default:
			printf("Draw %d ", AS_RECORD(TOP)->constructor->tag);
		}
		pop();
		assert(vm.stackTop == args + 2);
	}
	
	SDL_RenderPresent(DISPLAY_PTR->renderer);
	return UNSET_VAL;
}

static Value dp_close(Value *args) {
	finalize_display((Display *)AS_PTR(SELF->fields[DP_DISPLAY]));
	return UNSET_VAL;
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
		if (!IS_UNSET(SELF->fields[ON_TICK])) {
			push(args[3]);
			push(SELF->fields[ON_TICK]);
			enqueue_message(apply());
		}

		SDL_Event ev;
		while (SDL_PollEvent(&ev)) {
			switch (ev.type) {
			case SDL_QUIT: {
				push(args[3]);
				push_C_string(":close:");
				bind_method_by_name();
				enqueue_message(pop());
				Value on_quit = SELF->fields[ON_QUIT];
				if (!IS_UNSET(on_quit)) enqueue_message(on_quit);
				return UNSET_VAL;
			}
			case SDL_KEYDOWN:
#ifdef _DEBUG
				printf("Key Down: %d\n", ev.key.keysym.sym);
#endif // _DEBUG
				break;
			case SDL_KEYUP:
#ifdef _DEBUG
				printf("Key Up: %d\n", ev.key.keysym.sym);
#endif // _DEBUG
				break;
			case SDL_MOUSEMOTION:
				if (!IS_UNSET(SELF->fields[ON_MOUSE])) {
					push_motion_event(&ev.motion);
					push(SELF->fields[ON_MOUSE]);
					enqueue_message(apply());
				}
				break;
			case SDL_MOUSEBUTTONDOWN:
				if (!IS_UNSET(SELF->fields[ON_BUTTON_DOWN])) {
					push_button_event(&ev.button);
					push(SELF->fields[ON_BUTTON_DOWN]);
					enqueue_message(apply());
				}
				break;
			case SDL_MOUSEBUTTONUP:
				if (!IS_UNSET(SELF->fields[ON_BUTTON_UP])) {
					push_button_event(&ev.button);
					push(SELF->fields[ON_BUTTON_UP]);
					enqueue_message(apply());
				}
				break;
			case SDL_WINDOWEVENT:
				break;
			case SDL_TEXTEDITING:
				break;
			case SDL_AUDIODEVICEADDED:
				break;
			default:
#ifdef _DEBUG
				printf("Event %d\n", ev.type);
#endif // _DEBUG
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
	push_C_string("DisplayProxy");
	make_field_offset_table(NR_DP_FIELDS);
	push_C_string("display");
	define_actor();

	create_native_method("draw", 2, dp_draw);
	create_native_method(":close:", 2, dp_close);

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
	make_field_offset_table(NR_GAME_FIELDS);

	push_C_string("SDL_GameLoop"); // Implements the GameLoop interface.
	define_actor();  // Will need fields soon enough at least for main display.

	// Continue to follow the trail forged by the console-actor:

	create_native_method("on_quit", 2, game_on_quit);
	create_native_method("on_mouse", 2, game_on_mouse);
	create_native_method("on_tick", 2, game_on_tick);
	create_native_method("on_button_down", 2, game_on_button_down);
	create_native_method("on_button_up", 2, game_on_button_up);
	create_native_method("on_key_down", 2, game_on_key_down);
	create_native_method("on_key_up", 2, game_on_key_up);
	create_native_method("play", 3, game_play);

	Value dfn = pop();
	for (int i = 0; i < NR_GAME_FIELDS; i++) push(UNSET_VAL);
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

