# Sophie

A call-by-need strong-inferred-type language named for French mathematician Sophie Germain.

The design goals are:

1. Have Fun!
2. Keep it simple.
3. Approachable appearance. This is admittedly subjective.
4. Be pragmatic. Trade cheap computer power for a nicer time.

## What's it look like?

My aesthetic bends toward those derived from [Algol 60](https://www.theregister.com/2020/05/15/algol_60_at_60/),
such as Pascal, C, Perl, Python, and Ruby. Given that most programmers seem to learn Java and Python these days,
this should not break too many brains. However, Sophie an expression-oriented call-by-need language,
so some things will look a bit more like SQL.

Here is a preliminary example:
```
# Comments extend from a hash-mark to the end of the same line.

type:
predicate[A] is A -> flag;
tree[X] is { nil | tree(left:X,right:X) };

define:

primes_simple(max) = filter(is_prime, 2 .<=. max) where
    is_prime(x) = not any [ y mod x == 0 for y in 2 .<=. floor(sqrt(x)) ];
end primes_simple;

primes_smarter(max:integer) -> list[integer] = NIL IF max < 2 ELSE cons(2, odd_primes) where
    odd_primes = more_primes(0, cons(4, map(square, odd_primes)), 3);
    more_primes(bound, squares, candidate_prime) = CASE
        WHEN candidate_prime > max THEN NIL;
        WHEN candidate_prime > head(squares) THEN more_primes(bound+1, tail(squares), candidate_prime);
        WHEN is_prime THEN cons(candidate, successors);
        ELSE successors;
    ESAC where
        is_prime = NOT any [ candidate MOD p == 0 FOR p IN take(bound, odd_primes) ];
        successors = more_primes(bound, squares, candidate_prime+2);
    end more_primes;
end primes_smarter;
```

Keywords are case-insensitive. Names will preserve case but must differ in more than just case.
Whitespace is only significant for delimiting other tokens that might otherwise run together.
Note that `nil` can be a member of both `list` and `tree`. When it's not clear from context,
there will be syntax to clarify such things.

Several important decisions are not yet made, and some things may change.
The arithmetic progression syntax `.<=.` is provisional and may change or go away.
I'd like syntax for literal sets and dictionary-like objects.

## Install/Run

1. `pip install booze-tools`
2. Clone or download the repository.
3. `py -m sophie your_program.sg`

## What to Expect

Sophie is presently an exploratory project.
Nothing is yet etched in stone but the general philosophy.

At the moment, it just parses and reports on the parse.
There is not yet any semantic analysis or execution.
Not every grammar rule is yet written down, so the example above won't yet parse.

## How do I Learn Sophie?

When all is said and done, I'd like Sophie to be a viable alternative for
learning (or deepening one's grasp of) comp-sci.
The call-by-need pure-functional design gives Sophie a very different flavor from
your average introductory language, but should produce excellent habits.

It sure might be nice to have a *Learn computer science with Sophie*
book on the coffee table, but that book has yet to be written.
You could start by looking at the grammar,
which is at `sophie/Sophie.md` in the project hierarchy.
Of course that assumes you know how to read a context-free grammar,
which is already a somewhat-advanced topic in CS.

So the most likely direction is to set up some experimental instructional setting,
and then take notes on how things go.

## Open Problems

Most is not implemented yet. Some is not even contemplated yet.

Interactivity is a big question mark right now.
One option is explicit syntax for sequencing and (allowed) concurrency.
Maybe controlling a bank of elevators would be a good concrete example problem?
The pipe-dream is an asynchronous and resilient processes network similar to Erlang.

## Why not just use Language X, Y, or Z?

Have you been paying attention?

## Long-Term Plans

Sophie also provides a convenient test-bed for my own learning and experimentation.
Here are some examples:

### For Use in Presentations

I occasionally give talks on comp-sci concepts.
Experience with audience reaction to the syntax and semantics of Sophie will guide further design development.

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
