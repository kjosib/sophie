# Sophie

A call-by-need strong-inferred-type language named for French mathematician Sophie Germain.

Sophie is an educational project. It's for fun and learning, but might grow into something useful.

The design goals, _in priority order,_ are:

1. Have Fun!
2. Keep it simple.
3. Subjectively readable appearance in my personal opinion.
4. Be pragmatic. Trade cheap computer power for a nicer time.
5. Call-by-need pure-functional for general computation.
6. Turtle graphics.
7. Other nice things to have. (See the roadmap.)

When all is said and done, I'd like Sophie to be a viable alternative for learning (or deepening one's grasp of) comp-sci.
The call-by-need pure-functional design gives Sophie a very different flavor from your average introductory language,
but should produce excellent habits.

## What's it look like?

My aesthetic bends toward the [Algol](https://www.theregister.com/2020/05/15/algol_60_at_60/) clade,
such as Pascal, C, Perl, Python, and Ruby. Given that most programmers seem to learn Java and Python these days,
this should not break too many brains. However, Sophie is an expression-oriented call-by-need language,
so some things are bound look a bit more like SQL or Haskell.

Here is a preliminary example:
```
# Comments extend from a hash-mark to the end of the same line.

type:
predicate[A] is A -> flag;
album is (title:string, artist:string, year:integer, tracks:list[string]);
tree[X] is { nil | node(left:X,right:X) };
album_tree is tree[album];

define:

primes_simple(max) = filter(is_prime, 2 .<=. max) where
    is_prime(x) = not any [ y mod x == 0 for y in 2 .<=. floor(sqrt(x)) ];
end primes_simple;

primes_smarter(max:integer) -> list[integer] = NIL IF max < 2 ELSE cons(2, odd_primes) where
    odd_primes = more_primes(0, cons(4, map(square, odd_primes)), 3);
    more_primes(bound, squares, candidate_prime) = CASE
        WHEN candidate_prime > max THEN NIL;
		WHEN candidate_prime > squares.head THEN more_primes(bound+1, squares.tail, candidate_prime);
        WHEN is_prime THEN cons(candidate_prime, successors);
        ELSE successors;
    ESAC where
		is_prime = NOT any (map(is_divisor, take(bound, odd_primes)));
		is_divisor(p) = candidate_prime MOD p == 0;
        successors = more_primes(bound, squares, candidate_prime+2);
    end more_primes;
end primes_smarter;

square(x) = x * x;

any(xs) = xs != nil and (xs.head or any(xs.tail));
map(fn, elts) = nil if elts == nil else cons(fn(elts.head), map(fn, elts.tail));
take(n, xs) = nil if n < 1 else cons(xs.head, take(n-1, xs.tail));

begin:
    map(square, [1,2,3,4]);
    primes_smarter(2000);
end.
```

Keywords are case-insensitive. Names will preserve case but must differ in more than just case.
Whitespace is only significant for delimiting other tokens that might otherwise run together.
Note that `nil` can be a member of both `list` and `tree`. When it's not clear from context,
there will be syntax to clarify such things.

Several important decisions are not yet made, and some things may change.
The arithmetic progression syntax `.<=.` is provisional and may change or go away.
I'd like syntax for literal sets and dictionary-like objects.

## Install/Run

1. `pip install --upgrade booze-tools`
2. Clone or download the repository.
3. `py -m sophie examples/primes.sg`

## What to Expect

Sophie can run programs, subject to a few caveats.

* There is not yet any way to take input.
* The only output is the return value from each expression in the `begin:` section.
* List comprehensions and range/progression operator(s) do not yet work.
* It is of course not a high-performance experience yet.

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
* The evaluator can run programs and display results.
* It does not check types, so run-time errors are still possible.
* It does check the validity of identifiers (but not yet field names, which depend on type).
* List comprehension (expressions like `[expr FOR name IN expr]`) are removed from the syntax for now.
  Something will take its place, but it will take some work.
* There is no interactivity. It will depend on the _Functional Process Abstraction_ which also doesn't exist yet.
* Imports and exports are waiting on a proper module system, so they don't do anything yet.

For FPA, maybe controlling a bank of elevators would be a good concrete example problem?
The pipe-dream is an asynchronous and resilient processes network similar to Erlang.


## Why not just use Language X, Y, or Z?

Have you been paying attention?

## Long-Term Plans

Sophie also provides a convenient test-bed for my own learning and experimentation.
Here are some examples:

### For Use in Presentations

I occasionally give talks on comp-sci concepts.
Experience with audience reaction to the syntax and semantics of Sophie will guide further design development.
It may seem a small thing, but algebra-style parentheses are much more clear to me than Lisp or Haskell style. 

### Various forms of optimization

#### Transparent Scope Lifting

The nose-following translation of a sub-function involves a static link to the containing function.
However, functions can be subordinated for namespace control, not just for access to surrounding identifiers.
If a function doesn't use the immediately-enclosing scope, then it may be translated *as if* it were defined
in the larger scope, but only visible where it's *actually* defined.
This may prevent some redundant calculation, depending on how the affected function is used.

#### Transparent Adaptive Strictness

Sophie guarantees call-by-need semantics, but call-by-value is normally a more efficient translation.
In many cases, you can prove that *if expression X terminates, then subexpression Y gets evaluated,*
from which you may then schedule *Y* within *X* on a strict basis.
This transformation diminishes the amount of thunks a translation must prepare,
which would accelerate a compiled Sophie program to a competitive speed.

### Foreign-function interface

A langauge gets immediately much more useful if it can harness an existing ecosystem.
High-speed numerical subsystems would be an obvious early candidate.
(This might entail integrating a true `array` type, or maybe even `matrix` and `tensor`.)
Another strong candidate would be turtle graphics or even a GUI toolkit such as TK or OpenGL.

### Platforms

Nothing stops an intrepid enthusiast from translating Sophie to the JVM, the CLR, or native CPU code.
