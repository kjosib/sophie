Learn Sophie (by Example)
=========================================

Welcome, and thank you for taking the time to learn Sophie.
She's a little different from what the average coding boot-camps are teaching these days,
but *vive la différence!* I hope she gives you a new perspective on CS.

.. contents::
	:depth: 2

Initial Preparations
---------------------

Sophie is first and foremost a language for expressing ideas about computations that might happen.
That means you can write *and reason about* Sophie programs without any computer.
Sophie is meant to be suitable for the blackboard or publication in a magazine.
There are no special formatting requirements.

But if you'd like to put your computer up to the task of evaluating (executing, running) Sophie programs,
you'll need an interpreter. You can get one easily enough:
Follow the directions at :doc:`quick_start` and then come back here.

Your First Program in Sophie
------------------------------

Virtually every programming tutorial starts the same way::

    begin:
        "Hello, World!";
        "All done here.";
    end.

If you followed directions earlier, you already have a copy of this program at ``examples/hello_world.sg``.

Now suppose you're at a command-prompt_ and you've set the current-directory_ to wherever you extracted Sophie.
If you then run::

    py -m sophie examples/hello_world.sg

you will see::

    Hello, World!
    All done here.

Let's break this down:

* Sophie programs are files.
* The main program begins with the phrase ``begin:``.
* Next comes a sequence of steps. Sophie follows those steps, one after another:
    * Each step is an *expression* of some value.
    * Sophie computes the value of that expression, and then displays the result.
    * Here we've only seen one kind of expression (the humble ``string``) but there are other kinds to handle all of computing.
    * If that expression should happen to be a ``drawing``, then the display is graphical. Sophie supports something called "Turtle Graphics". Deets later.
* Finally, every Sophie program ends with the phrase ``end.`` with a period.
    * Why? Because it looks nice in print.
* At the moment, Sophie is implemented as a Python program.
    * So in general, you will invoke ``py -m sophie`` followed by the pathname_ to your program.
    * Some day, this may change. If you'd like to help that along, let's talk about something called *self-hosting*.


Super-Fancy Calculator
--------------------------

This section starts with  Here's a small excerpt::

    begin:
        3 + 4 * 5;            # Precedence works like you learned in school.
        ( 3 + 4 ) * 5;        # You can always override that with parentheses
        sqrt(1+1);            # A number of mathematical functions and constants are built-in.
    end.

You can't miss the explanatory text on each line.
Sophie sees the ``#`` mark and concludes that the remainder of that line is a comment.
(This is a fairly typical convention.)
Comments are great for telling *people* about your code, for Sophie ignores them.

Let's break down the meaning of each expression, line-by-line:

* ``3 + 4 * 5``: Produces ``23`` because multiplication comes before addition.
* ``( 3 + 4 ) * 5``: Produces ``35`` because parenthesis.
* ``sqrt(1+1)``: Produces ``1.4142135623730951``.
  The name ``sqrt`` refers to a pre-defined function which computes the square-root of what you give it.
  This expression means to apply the number ``2`` to the function called ``sqrt`` and use the result.
  Some functions take more than one input value: just put a comma (``,``) between each parameter.

You can see more examples in the ``some_arithmetic.sg`` example file.

Define your own!
------------------

Functions are the backbone of programming.
Indeed, all of computing amounts to evaluating functions of varying complexity.
So it's time to talk about how to make and use them.

The usual standard explanation would begin something like this::

    define:
        double(x) = x + x;
        square(x) = x * x;
        area_of_rectangle(length, width) = length * width;
        five = 5;
    begin:
        double(five);          # 10
        square(five);           # 25
        double(square(five));    # 50
        square(double(five));     # 100
        area_of_rectangle(20, 30)  # 600
    end.
    
We have here a simple Sophie program that defines three functions, called ``double``, ``square``, and ``area_of_rectangle``.
It also defines a constant, called ``five``, which conveniently enough refers to the number ``5``.

Let's break this down:

* In Sophie, the definitions of functions (and constants) go in a section introduced with ``define:``.
* In this program, the names ``x``, ``length``, and ``width`` serve as *formal parameters*.
  That means the ``x`` in  ``double(x)`` is a place-holder for whatever other actual value.
  Same for ``length`` and ``width`` in ``area_of_rectangle``.
* When you want to write a function of more than one parameter, separate them by a comma.
* You can, of course, refer to functions from within functions.

.. admonition:: Names are Important

    Consider the implications if ``five`` were instead called ``six`` in a large program:
    People might look at the word *six* and mistakenly guess that it would mean ``6``,
    as it *would* in a sane world.

    This sort of treachery is typically called *unmaintainable* by those in the business,
    but I have a better word for it: *unethical*. Don't do it.
    Pick names that evoke the proper meaning.
    If the meaning is abstract, pick an abstract name.
    The most abstract names of all are single letters near the end of the alphabet.

More Fun with Functions
-------------------------

You can do quite a bit with functions.
Consider this example::

    define:
        iterate_four_times(fn, x) = fn( fn( fn( fn( x ) ) ) );

        root(square) = iterate_four_times(newton, 1) where
            newton(guess) = (guess + square/guess) / 2;
        end root;

    begin:
        root(2);   # 1.4142135623746899 -- good to 13 digits!
    # Exact value is 1.4142135623730951

        root(17);  # 4.126106627581331 -- Only the first three digits are correct,
    # Exact value is 4.123105625617661 -- but it's all downhill from there.
    end.


This program illustrates Isaac Newton's method for figuring square-roots.
The method achieves excellent accuracy after just a few steps if you start with a decent guess.
(Start with a bad guess, and it takes a few extra steps. Selecting good guesses is a topic for another time.)

Once again, let's study the bits.

* ``iterate_four_times`` is a function which *takes a function* as one of its parameters.
  The *body expression* is to call that function on the result of... well, you get the point.
  (One convention to make this scenario clear is visible in how the parameters are named:
  ``fn`` is commonly the name of a function. Similarly, ``x`` is often a number.)

* The first key point about ``root`` is the ``where`` clause.
  It allows you nest functions within functions (within functions... etc.).
  In this case, ``newton`` is defined within ``root``.
  That's useful for two things:

  * First, it hides the internals. If ``newton`` is only relevant to ``root``,
    then only ``root`` needs to see ``newton``. This is a good way to limit the amount
    of information you need to keep in your head at once.

  * Second, it allows ``newton`` to see values that only exist within the context of ``root``.
    Specifically, ``newton`` can use the value of ``square`` even when ``iterate_four_times`` calls it.
    This phenomenon is called *closure*.


Making Decisions
--------------------

Introduce the conditional forms.


.. _pathname: https://www.google.com/search?q=define+pathname
.. _command-prompt: https://www.google.com/search?q=define+command+prompt
.. _current-directory: https://www.google.com/search?q=define+current%20directory
