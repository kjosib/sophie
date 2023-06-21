Fantastic Lists and Where to Find Them
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. contents::
	:local:
	:depth: 3


So far, almost all the data in the tutorial has been numbers,
with the occasional bit of text (what programmers often call "strings" for historical reasons).
In the small, most things do boil down to letters and numbers,
but we're often interested in treating coherent groups of information as a unit.
In other words, we want structured data.

Sophie provides two primary data structuring conventions: records and variants.

Case Study: Music Archive
--------------------------

Suppose you're going to write some code that deals with a library of music.
You might end up with some type definitions like this::

	type:
	year is number;
	track is (title:string, artist:string, published:year, recorded:year);
	album is (title:string, published:year, tracks:list[track]);

Line by line:

1. The ``type:`` section goes before any ``define:`` or ``begin:`` section.
2. The word ``year`` is made a synonym for ``number``.
3. Next, ``track`` is defined to have a title, artist, year of publication, and year when it was recorded.
4. Finally, we define ``album`` to have its own title and year, but also a list of tracks.
   Thus, ``track`` and ``album`` are both record definitions.

Here's some sample expression of an album::

	sample = album("50 Public-Domain Songs", 2022, [
		track("After You Get What You Want, You Don't Want It", "Irving Berlin", 1925, 2021),
		track("Some of These Days", "Shelton Brooks", 1925, 2022),
	]);

	some_year = sample.published;

Notice a few things:

* Record definitions behave somewhat like functions.
  We can create an album or a track by giving arguments in the correct type and sequence.
* You can write a list of things with commas between and surrounded by square brackets.
  The syntax looks like ``[`` *element* ``,`` ... ``,`` *element* ``]``.
  If it makes life easier, you can optionally include a comma after the last element.
* An empty list is spelled ``nil``, even though we don't yet have an example here.

Lists in Sophie are sequences of all the same type of object. You can have lists of numbers,
lists of strings, lists of tracks, even lists of other lists;
but then those other lists must themselves all have the same type of entry.

So, for instance, ``[1, "apple"]`` is not a list because it contains elements of dissimilar type.

You can also make lists one element at a time, using the ``cons`` constructor.
These are two ways to write the exact same list::

	begin:
		cons(1, cons(2, cons(3, nil)));
		[1, 2, 3];
	end.

Obviously the second way is much preferable for many cases,
but when you're composing lists functionally it's handy to have the other.

Now, you might be wondering how to get at data in lists.
This is a good time to look at the code for the ``map`` built-in function::

	map(fn, xs) = case xs of
		nil -> nil;
		cons -> cons(fn(xs.head), map(fn, xs.tail));
	esac;

How to explain this? On two levels: what it does, and how it works.

