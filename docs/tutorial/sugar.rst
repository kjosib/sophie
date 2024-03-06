Syntactic Sugar
################

.. contents::
   :local:
   :depth: 3

Anonymous Functions
====================

Sophie code frequently passes functions around as parameters to other functions.
The canonical examples are ``map``, ``reduce``, and ``filter``.
Each of these take another function. Often that other function is trivial.
Sophie now lets you sidestep the ceremony of inventing names for trivialities.

In March of 2024, Sophie gets *anonymous function* expressions.
Many programmers call these "lambda forms".

The syntax looks like ``{`` *parameters* ``|`` *expression* ``}``.

Examples:
    if you need a list of numbers raised to the third power, you could write::

        cubes = map( {x|x^3}, iota(0, 10) );

    You could write ``sum`` as::

        my_sum(xs) = reduce( {a,b|a+b}, 0, xs);

