Functions: How Sophie Calculates
=========================================

.. contents::
    :local:
    :depth: 3


Super-Fancy Calculator
~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's a small program showing how math (and comments) in Sophie appears:

.. literalinclude:: ../../examples/tutorial/simple_calculations.sg

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

* Exercise:
    Find the ``some_arithmetic.sg`` example file. Read it (say, in *notepad* or *textedit*)
    and run it through the Sophie interpreter.
    This should be very similar to running the ``hello_world.sg`` example.
    What does this say about how Sophie reads mathematical expressions?

.. important::
	Sophie will only run a program she can read and understand completely in advance.
	Otherwise you'll get a diagnostic message to try to help you sort out what went wrong.
	These messages are not in their final form, but they should at least pinpoint the issues.

* Exercise:
	Modify the ``some_arithmetic.sg`` example file and save your changes,
	then try to run the modified version.
	What happens if you leave out a closing parenthesis, or leave out an operator between numbers?
	Can you make sense of the diagnostic messages?

Define your own!
~~~~~~~~~~~~~~~~~~

Functions are the backbone of programming.
Indeed, all of computing amounts to evaluating functions of varying complexity.
So it's time to talk about how to make and use them.

The usual standard explanation would begin something like this:

.. literalinclude:: ../../examples/tutorial/define_functions.sg

We have here a simple Sophie program that defines three functions, called ``double``, ``square``, and ``area_of_rectangle``.
It also defines a constant, called ``five``, which conveniently enough refers to the number ``5``.

If you're curious (and I hope you are) you can run it like::

	D:\GitHub\sophie>py -m sophie examples\tutorial\define_functions.sg
	10
	25
	50
	100
	600

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
~~~~~~~~~~~~~~~~~~~~~~~~~

You can do quite a bit with functions.
Consider this example:

.. literalinclude:: ../../examples/mathematics/Newton.sg

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
