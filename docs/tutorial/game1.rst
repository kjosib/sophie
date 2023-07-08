Let's Play a Text Game!
~~~~~~~~~~~~~~~~~~~~~~~~

.. contents::
   :local:
   :depth: 3

Sophie can hold an interactive conversation::

    D:\GitHub\sophie\examples\games>sophie guess_the_number.sg
    I have chosen a random number from 1 to 100.

    What is your guess? 50
    Too high. Try a lower number.
    What is your guess? 25
    Too low. Try a higher number.
    What is your guess? 37
    Too low. Try a higher number.
    What is your guess? 45
    You win after 4 guesses!

You can find the code for the game under ``examples/games/guess_the_number.sg``, 
or it's copied in full toward the end of this chapter.

Guided Tour of the Game
------------------------

Introducing the Console
........................

The main program gives an introduction and then begins a game with a random number.
Here's an excerpt for that part::

    define:
        intro = ["I have chosen a random number from 1 to 100.", EOL, EOL];
        game(r) = turn(1) where
            goal = int(r*100)+1;
            ...
        ...
    begin:
        console ! echo(intro);
        console ! random(game);

Already we see a few new concepts at work.
Let's work through this part from the bottom up.

``console``
    This game uses the keyboard and text screen,
    called the *console* by ancient tradition,
    so that is the word Sophie defines for the purpose.

    The ``console`` is considered a separate entity from your program.
    You might call it an *actor* but then the programming-language theorists would yell at me.
    So let's call it an *agent* instead. You can send an agent a message,
    and the agent can do something in response whenever the message arrives.
    Your program will not stop to wait for that response, but will continue computing.
    This is what is meant by "asynchronous message-passing".

    Syntax such as ``console ! echo(intro)`` means to send the message ``echo``,
    with single argument ``intro``, to the agent called ``console``.
    And to be clear, it means the *idea* of that action.

Actions are values.
    You can pass them around to functions, hold them in data structures,
    and select among them as you would with any other kind of value.
    The only way an action actually *gets done* is when an expression in the ``begin:`` section
    evaluates to an action.

``echo``
    The ``echo`` message asks the console to print some text.
    The text here is a list of strings.
    The reason ``echo`` takes a list rather than single string is applied laziness:
    You'll often print several things together, such as some text and the ``EOL`` or end-of-line.
    It's best by far if each distinct message expresses a single complete idea.
    (Violating this principle can lead to trouble down the line.)

``random``
    The ``random`` message asks the console to:
    
    1.  Pick a real number at random in the half-open range [0, 1).
    2.  Send that number to by way of ``random``'s own argument.

    In this example, that means ``game`` gets the number.
    As you can see, ``game`` is just a function of one argument.
    What may be less obvious here is that ``game`` is also expected
    evaluate to some action of its own, but that's just how ``random``
    uses its argument. It's not baked into the idea of message-passing.

Asking for Input: Sequence
...........................

The ``turn`` function is the main loop of the game.
It's job is to prompt for a guess and then interpret that guess as either too high, too low, or just right::

    game(r) = turn(1) where
        goal = int(r*100)+1;
        turn(score) = do
            console ! echo ["What is your guess? "];
            console ! read(guess);
        end where
        ...
    ...

When it's the player's turn, we need to

1. ask our question, and
2. get an answer.

You can put a sequence of actions between ``do`` and ``end`` as shown here.
That creates a single larger action.
In this case, we have another ``echo`` and this time a ``read`` message.

* Just like with function calls, you don't need parenthesis around a list if it's the only argument to a message.
  The square brackets of the list itself are enough to make yourself clear.
* The ``read`` message means to wait for a line of input text (ending with the 'enter' or 'return' key)
  and forward that on in similar manner to how ``random`` sent along a number.
  Naturally, ``read`` sends you a string because the player can type anything at all, not just numbers.
* Speaking of ``random``: the ``goal`` sub-function provides our number scaled up to between 1 and 100 inclusive,
  as promised in the introduction. The multiplication and addition should be self-explanatory.
  To get rid of any remaining fractional part, we apply the ``int`` function as shown here.


Analyzing Input: Selection
...........................

Evidently, ``guess`` must analyze the input. Before we worry about comparing the guess to the goal,
there's another important possibility. The player might enter something which is not a number::

        guess(g) = case val(g) as v of
            this -> consider(int(v.item));
            nope -> do
                console ! echo ["I didn't grok that number.", EOL];
                turn(score);
            end;
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

Finally, notice how in the ``nope ->`` section, the action ends with ``turn(score)``.
This decision says we do not charge the player a guess for having fat-fingered her number.

Evaluating a Guess
...................

Now let's see what happens if the input actually *is* a number::

        consider(g:number) = case
            when g > goal then go_again('Too high. Try a lower number.');
            when g < goal then go_again('Too low. Try a higher number.');
            else win;
        esac;
        
This function ``consider`` is probably about what you'd expect.
Unsurprising code is virtuous code. But we do have two more words to define::
        
        go_again(text) = do console ! echo [text, EOL]; turn(score+1); end;
        win = console ! echo ["You win after ", str(score), " guesses!", EOL];

Things of particular interest here:

* In contrast to the *not-a-number* case, when the player guesses wrong,
  the subsequent ``turn`` operates with the next higher score.
* ``go_again`` crams multiple actions on one line. This can get hard to read. Use your discretion.
* The ``str`` function turns a number into a string. That helps here because in Sophie,
  the members of any given list are all the same type of thing as each other.
* Notice the blank spaces after ``after`` and before ``guesses``.
  If they were absent, then you might see something like ``You win after4guesses!`` in the output.
  That would be hard to read. The point is that **Sophie** takes you *exactly* at your word,
  and does not blithely insert spaces between bits of what you ``echo``.

The Full Game
------------------

Without further ado, here's the completed game:

.. literalinclude:: ../../examples/games/guess_the_number.sg

Concluding Remarks
-------------------


In principle, you now have what it takes to make a wide variety of interactive programs.
In practice, it will take practice!

Also in practice, **Sophie** will benefit from a greater variety of interactive capabilities.
These new abilities will come in time.