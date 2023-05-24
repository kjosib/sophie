Communicating Sophie Processes
================================

There is a classic paper entitled `Communicating Sequential Processes <https://www.cs.cmu.edu/~crary/819-f09/Hoare78.pdf>`_
which *inspired*, but did not directly shape, **Sophie**'s approach to asynchronous and concurrent processing.
Every computer scientist should probably read it.

.. warning::
    This chapter is still speculative.
    It describes an incomplete, developing idea.
    Expect change.

.. contents::
    :local:
    :depth: 3

Introducing: Channels and Procedural I/O
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the beginning, an I/O operation can just be either a read or a write.

Maybe the next version of *num-guess* looks vaguely like this::

    define:
        EOL = chr(10);
        intro = ["I have chosen a random number from 1 to 100.", EOL, EOL];
        game(goal) = turn(1) where
            turn(score) = {
                send screen ["What is your guess? "];
                read keyboard;
                case val(keyboard) as guess of
                    this -> consider(int(guess));
                    nope -> { send screen ["I didn't grok that number.", EOL]; turn(score) };
                esac
            } where
                consider(guess:number) = case
                    when guess > goal then { send screen ['Too high. Try a lower number.', EOL]; turn(score+1) };
                    when guess < goal then { send screen ['Too low. Try a higher number.', EOL]; turn(score+1) };
                    else { send screen ["You win after ", str(score), " guesses!", EOL]; stop };
                esac;
            end turn;
        end game;
    begin:
        { send screen intro; read random; game(int(random*100)+1) };

Here, I'm assuming the existence of some ambient channels called ``keyboard``, ``screen``, and ``random``.
Probably eventually the *ambiance* will be restricted to the ``begin:`` block, but that's a problem for another day.

We get some new syntax forms. Here's some EBNF::

    procedure -> expression | '{' semicolon_list(command) expression '}'
    command -> READ name | SEND name expression

and in various places in the grammar, *expression* must be replaced by *procedure* instead.

The semantics are as follows:

STOP
    The *literal* stopped process. Has type *procedure.*
    Like all **Sophie** keywords, case is not significant.

READ name
    Reads a value from the given channel, binds the name, and evaluates the right hand side.
    Waits as long as necessary for such a value to become available.
    Block scope and shadowing apply.

SEND name expression
    Writes the expression to the named channel.
    Waits as long as necessary for a corresponding reader to appear.
    Then proceeds to the right.

{ ... }
    For simplicity and consistency, let's keep deterministic I/O operations inside braces.
    It eliminates visual confusion about the semicolon.
    The result of the procedure-expression is that of the expression it ends with.

Other Alternatives
---------------------------

* I originally tried copying the ``?`` and ``!`` notation from the CSP paper.
  It quickly got out of hand. It's furthermore a bit at odds with the larger **Sophie** pattern
  of using keywords instead of cryptic symbols. I'll grant that these symbols have gained
  traction among certain subcultures, but they're far from universally recognized.
  Furthermore, the keyword-commands seem easier to parse and easier to extend with more powers later.

* I have been back and forth on whether the expression at the end of a command-sequence ought to
  be inside or outside the curly brackets.

* The curly brackets are not *strictly* necessary,
  but without them I'd have semicolons meaning different things in what's *visually* the same scope.
  I could go with some other connective after I/O commands, but not many suggest themselves.


Non-Determinism
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let there be some sort of syntax form where the semantics are to multiplex amongst several possible continuations.
Each is the combination of a I/O channel operation, followed by a resulting expression,
which becomes the value of the operator *if* the particular I/O happens first.

For example, consider a process that copies input from keyboard to screen until an alarm rings.
Probably this could look like::

    define:
        foo = case of
            read keyboard -> { send screen [keyboard, EOL]; foo };
            read alarm -> stop;
        esac;

Here's some more EBNF::

    expression -> ..... | nondeterministic_choice
    nondeterministic_choice -> CASE OF semicolon_list(guarded_command) ESAC
    guarded_command -> command '->' expression

Many sources propose a way to switch individual clauses on and off by boolean tests.
In my notation, it might look like::

    guarded_command -> command WHEN expression '->' expression

Maybe a future version of **Sophie** might consider this form of expression,
but for now it's just an extra complication I'll try to live without.

Non-Termination
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Contemplate::

    define:
        copy = {read keyboard; send screen [keyboard, EOL]; copy};

This defines a non-stop copying process that just reads a line, prints a line, and repeats.
There is a small problem here: ``copy`` has no "base case" (termination condition).
That means it has no particular result-type. The present type-checker would call that an error.
In fact this function is precisely designed to run forever, or at least until interrupted by a higher power.
*(Or a loss of power, for that matter.)*

The obvious temptation here is to blindly copy the CSP paper and declare a
repetition construct like ``*{ ... }`` but what about mutual recursion?
An non-terminating state machine needs to work just as well as one that can quit.

I think it's probably fair to make some adjustments to the type system based on the I/O commands.
A recursive call with no *necessary* I/O should still have a problematic type,
but a recursive call that *must* first perform I/O has a less-problematic type.

The tricky bit is that *bottom* is no longer quite the same.
Specifically: ``IO union bottom`` should still be ``bottom`` because
there may remain a path to a CPU-bound infinite loop.
But the syntax forms that represent communication should convert ``bottom`` back to ``IO``.

.. note::
    It *may* be smarter in this instance to make some clear declaration that the function is not expected to finish.
    And perhaps that declaration belongs at the call-site that creates the function.
    I still haven't even decided how channels come into being yet.

Beyond that, I don't want an IO monad in the Haskell sense.
All functions are inherently and implicitly asynchronous-as-needed.
You can call communication a side-effect, but sometimes it's the proper way to compute a thing.
I believe once there's control over the visibility of channels,
the right things will fall out naturally.

Open Questions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Where do channels come from in the first place?
    One idea is a new kind of IO command to create new channels.

Where shall we get them from?
    I presume it shall be possible to pass channels around as ordinary parameters to functions.
    As for services that a module might provide (such as the random number generator),
    I haven't decided yet.

How shall channels get their types?
    The glib answer is to suppose that writers type the channel by the data they write,
    but a channel could route all over the place. We need something of a contract here.
    It's probably best if channels are manufactured with an obvious data type.
    However, it may be necessary to absorb the type of some other expression in scope.
    This would be important for generic operations.

How shall we snap sub-processes together and make larger processes?
    Dunno. Probably make channels and pass them to functions.
    But that last part seems ... dubiously sequential.
    More syntax *may* be required.

What about arrays of processes, or of channels?
    Dunno.

Returning a result?
    I plan that a process / procedure will be able to return a value in the usual sense.
    This may seem to violate the no-side-effects law of lazy functional programming,
    but I think it will work out OK.

What about joining the results of several processes?
    Scatter/gather behavior is still an open question.
