# Sophie

A programming language with:

* Call-by-need (lazy) pure functions
* Actor-based concurrency and interaction
* A strong impredicative type system
* Readable, intuitive syntax
* Other innovative niceties

**Sophie** is named in honor of French polymath Sophie Germain.

Sophie started as a personal project for fun and learning, but is growing into something useful.
The graphics features provide a nice diversion and opportunity to play with
higher ideas than what typically comes up in the daily grind of professional coding.
These days, Sophie is also a vehicle for solving Advent-of-Code puzzles.

When all is said and done, I'd like Sophie to be a viable alternative for learning (or deepening one's grasp of) comp-sci.
The call-by-need pure-functional design gives Sophie a very different flavor from your average introductory language,
but should produce excellent habits.

## What's it look like?

The best answer is to [look at the examples](https://github.com/kjosib/sophie/tree/main/examples).

![Syntax Highlighting](https://github.com/kjosib/sophie/blob/main/docs/syntax%20highlight.png?raw=true)

My aesthetic bends toward the [Algol](https://www.theregister.com/2020/05/15/algol_60_at_60/) clade,
such as Pascal, C, Perl, Python, and Ruby. Given that most programmers seem to learn Java and Python these days,
this should not break too many brains. However, Sophie is an expression-oriented call-by-need language,
so some things are bound look a bit more like SQL or Haskell.

It may seem a small thing, but algebra-style parentheses are much more clear to me than Lisp or Haskell style.
I think that's also true for most of the world's programmers.
Things are better when the notation does not interfere with understanding.

## Installing

You can simply `pip install sophie-lang` which will get you going in a pinch,
but it's probably a better experience to follow the
[slightly more involved directions](https://sophie.readthedocs.io/en/latest/howto/quick_start.html)
in the manual.

## How do I Learn Sophie?

1. [Read the docs](https://sophie.readthedocs.io)
2. Poke around the [examples](https://github.com/kjosib/sophie/tree/main/examples) and [grammar](https://github.com/kjosib/sophie/blob/main/sophie/Sophie.md)
3. Contribute to the docs in the usual way.

It sure might be nice to have a *Learn computer science with Sophie*
book on the coffee table, but that book has yet to be written.
So the most likely direction is to set up some experimental instructional setting,
and then take notes on how things go.

## Syntax Highlighting

There is a
[basic highlighting grammar for vscode](https://github.com/kjosib/sophie/tree/main/ide-ext/vscode/sophie-lang)
in the GitHub repository.
If you clone the repository or download a release,
then you can install the Sophie language extension directly from there.

## Current Status

There is now a [change log](https://github.com/kjosib/sophie/tree/main/CHANGELOG.md).

Some things are going well:

* A native-code [Virtual-Machine](https://github.com/kjosib/sophie/tree/main/vm) can run Sophie code at a respectable speed.
  It reads a "compiled" form which you can generate with a command-line like `sophie -x your/sophie/program.sg > program.is`.
  It runs most of the examples just fine, but lags slightly behind on extensions.
* Sophie has Turtle-graphics! (See [here](https://github.com/kjosib/sophie/blob/main/examples/turtle/turtle.sg) for examples.)
* Sophie is interactive! See [this guessing game](https://github.com/kjosib/sophie/blob/main/examples/games/guess_the_number.sg) as an example.
* The type-checker gives excellent feedback and cannot be fooled.
  Through abstract interpretation it completely rules out *type* errors.
  (Domain errors, such as division by zero, are still possible.)
* The module system got an upgrade: there is now a notion of a system-package and the beginnings of a standard library.
* The FFI: Sophie can call Python; Python can call Sophie; and Python can install I/O drivers into Sophie.
  The same FFI directives on the Sophie side interact properly with the native-code VM.
* Compile-time error display is generally clear and informative.

Some things are in progress:

* SDL bindings (via PyGame for now). See for example this [graphical mouse-chaser](https://github.com/kjosib/sophie/blob/main/examples/games/mouse.sg).
* Operator overloading.

Certain things are not started yet:

* Variable-Arity Functions. (This may never happen.)
* Ad-hoc polymorphic multi-methods. (This becomes less interesting once operator overloading gets finished.)
* List comprehension (expressions like `[expr FOR name IN expr]`) are removed from the syntax for now.

## Why not just use Language X, Y, or Z?

Have you been paying attention?

## Long-Term Plans

Use Sophie as a medium for explaining software concepts in talks and papers.
Experience with audience reaction to the syntax and semantics of Sophie will guide further design development.
Sophie also provides a convenient test-bed for learning and experimentation.

