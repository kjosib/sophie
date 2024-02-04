Analyzing Demand / Inferring Strictness
========================================

.. note:: This is a plan. It will probably happen soon.

The goal and purpose of demand analysis (or strictness inference)
is to let Sophie evaluate only those things which *must* be evaluated,
but to do so as soon as it's clear that *indeed* they must be evaluated.
This *opportunistic eagerness* results in many fewer thunks and therefore faster code.

Sophie should infer a parameter should be *strict* if the value of that
parameter is *definitely* necessary in order to evaluate the body of a function's expression.
This is approximately a mutually-recursive relationship.

An expression *strictly* demands some subset of formal parameters.
Using a formal parameter in a "strict" position demands that parameter.
Strict positions are the recursive extension (from the body expression) of:

* The left side of a short-cut logical operator
* Both sides of an arithmetic or relative operator
* The if-part of a condition
* The subject of a type-case match
* Those argument positions of a UDF-call that have thus far been determined to be strict.
* All arguments to what is syntactically a bound-method.
* The *function to be called* in a function-call expression.
* Within a ``do``-block, all *new_agent* expressions and each *step* expression.
* Within a task-expression, the subexpression that represents the procedure to be scheduled.

Additionally:

* Branching forms also demand the *set intersection* of whatever their alternatives demand.
* Calling a nested UDF also demands any closed-over (i.e. outer) parameters which that UDF's own expression demands.

This has the essential nature of a data-flow problem.
The key organizing principle would be a graph of the statically-determined calls.
Such a graph will generally contain cycles, but that's not a real problem.
Attack the graph in SCC order.
For each SCC, keep refining the solution until no member of the group gains new strictures.

Essentially, the basic per-function operation is to evaluate the set of strict parameters for the function's body-expression,
and if there are any newly observed, then update and let the per-SCC bit know that it's not done.
Also, this algorithm will need to keep a set of nonlocal strict parameters per function,
but we can throw those away at the end of the algorithm because they will have done their job.

It's probably worth first taking note of which call-sites have a statically-determined callee.
These are ones where the callee is a look-up of a reference that resolves to a UDF.
(Right now the intermediate-code generator contains a suitable predicate.)

Thanks to the magic of a non-cyclic import mechanism,
it's entirely feasible to analyze (first-order) demand on a module-by-module basis.

By the way
-----------

If some function is never passed as a parameter to any other thing,
then we may be sure that all calls to it are statically-determined,
so that its strictness criteria will always be respected in calls.
Therefore, that function need not begin with "STRICT" instructions.

One could conceive of strictness-based monomorphism.
This would automatically call different versions of higher-order functions
depending on different strictures of the functional-parameters.
Such higher-order demand analysis might yield faster code,
but it would require whole-program analysis,
and chances are it's a minimal improvement over the basic analysis.

It will remain possible to *expressly* annotate a parameter as ``strict``.
An example use-case is the ``reduce`` function's *accumulator* parameter.
This must be strict to avoid building a gargantuan tower of thunks
which the run-time then cannot evaluate due to stack overflow,
but the accumulator is never used in an obviously-strict position.
