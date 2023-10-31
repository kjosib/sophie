Strictness and Volatility
#########################

.. contents::
    :local:
    :depth: 2

Overview
===========

Sophie sports the semantics of "lazy evaluation" rather than "eager evaluation".
That's a *semantic* distinction because it changes the set of programs which terminate.
In particular, more functions can terminate with lazy semantics.
Taking advantage of this makes many algorithms easier to write.
On the other hand, references to the internal private state of an actor
must be evaluated *immediately* thus to prevent data races.

Corresponding to the different semantics are two equally-different implementation strategies.
These are *call-by-need* and *call-by-value*.

As implementation strategies go, call-by-value is normally the more efficient *when it is acceptable.*
Therefore, it behooves the diligent implementer to produce call-by-value code sequences whenever
possible without changing the meaning of the program.


Volatility: Stricture's Dual
==============================

Certain expressions refer to the current state of an actor. These must not be made into thunks,
as their values could change before they get forced. (That would be a pernicious data race.)
Therefore, any expression which contains a reference to current-state is considered "volatile".
The rule is to never create a volatile thunk. You have to evaluate the sub-expression instead.

The phrase ``self`` is not volatile, but a *FieldReference* containing ``self`` would be volatile.
And then any expression with a volatile component is itself volatile.
This is straightforward to compute, since it's basically a bottom-up tree transduction.
It's also critical for correctness of the thready parts.


Strictness, Inductively Defined
=================================

Let's consider strict parameters vs. non-strict parameters to some given function ``F(a,b)``.

Suppose it can be shown that evaluating ``F`` *necessarily* forces the value of ``a``.
In that case, we can say that ``F`` is *strict in* parameter ``a``.
So for any call-site referring specifically to function ``F``,
we may as well evaluate the actual ``a`` eagerly.

On the other hand, suppose that ``F`` only *sometimes* uses the value of ``b``,
perhaps depending on the value of ``a``. In that case, ``F`` is *non-strict* in ``b``.
Now the question becomes whether it is safe and quick to compute ``b`` in advance.
But let's keep it simple for now and just call ``b`` a lazy parameter.

The minimal solution to strictness-analysis would be the transitive closure of this line of reasoning.

Strictness as a dataflow problem
---------------------------------

Finding Strictness
....................
We can determine a *greatest lower bound* on strictness by walking the syntax tree.
Top-down, expressions are either strict or lazy according to form and what's known so far.
Bottom-up, parameters are strict if they get used in a strict position.

As a base case, certain expressions are *formally* in strict position.
These include the *if-part* of a conditional form, the left-hand-side of a logical connective,
and any argument to mathematical operator. Also, the *function* part of a function call,
the subject of any match-case, and any arguments to *known-strict* parameters of a known function.

* For branching forms, take the intersection of the sets from the alternatives,
  and then union that with the set from the condition.
* For function calls, take the union of sets for each known-strict argument,
  and then union with the head-form (i.e. which function to call).
* For short-cut logical operators, the left-hand side is strict.

If the set of strict arguments is found to be larger than the prior estimate,
then reconsider its callers, as they may suddenly become stricter too.
There may be a clever solution involving work-queues.

Nested sub-functions can also be strict in lexical captures.
To deal with this: If a sub-function is called in strict position,
then add its strict captures to the locally-strict set.

The data model for this exercise is that every concrete function has a set of strict formal
parameters and a set of strict captures.
Parameters used as functions are assumed to have lazy arguments.

Perhaps one day some deeper analysis can prove strictness sound in more cases.
But for now, the goal is something that works as expected all the time,
even if that means sacrificing a few percentage points on the speedometer.

Eagerness, Inductively Defined
================================

Certain syntax forms can never *return* thunks. Among these are literal constants,
the names of constructors, the results of arithmetic, and certain other things.
If a function's body-expression falls into one of these categories,
than the function has an eager return-type.
Calling such a function is thus also an eager expression.


Over-Eagerness
================

There are ways to crank the knobs even more towards the eager-evaluation end of the scale
without losing (all of) the benefits of lazy semantics.
I'll skip out on these for the moment, but may come back to them some day.

Opportunistic Eagerness
------------------------

Suppose we compute ``b`` speculatively only when ``b``'s argument-expression is *obviously* safe.
I propose that *obvious-safety* is a property similar to data-type:
You can get precision through deeper analysis, but at the asymptote lies the halting problem.

Assuming ``b`` is deemed safe, it still wastes computation if ``b``'s value is computed but never used.
A sufficiently-smart compiler could estimate the cost of evaluating an expression,
and if that cost is below some threshold, go ahead and do the evaluation up front.
Where that threshold should be depends on probability-of-need and the relative cost of a thunk.

If the compiler decides to evaluate some ``b``-argument speculatively,
that could make the surrounding function stricter in some of its own arguments.

Higher-Order Eagerness
-----------------------

The original example assumed ``F`` was a name defined in scope.
If instead it's a formal parameter or the result of some other expression,
things get more interesting.

The easy way out is to just assume laziness.
A strict function will force its parameters in any case.
But there is another way:
Work out the strictness-signatures of possible arguments and make specialized variants of higher-order functions.
This smacks of template-expansion in C++, which runs somewhat counter to the current design goals.

Explicit Eagerness
-------------------

Some systems allow the programmer to declare parameters as expressly strict.
That's at odds with Sophie's current design goals, so I will not explore this further.

Pragmatic Eagerness
--------------------

It may be worth experimenting with compiler flags to adjust the behavior around eagerness.
If nothing else, it could provide insight into different approaches.


