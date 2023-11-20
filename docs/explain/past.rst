Discarded Ideas
================

This chapter contains ideas that are no longer part of Sophie.
Yet they influenced the path Sophie took,
and there may be some historical interest.


.. contents::
    :local:
    :depth: 2


I/O, Randomness, and the Process Abstraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
    This section was created before Sophie had an actor model.
    Now her ``console`` actor handles all of these things.

One view of a process is a function which must wait for an input event before computing anything.
Specifically, it computes its own next state (i.e. subsequent behavior-function) and any outputs.
You don't have to squint much to see that as C.A.R. Hoare's original concept in the CSP paper.

Teletype: A Toy Model for Pure Functional I/O
-----------------------------------------------

We can see that model at work in the simple text-based "guess-the-number" style game.
The computer picks a number at random, then waits for a guess to arrive from the human player.
A function is on deck to respond to that guess, eventually to perform more I/O actions.

I've modeled these I/O actions as a variant-record type with four cases:

* ``done`` is the stopped process.
* ``echo`` is a process that writes some output (to the screen) and then becomes another process.
* ``read`` is a process waiting on a line of input. When that input arrives
  (i.e. the user types something and presses the ``enter`` key)
  then we have a function ready to convert that input into the next process.
* ``random`` is a process which ... generates a random number? Let's have a think about that.

These cases represent in microcosm the *essence* of the pure-functional I/O problem.
Each is a type-specimen to represent an entire class of capabilities.
``read`` and ``echo`` quite obviously represent external input and output.
But ``random`` is quite the oddball!

The Curious Case of Random Numbers
--------------------------------------

In principle, a pseudorandom number generator is just an infinite stream of numbers.
Perhaps there's some initialization procedure that reads entropy from the outside world,
but once started the PRNG is effectively an infinite sequence, which is a pure-functional thing.

Clearly, this leaves out some important details and interactions.

Seen in isolation, the PRNG looks a lot like an output process.
But there's no device or file-handle where to send that output.

Another note: Somewhat by definition, a PRNG cannot be a pure function!
The state-transition function can be pure in itself, but that state-transition needs almost a linear type:
reading the next state consumes and destroys the old, so that no two random numbers are generated from the same state.
Yet if we treat a PRNG as a normal ordinary functional sequence, then aliasing is a real problem.

On the one hand, generating the next random number does not *really* require I/O in the usual sense.
But it does represent an *isolated, stateful process* that yields numbers as-needed for other parts of the program.

Clearly, we need to treat *requesting* a random number as an I/O action. But what about *producing* them?
How do we model that?

The PRNG may be seen as a demand-pull process, or as a coroutine, or perhaps both.
As functions go, it clearly must return something characteristically similar to an ``echo`` object,
but with a number instead of a list of strings.

Now suppose we had some way to identify these demand-pull processes:
Maybe a "read number from process *<random>*" action?
We could include that token *<random>* in a more general *read-number* action.
And since there's a *<random>* process ready and willing to yield a number (while also computing its own next state)
then we get something like a CSP channel.

Taking this to the next level
------------------------------

Python's PRNG is pretty excellent. But for the purpose of discovery,
let's think through what it would take to replace it with pure **Sophie** code.

The answer is "Not very much at all."

Supposing I pass in a functional-process that emits numbers,
I can just call that function instead of the Python PRNG from within the ``teletype_adapter`` module.
The result would contain a number and the PRNG's next state-function (i.e. closure over whatever state).
``teletype_adapter`` can then give the number to the main process.

What I've described so far might be adequate to the very specific case of playing games with pseudo-randomness,
but it also points the way to a channel-based model of concurrency.

And along that path, deep problems lie in wait.

Briefly, I'd propose that nothing can be a writer unless the thing it's ready to write is fully strict.
I don't want the hapless reader to suddenly become responsible for a giant calculation that was lazily delayed.
And also, this means (a) no infinite structures,
and (b) it's possible to pass this data across process or network boundaries.

It's straightforward to show that a given data type *can* be finite.
It's undecidable whether some arbitrary algorithm *will* produce a finite structure, because *halting problem.*
So perhaps the best we can do is watchdog timers?

At any rate, the larger point is that some bit of infrastructure will be responsible for managing and scheduling all the communication.
At first some simple single-threaded round-robin approach might be fine.

Oh, and one other thing: Evidently channels are opaque types, but they are also generic types in the sense that you should not send, or expect to receive, the wrong sort of message to a typed channel.
But parameterized opaque types currently run against Sophie's rules of type engagement. It's not yet clear if this case is special enough to break the rule or what.
