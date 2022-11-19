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

## Install/Run

1. `pip install --upgrade booze-tools`
2. Clone or download the repository.
3. `py -m sophie examples/turtle.sg`

Yes, it's implemented atop Python. For now. That's a key enabler, actually.
Python pays the bills right now. C'est la vie.

## How do I Learn Sophie?

1. [Read the docs](https://sophie.readthedocs.io)
2. Poke around the [examples](https://github.com/kjosib/sophie/tree/main/examples) and [grammar](https://github.com/kjosib/sophie/blob/main/sophie/Sophie.md)
3. Contribute to the docs in the usual way.

It sure might be nice to have a *Learn computer science with Sophie*
book on the coffee table, but that book has yet to be written.
So the most likely direction is to set up some experimental instructional setting,
and then take notes on how things go.

## Current Status

* Sophie has Turtle-graphics! (See [here](https://github.com/kjosib/sophie/blob/main/examples/turtle.sg) for examples.)
* The evaluator can run programs and display results, including turtle graphics as mentioned.
* Type checking is a work in progress. Run-time errors are still possible, but this will soon change.
* It checks the validity of all identifiers (but not yet field names, which depend on type checking).
* List comprehension (expressions like `[expr FOR name IN expr]`) are removed from the syntax for now.
  Something will take its place, but it will take some work.
* There is no interactivity. It will depend on the _Functional Process Abstraction_ which also doesn't exist yet.
* Imports and exports are waiting on a proper module system, so they don't do anything yet.

For FPA, maybe controlling a bank of elevators would be a good concrete example problem?
The pipe-dream is an asynchronous and resilient processes network similar to Erlang.


## Why not just use Language X, Y, or Z?

Have you been paying attention?

## Long-Term Plans

Use Sophie as a medium for explaining software concepts in talks and papers.
Experience with audience reaction to the syntax and semantics of Sophie will guide further design development.
Sophie also provides a convenient test-bed for learning and experimentation.

