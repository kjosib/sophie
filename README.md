# Sophie

A call-by-need strong-inferred-type language named for French mathematician Sophie Germain.

Sophie is a personal project for fun and learning, but might grow into something useful.
Already the turtle-graphics feature provides a nice diversion and opportunity to play with
higher ideas than what typically comes up in the daily professional grind.

When all is said and done, I'd like Sophie to be a viable alternative for learning (or deepening one's grasp of) comp-sci.
The call-by-need pure-functional design gives Sophie a very different flavor from your average introductory language,
but should produce excellent habits.

## What's it look like?

The best answer is to [look at the examples](https://github.com/kjosib/sophie/tree/main/examples).

My aesthetic bends toward the [Algol](https://www.theregister.com/2020/05/15/algol_60_at_60/) clade,
such as Pascal, C, Perl, Python, and Ruby. Given that most programmers seem to learn Java and Python these days,
this should not break too many brains. However, Sophie is an expression-oriented call-by-need language,
so some things are bound look a bit more like SQL or Haskell.

It may seem a small thing, but algebra-style parentheses are much more clear to me than Lisp or Haskell style.
I think that's also true for most of the world's programmers.
Things are better when the notation does not interfere with understanding.

## How do I Learn Sophie?

1. [Read the docs](https://sophie.readthedocs.io)
2. Poke around the [examples](https://github.com/kjosib/sophie/tree/main/examples) and [grammar](https://github.com/kjosib/sophie/blob/main/sophie/Sophie.md)
3. Contribute to the docs in the usual way.

It sure might be nice to have a *Learn computer science with Sophie*
book on the coffee table, but that book has yet to be written.
So the most likely direction is to set up some experimental instructional setting,
and then take notes on how things go.

## Current Status

Some things are going well:

* Sophie has type-safe asynchronous message-passing concurrency.
* Sophie has Turtle-graphics! (See [here](https://github.com/kjosib/sophie/blob/main/examples/turtle/turtle.sg) for examples.)
* Sophie is interactive! See [this guessing game](https://github.com/kjosib/sophie/blob/main/examples/games/guess_the_number.sg) as an example.
* The new type-checker gives excellent feedback and cannot be fooled. Through abstract interpretation it completely rules out *type* errors.
  (Domain errors, such as division by zero, are still possible.)
* The module system got an upgrade: there is now a notion of a system-package and the beginnings of a standard library.
* The FFI (into Python): Sophie can call Python; Python can call Sophie; and Python can install I/O drivers into Sophie.
* Error display is improved in various ways. There is also now an easy way to install helpful messages for parse errors.
  This works surprisingly well now.

Some things are in progress:

* A [C-based Virtual-Machine](https://github.com/kjosib/sophie/tree/main/vm) can run Sophie code at a respectable speed.
  It reads a "compiled" form which you can generate with a command-line like `sophie -x your/sophie/program.sg > program.is`.
  It's far from complete, but making progress.  
* SDL bindings (via PyGame for now). See for example this [graphical mouse-chaser](https://github.com/kjosib/sophie/blob/main/examples/games/mouse.sg).

Certain things are not started yet:

* Variable-Arity Functions.
* Ad-hoc polymorphic multi-methods.
* List comprehension (expressions like `[expr FOR name IN expr]`) are removed from the syntax for now.

## Why not just use Language X, Y, or Z?

Have you been paying attention?

## Long-Term Plans

Use Sophie as a medium for explaining software concepts in talks and papers.
Experience with audience reaction to the syntax and semantics of Sophie will guide further design development.
Sophie also provides a convenient test-bed for learning and experimentation.

