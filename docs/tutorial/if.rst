Making Decisions (Conditional Forms)
=========================================

.. contents::
	:local:
	:depth: 3



So far, we've seen arithmetic and how to use functions, but no way to decide between options.
Let's fix that.
Sophie has three of what we call *conditional forms,* or ways to represent decision-points in a program.
I'll cover the first two of these here, and the last in the section about data structures.

Case Study: Age Classifier
---------------------------
Here's an example of a not-always-totally-respectful age-classifier:

.. literalinclude:: ../../examples/tutorial/case_when.sg

The ``case`` - ``when`` - ``then`` - ``else`` - ``esac`` structure
represents a multi-way decision.
You might not agree with the precise thresholds or translations,
but what's going on should be pretty clear.
Sophie looks for the first ``when`` clause that is true in context,
and evaluates the corresponding ``then`` clause.
If no ``when`` clause is true, then Sophie evaluates the ``else`` clause instead.

	And what about that funny word ``esac``? Well, it's ``case`` spelled backwards.
	It makes for a nice symmetric open-and-close, sort of like parentheses.
	We could probably live without it for this particular structure
	because ``else`` is always last here,
	but Sophie uses the word ``case`` in a couple other ways where clear
	containment is less obvious without the closing bracket.
	So this is a nod to consistency,
	which will make for easier composition and reading.

* Exercise:
	Observe that this demo calls the ``age`` function with a few different
	sample arguments ``1``, ``10``, and ``100``. Think about what result you expect
	in each of these scenarios, and why that is the result you expect.

* Exercise:
    We haven't yet seen the ``map`` function. Based on how it's used here,
    what do you suppose it might do?

* Exercise:
	Actually run the example code.
	See how things line up with your expectations.

* Exercise:
	Try mixing up the order in which the ``when`` ... ``then`` clauses appear.
	What happens?
	Can you adjust the ``when`` conditions to make them work properly regardless of the order in which they appear?

* Exercise:
	Can you think of a way for Sophie to check for overlap between the conditions?
	If so, how does your idea change when the conditions get more complicated?

Case Study: Improved Root-Finder
-----------------------------------

Let's improve our root-finding program.
You may have noticed that it did significantly better with ``root(2)`` than with ``root(17)``.
To get a better answer for larger numbers, one approach we could take is to iterate Newton's method more times.
We could do this:


.. literalinclude:: ../../examples/mathematics/Newton_2.sg

..

    For the record, ``sqrt`` is the built-in math function for taking square-roots,
    so that's convenient for testing against.

In this example, I've added two more rounds of Newton's Method (and renamed a certain function accordingly).
Even still, it's not enough.
Feed a big enough number into the ``root(...)`` function and it stops too soon.

	Of note, you can have underscores in numbers
	like ``123_465.789_012`` and you can group them as you like,
	so long as there is a digit on both sides of every underscore.

It would be nice if we could let Sophie figure out when to stop.
Perhaps we come up with a function like this:

.. literalinclude:: ../../examples/mathematics/Newton_3.sg

Success! But ... What just happened? There's a lot going on in this case-study.

1. | The body-expression of ``iterated`` shows the first of the conditional forms:
   |    *expression-1* ``if`` *test* ``else`` *expression-2*.

2. So-called *where-clauses* can have as many definitions as you like.
   The main ``root`` function defines two sub-functions in this manner.

3. You can nest sub-functions as deeply as you like.
   The function ``good_enough`` is within ``iterated``, which itself is within ``root``.

4. In the function ``good_enough``, we meet `scientific notation`_.
   ``1e-14`` is one over ten trillion, or a very *very* small number for most practical purposes.

5. The built-in function ``fabs`` stands for "absolute-value of" and is effectively ``fabs(x) = x if x >= 0 else -x``,
   but in native code. The ``f`` in ``fabs`` comes from a historical accident, and I will probably remove it
   from a near-future version of the interpreter.

6. This illustrates a design technique: The function ``iterated(x, y)`` does most of the work,
   and is `recursive`_ with two parameters. So the outer function ``root(square)`` must
   provide an initial set of values for those parameters.

   When you write a recursive algorithm, you should spend a moment to convince yourself that it always terminates.
   In our case, Isaac Newton has already done most of the work four hundred years ago,
   as long as you start with a positive number.
   It might not go so well if you feed in a negative number, but that's a topic for a bit later on.

7. There are limits to the precision of numerical operations in computers.
   The built-in ``sqrt`` can determine square-roots to slightly more precision in a single operation
   than what we can accomplish with several separate operations. (It's also much faster.)

.. _scientific notation: https://en.wikipedia.org/wiki/Scientific_notation#E_notation
.. _recursive: https://en.wikipedia.org/wiki/Recursion_(computer_science)

..

    Normally, it's best to use the standard-library functions rather than re-build from scratch.
    But then again, normally you'll already know how to use the langauge.
    This exercise is just practice for learning the concepts.

Wrapping Up
--------------

We have seen how to do multi-way selection based on conditions,
and we have seen a short-cut notation when there are only two options.
Internally, they both translate to the same form (and it resembles the "short-cut").
One or the other syntax will more or less represent how you think about
any given decision point.
