Devilish Details to Determine
==============================

The Python and C run-times behave slightly differently.
That's not intentional so much as happenstance on account of
difference in how the underlying platforms do things.

.. contents::
    :local:
    :depth: 2


The Negative Modulus
----------------------

Consider an expression like ``A mod B``.
When ``A`` and ``B`` are both positive, there is no controversy.
But when ``A`` or ``B`` or both are negative, there are problems.

There's a good argument why ``A mod B`` should always have the sign of ``B``:
Applications of the ``mod`` operator tend to be about modular arithmetic in the
same sense mathematicians model, which requires ``0`` <= ``A mod B`` < ``B``,
and in general ``B`` will be positive.
If for some reason ``B`` is negative, then we can reverse the inequality to match.

C's ``fmod`` function retains the sign of ``A``.
The argument goes that a small negative number, modulo a large number (regardless of sign),
can either be a number of large magnitude that loses precision due to the foibles of floating point,
or a small negative number that *exactly* represents the correct answer.
So if you value exactness in corner cases over practical utility in general,
then you'll appreciate the C approach.

I think there's greater practical utility in the first approach,
so that's what the operator will do even though it does mean extra work.
If you are desperately worried about the potential loss of precision
around very large and very small numbers,
then you can use the ``fmod`` function instead of the operator.

Parsing Numbers
----------------

Python expects the entire (trimmed) string to represent a floating point number.
C allows junk after the number, and also allows binary or hexadecimal floating point.

The C approach seems like a "because we could" answer.
The better answer is probably to reflect Sophie's own number
syntax in the basic number conversion utility function ``val``,
and to provide for alternatives on request.

Random Numbers
---------------

Out of the box, C provides no excellent way to generate random numbers.
The standard ``rand()`` function will do in a pinch for simple games,
but soon I'd rather see something with better statistical properties.

Apparently the recent C++ standard calls for a handful of nice generators.
But I'm not using C++. I may end up using something simple from the 
