High-Order Type Checking (HOT)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

I would like a rather precise up-front analysis phase based on what we can infer about the types of variables,
but I do not mean to impose burdens normally associated with *dependent-type* systems.

I settled on a solution based on abstract interpretation.
In concept, my approach is to just run the program as-is, but in the realm of types rather than values.
This is a whole-program approach to the question type-correctness:
The same function might be safe-or-not depending on how you call it.

.. contents::
    :local:
    :depth: 2




Type Numbering
---------------------
Types can be nontrivial recursive objects.
We need a quick way to tell if we're looking at two instances of the same type.
Something akin to value-numbering will do nicely.
For the Python implementation, I'll use the booze-tools ``EquivalenceClassifier``
and make ``SophieType`` objects define ``__hash__`` and ``__eq__`` suitably.

Dynamic Type Dependency Front
------------------------------
Formally, this is the set of parameters upon which a function's type may depend.
We want that so that the evaluator can *properly* memoize the results of its type computations.

Naively this would be the set of all parameters that the function's body mentions.
However, that's not quite right:
If function A calls function B, and function B mentions parameter P (or match-subject id) not its own,
then the type of P influences the type of B which in turn influences the type of A.

This is another data-flow problem. Start by associating all the non-local data dependencies,
then flow these through that partial call-graph consisting of calls to non-global functions.

Finally, add the local variable dependencies specifically if they are mentioned.
(This is because a function ``(a,b)->b`` does not depend on the type of ``a``.)

The type-dependency front will inform the memoization layer.

Evaluate the Type-Program
---------------------------
The structure of ``sophie.hot.type_evaluator`` should bear a striking resemblance to that of ``sophie.simple_evaluator``.
However, I intend some different semantics. The type-evaluator can use memoization with eager/strict evaluation.
It will also need a way to detect recursion, and a sensible theory of how to close such loops.

The *apply* operation takes care of recursion and memoization.

Dealing with Recursion
.......................

Having reached a recursive call, there is a least-fixpoint problem.
I take this approach:

At first, hypothesize that the function returns *nothing.*
Not a *maybe-monad* style ``nothing``, for that would be *something.*
I mean more like a *Never-Ending Story* kind of nothing.
(See the film with your kids, if you haven't already done.)

In the land of type theory, *The Nothing* has a type and that type is called "Bottom".
Note in particular the following algebraic **laws of Bottom:**

1. Bottom is a universal *subtype:* ``union(X, Bottom) => X``.
2. Bottom is a universal *intersection:* ``Bottom.foo => Bottom``.
3. Bottom is a universal *argument:* ``(A->B)(Bottom) => B``.
4. Bottom is a universal *function:* ``Bottom(foo) => Bottom``.

    Each of these laws also corresponds to a constraint about a particular bottom-typed value.
    It's *mostly* pointless to chase that rabbit. Rather than, for example, discerning
    that *X* must be a record (or a function, respectively), we can rely on the type-evaluator
    to get around to that point with a specific *X* type.

At the end of this preliminary round of deduction,
we have a sensible lower-bound return-type for the function *as it was actually called.*

If that preliminary lower-bound is *Bottom*, then the function's induction lacks a base-case,
which is an error. Otherwise:

* Put the updated lower-bound return-type in the cache line for this type-context.
* Attempt the *apply* again, with this new updated hypothesis in the cache.
* Repeat the above two-step dance until the resulting type stops changing.
* Call it a day.

Functions as Type Transformers
--------------------------------

Sophie's type-evaluator has this concept that user-defined functions do not *have* types,
and they are not types *in themselves*, but rather they *transform* types in the same manner
that they transform values.
This and a matching type-checking algorithm are why we *can indeed* have nice things.
Behold:

High-Order Functions as Parameters
....................................

We can pass a high-order function as a parameter to another function,
and use that first function generically:

.. literalinclude:: ../../examples/tutorial/generic_parameter.sg

This *looks* like the sort of thing that would normally require a dynamic language.
How's it type-check? It's actually quite straightforward:
Every reference to a function resolves to a type. If it's a native function,
then it resolves to whatever type the FFI promised. But if it's a user-defined function,
then we have special "user-function" types in the type-calculus.
These types can close over contextual types in the same way nested functions can close over values.

Nothing is concerned with the *generic* type of ``map``.
It's just that whenever ``m`` gets applied, it has the *UDF-Type* of ``map``,
which is *implicitly* generic as an *emergent property* of ``map``'s definition.

High-Order Functions as Concrete Data
.......................................

We can also pass generic functions -- both native and user-defined -- as parameters
to constructors, and then use those functions according to their indicated manner:

.. literalinclude:: ../../zoo/ok/arrows.sg

Now, when it comes time to put a user-defined function into a record-like datum,
Sophie's type-checker splits the field-type's arrow into argument and result types.
She feeds the argument into the UDF-type, runs the normal deductions, and then
binds the result back to the expected result-type. If this works, then great!
The function *will serve* in that role. Otherwise, it's a type-error.

There is one gotcha: You cannot necessarily play this trick with generic record types.
You will generally create and refer to a concrete alias to the generic type if you want to store functions as fields.
By design, the expression type-deduction routines do not expect type-variables in actual-parameters.
You might get away with it on occasion,
but only if the function does not use the type-variable in any meaningful way.
