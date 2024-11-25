2-D Graphics and Animation
===============================

.. warning:: This chapter is under development along with the features it describes.

.. contents::
   :local:
   :depth: 3

The Situation
--------------

November 2024

Certain important patterns don't pass the current type checker.
Canonical examples are *list-of-actor* and *list-of-function*.
This is because the type-checker is not designed to unify user-defined things.
It is designed to trace the execution of a program in an abstract space of *types-instead-of-values,*
but making a list of actors (or functions) can break the metaphor as it currently stands.

The Plan
---------

First, I will establish syntax for declaring that particular actors (or rather,
actor-definitions) play certain roles.
There's already a concept of ``role`` in the type system,
but it will need to grow to support multi-role requirements.

* An actor with a role declaration (``plays`` clause) can implement exactly (and only) those roles.
* An actor *without* a role declaration may be taken to define its own role.

Next, I need to solve the up-casting problem:
*A list of stage-actors should contain only stage-actors, but any stage-actor will do.*
Currently, the type-system barfs on attempting to "unify" distinct actors,
even if they are both capable of acting on stage.

This means solving two problems:

1.  A mutable slot probably needs a manifest type.
2.  The expression syntax probably needs a way to make role-assertions.

Manifestly-Typed Mutable Slots
................................

To an extent, actor-definitions have much in common with record definitions.
It's entirely reasonable to demand manifestly-typed slots in the same way
as record definitions have manifestly-typed fields. For parametric polymorphism,
we introduce type-parameters in the usual way.

This might require some adjustments to the syntax rules.
Not that big a deal.

It would also mean assurance that the left side of an assignment is never a unification,
but only a compatibility check. Of course compatibility is complicated around functions,
but we can assuredly solve that problem with care. The main thing is we're no longer
trying to decide if user-defined functions have the same type as each other.

Role Assertions
....................

The second problem is probably easier to solve:
Some form containing a normal expression and one or more roles.
The type-checker can then:

* make sure the inner value satisfies the given roles, and
* forget the details, using the declared roles as the type of the whole expression.

An Observation
---------------

Actors are not the only things that sometimes benefit from explicit type-abstraction.
For example, you may reasonably wish to define a list of user-defined functions as a
free-standing value in the program. That has not been possible yet,

It is tempting to generalize that role-assertion into an arbitrary *up-cast* mechanism.