* ``map`` takes a function (from type A to type B, let's say) and a ``list[A]``;
  and produces from these a ``list[B]`` by applying the function to each element in succession.

* ``map`` works by deconstructing each ``cons``, applying the function to the head, and constructing a new ``cons``.
  Naturally when it finds ``nil`` it's done.

For context, let's look at the definition of ``list``::

	list[x] is case:
		 cons(head:x, tail:list[x]);
		 nil;
	esac;

So, every ``list`` is *either* a ``cons`` or an empty-list (called ``nil``.)
We call ``cons`` and ``nil`` the two constructors of ``list``.
We *define* ``list`` with a ``case`` construction, and we *take apart* a ``list`` with a ``case`` construction.

Note that we don't *just* define ``list``. We actually define ``list[x]``.
The ``x`` is a placeholder for some other type: the element-type for any given list.
It works sort of like the argument to aa function: you can supply whatever ``x`` you need when you need it.
We go on to use ``x`` in the definition of the ``cons`` constructor.

Getting back to ``map``:
The phrase ``case xs:`` says we've got a different answer depending on which constructor ``xs`` is built with.
In the outer function body, ``xs`` is known only to be a ``list``,
but within the ``cons ->`` branch, ``xs`` certainly has the subtype of ``cons``,
so we can access ``xs.head`` and ``xs.tail`` only within that branch.

Case Study: Fibonacci Numbers
------------------------------

Everything you ever wanted to know about these numbers are at https://en.wikipedia.org/wiki/Fibonacci_number
but here's the extremely short version:

	You get an interesting *and endless* sequence of numbers by starting ``1, 1,``
	and then each next number is the sum of the two preceding ones.
	A slightly longer prefix of this sequence goes ``1, 1, 2, 3, 5, 8, 13, 21, 35,``
	but the sequence overall continues until you get tired of it.

	These numbers come up often in nature, music, art, and applied math,
	so it's handy to have a convenient way to get a list of them.

The usual mathematical definition of the Fibonacci sequence usually looks something
like ``fib(n) = 1 if n < 2 else fib(n-1) + fib(n-2);`` but that has three problems:

1. It defines the nth Fibonacci number, not the sequence of them all.
2. This style of recursive definition is rather difficult to make an efficient translation of.
   Some systems apply some clever tricks which can often help,
   but for the most part we can expect this *general category* of expression
   to require `exponential time <time_comp_>`_.
   Why? It breaks the larger problem into two smaller similar problems,
   but they are "smaller" by a only constant increment rather than a constant factor.
3. There happens to be a direct, non-recursive expression for the nth Fibonacci number.
   A text on discrete math will show you how to find such an expression.

What I'd like to do instead is define the infinite list of Fibonacci numbers,
and then have a convenient way to get a prefix of that list.
Here's one way to do it:

.. literalinclude:: ../../examples/mathematics/Fibonacci.sg

Discussion:

1. The Fibonacci sequence is something called a `linear recurrence relation <rec_rel_>`_.
   It is perhaps the simplest non-trivial one: each term is the sum of the two previous terms.
   I've captured the fact of that summation in the ``recur`` sub-function:
   it composes an infinite list.

2. The sequence specifically is that recurrence beginning with a pair of ones.
   A common pattern in the design of functions is to apply a specific set of initial conditions
   to a more generalized recursive core. We saw something similar in the design of the improved root finder, earlier.

3. An infinite list may be easy to define, but naturally you can't use the whole thing.
   You have to confine yourself to using a finite prefix of the infinite list.
   One way is the function ``take``, which is built-in to the `standard preamble`_.
   It takes a *size* (here, ``20``) and a source-list to produce a new list with at most *size* elements.
   For reference, here is the source code for ``take``::

	take(n, xs) = nil if n < 1 else case xs of
		nil -> nil;
		cons -> cons(xs.head, take(n-1, xs.tail));
	esac;

Exercises:

1. Critique the similarities and differences between how ``Fibonacci`` and ``take`` use the ``cons`` list-constructor.
2. Explain  why the ``take`` function *always* finishes. Don't just test it.
   Prove it. *(Hint:* mathematical_ induction_ *is your friend.)*
3. The `Lucas numbers`_ are similar, but they have a different starting value. Refactor this to provide both sequences.
4. The `Pell numbers`_ are again similar, but with a multiplication involved. How could you add support for these?
5. (Harder) Try composing a version of ``Fibonacci`` that takes a *size* argument and produces only that size of list,
   but without using ``take`` as a primitive.
   Now critique the mess you just made.
   How much harder was it to write, and later to read?
   Now you know why not to ever do that again.
   Instead, design and take full advantage of small composable functions.

.. _time_comp: https://en.wikipedia.org/wiki/Time_complexity
.. _rec_rel: https://en.wikipedia.org/wiki/Recurrence_relation
.. _mathematical: https://www.mathsisfun.com/algebra/mathematical-induction.html
.. _induction: https://en.wikipedia.org/wiki/Mathematical_induction
.. _Lucas numbers: https://en.wikipedia.org/wiki/Lucas_number
.. _Pell numbers: https://en.wikipedia.org/wiki/Pell_number

The built-in list-processing functions
---------------------------------------

You can read the `standard preamble`_ to see all the relevant source code,
but here's a handy list of built-in list processing functions:

* ``any`` - Given a list of yes/no values, tell if *any* of them are a yes. (For an empty list, this will be *no*.)
* ``all`` -  Given a list of yes/no values, tell if *all* of them are a yes. (For an empty list, this will be *yes*.)
* ``map`` -  Given a function and a source-list, produce a new list composed by applying the function to each element of the source list.
* ``filter`` - Given a predicate (i.e. a function returning yes or no) and a source-list, produce a new list composed of every source-list element for which the predicate is true of that element.
* ``reduce`` - Described in detail below.
* ``cat`` -  Given two lists, produce a new list containing each element of the first list, and then each element of the second list.
* ``flat`` - Given a list-of-lists, produce a single-level list consisting of all the elements of each sub-list in succession.
* ``take`` - Given a number and a source-list, produce a new list containing at most the first *number* elements of *source-list*.
* ``skip`` - Given a number and a source-list, produce only that portion of *source-list* after the first *number* elements are skipped over.

A word about ``reduce``:
	The idea here is that you have a list and you want to crush it down into a single value.
	To do this, you have a function (of two parameters) and some *initial* value.
	This function, applied to the *initial* value and the head of the list,
	produces a new *intermediate* value. We then apply your function to the *intermediate* value and the *next* element of the list,
	over and over until we run out of list-elements. At that point, whatever was the last value to be returned from your function
	is the result of ``reduce``.

	Here's an example::

		sum(xs) = reduce(add, 0, xs) where add(a,b) = a+b; end sum;

	Many authors refer to this behavior as a *fold*, evoking the image of literally folding a strip of paper over on itself many times.
	Some authors might specifically call it a *left-fold* due to its dynamic of processing the elements in the list from first to last.
	There are perhaps around a dozen commonly-encountered variants of approximately this function.
	Some expect a seed value; some take the seed from the head of the list. Some work in reverse.
	Some try to form a balanced tree of sub-list sub-folds. Some might even work in parallel across different CPU cores.
	Some reverse the arguments to the provided function. Some produce only the final result;
	others produce the list of intermediate values.

	If there's a point, it's this: There are many interesting patterns of iteration.
	Some of those patterns may well have conventional names, but they're all just variations on a simple theme.
	At the moment, Sophie is not trying to *catch them all.*
	It's easy enough to just catch the ones you need when you need them.
	Eventually, Sophie might add a library of these so-called *morphisms*.

.. _standard preamble: https://github.com/kjosib/sophie/blob/main/sophie/preamble.py
