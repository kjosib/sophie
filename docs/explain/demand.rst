Analyzing Demand / Inferring Strictness
========================================

Purpose
--------

The goal and purpose of demand analysis (or strictness inference)
is to let Sophie evaluate only those things which *must* be evaluated,
but to do so as soon as it's clear that *indeed* they must be evaluated.
This *opportunistic eagerness* results in many fewer thunks and therefore faster code.
The semantics are pretty much the same as fully-lazy evaluation.
(Code that crashes may *crash differently,* but that's not really a problem.)

How it's done
--------------

Sophie infers that a parameter is *strict* if the value of that
parameter is *definitely* necessary in order to evaluate the body of a function's expression.
This analysis is sound, but conservative and relatively simple:
It fits in less than 200 lines of code.

Each expression *strictly* demands some subset of formal parameters.
Using a formal parameter in a "strict" position demands that parameter.
Strict positions are the recursive extension (from the body expression) of:

* The left side of a short-cut logical operator
* Both sides of an arithmetic or relative operator
* The argument of a unary operator or field-access expression
* The if-part of a condition
* The subject of a type-case match
* Those argument positions of a UDF-call that have thus far been determined to be strict.
* All arguments to a foreign function.
* All arguments to what is syntactically a bound-method.
* The *function to be called* in a function-call expression.
* Within a ``do``-block, all *new_agent* expressions and each *step* expression.
* Within a task-expression, the subexpression that represents the procedure to be scheduled.

Additionally:

* Branching forms also demand the *set intersection* of whatever their alternatives demand.
* Calling a nested UDF also demands any closed-over (i.e. outer) parameters which that UDF's own expression demands.

This has the essential nature of a "least fix-point" data-flow problem.
The key organizing principle would be a graph of the statically-determined calls.
To that end, a ``DeterminedCallGraphPass`` computes that graph.
The remainder of the analysis proceeds in order of strongly-connected components, from leaves to roots.
A ``DemandPass`` refines the estimate of which parameters a function is strict in.
As usual with these problems, the ``analyze_demand`` repeatedly refines each estimate
until no member of the strongly-connected-component gets any stricter in the process.

Thanks to the magic of a non-cyclic import mechanism,
it would be feasible to analyze (first-order) demand on a module-by-module basis.
However, I'm currently doing it as a whole-program analysis after the fact.
In practice it works out the same.

By the way
-----------

To be sure, the current analysis is far from perfect.
For example, if a recursive function's base case clearly *demands* a parameter,
and if the recursive case uses that parameter in typical ways,
then chances are the parameter ought to be made strict.
But this does not yet happen. It would require a more sophisticated design.

If some function is never passed as a parameter to any other thing,
then we may be sure that all calls to it are statically-determined,
so that its strictness criteria will always be respected in calls.
Therefore, that function need not begin with "STRICT" instructions.
I'm not currently using this fact, because the impact of "STRICT"
instructions seems to be fairly small in the grand scheme of things.

One could conceive of strictness-based monomorphism.
This would automatically call different versions of higher-order functions
depending on different strictures of the functional-parameters.
Such higher-order demand analysis might yield faster code,
but it would require significant gymnastics,
and chances are it's a minimal improvement over the basic analysis.

It will remain possible to *expressly* annotate a parameter as ``strict``.
An example use-case is the ``reduce`` function's *accumulator* parameter.
This must be strict to avoid building a gargantuan tower of thunks
which the run-time then cannot evaluate due to stack overflow,
but the accumulator is never used in an obviously-strict position.
