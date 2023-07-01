Let's Play a Game!
~~~~~~~~~~~~~~~~~~~

.. contents::
   :local:
   :depth: 3

Sophie can hold an interactive conversation::

    D:\GitHub\sophie>sophie examples\games\guess_the_number.sg
    I have chosen a random number from 1 to 100.

    What is your guess? 50
    Too high. Try a lower number.
    What is your guess? 25
    Too low. Try a higher number.
    What is your guess? 37
    Too low. Try a higher number.
    What is your guess? 45
    You win after 4 guesses!

You can find the code for the game under ``examples/games/guess_the_number.sg``, but here it is:

.. literalinclude:: ../../examples/games/guess_the_number.sg

Guided Tour of the Game
------------------------

Preliminaries
...............

Let's take a guided tour.
We'll start at the top::

    import:
        sys."teletype" (done, echo, read, random);

You can think of ``done, echo, read, random`` as four kinds of action a text-based game might take.
Actually, this might be a good time to have a glance at
`the teletype module. <https://github.com/kjosib/sophie/blob/main/sophie/sys/teletype.sg>`_
Mainly it just defines those four words as subtypes of ``action``.
(It also performs a special kind of import you can learn more about :doc:`elsewhere <../ref/ffi>`.)

The Main Idea
................

The main program gives an introduction and then begins a game with a random number.
Here's an excerpt for that part::

    define:
        EOL = chr(10);
        intro = ["I have chosen a random number from 1 to 100.", EOL, EOL];
        game(r) = turn(1) where
            goal = int(r*100)+1;
            ...
        ...
    begin:
        echo(intro, random(game));

* The expression ``chr(10)`` refers to the "newline" character.
* The ``echo`` action prints text, then invokes the subsequent action.
  The text here is a list of strings. It's a list, rather than single string, for ... reasons.
* The ``random`` action picks a real number at least zero, but less than one, which gets passed to ``game`` here.
* The ``goal`` function scales that number up to between 1 and 100 inclusive.
  Here, the ``int`` function takes a real number and converts it to an integer by dropping the fractional part.

The ``turn`` function is responsible for most of the game.
It's job is to prompt for a guess and then interpret that guess as either too high, too low, or just right::

        turn(score) = echo(["What is your guess? "], read(guess)) where
            ...

* The ``read`` action takes one line of input from the player and passes it to, in this case, ``guess``.

Analyzing Input
................

Evidently, ``guess`` must analyze the input. Before we worry about comparing the guess to the goal,
there's another important possibility. The player might enter something which is not a number::

            guess(g) = case val(g) as v of
                this -> consider(int(v.item));
                nope -> echo(["I didn't grok that number.", EOL], turn(score));
            esac;

The ``val`` function turns a string into a number. Or rather, it *tries* to do that.
Not all strings make sense as numbers. So actually, the ``val`` function returns something
called ``maybe[number]``.

What's ``maybe`` about? Quite simply, ``maybe`` is about things that might or might not have an answer.
What's the number corresponding to ``"California"``? The answer to that question is ``nope``.

Notice also the ``as v`` in the top of the ``case`` expression. That is the closest thing **Sophie** has
to assignment. Within the boundaries of the ``case`` expression, ``v`` here means the value of ``val(g)``.
And that's how we're able to use ``v.item`` on the second line and *for sure* have a number at this point.

.. note::
    Personally, I consider it a bit wordy to have to say ``v.item`` instead of just ``v``.
    At some point I plan to change it, but that will take some nontrivial work.

Finally, notice how in the ``nope ->`` section, the result includes a call back to ``turn(score)``.
This decision says we do not charge the player a guess for having fat-fingered her number.

Evaluating a Guess
...................

Now let's see what happens if the input actually *is* a number::

            consider(g:number) = case
                when g > goal then echo(['Too high. Try a lower number.', EOL], turn(score+1));
                when g < goal then echo(['Too low. Try a higher number.', EOL], turn(score+1));
                else echo(["You win after ", str(score), " guesses!", EOL], done);
            esac;

By now, this should be easy reading. Things of particular interest here:

* When ``g < goal`` or ``g > goal``, and in contrast to the *not-a-number* case,
  the subsequent turn operates with the next higher score.
* The ``str`` function turns a number into a string.
* Notice the blank spaces after ``after`` and before ``guesses``.
  If they were absent, then you might see something like ``You win after4guesses!`` in the output.
  That would be hard to read. The point is that **Sophie** takes you *exactly* at your word,
  and does not casually insert spaces between bits of what you ``echo``.

Concluding Remarks
-------------------


In principle, you now have what it takes to make a wide variety of interactive programs.
In practice, it will take practice!

Also in practice, **Sophie** will benefit from a greater variety of interactive capabilities.
These new abilities will come in time.