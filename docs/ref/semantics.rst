Semantic Overview
##################


* Function application is call-by-need, except for primitive functions which are strict in every argument.
  Thus, if the value of a particular argument does not contribute to evaluating the body of a function,
  then the argument itself never gets evaluated (in the context where it appears). However, no single expression
  gets evaluated twice in the same (dynamic) scope.

* Data structures are lazy, meaning that you're welcome to express an infinite list as long as you don't consume it all.

* The logical connectives ``and`` and ``or`` use short-cut logic:
  if the expression on the left side determines the result,
  then the expression on the right side never gets evaluated.

* ``case ... when ... then ... else ... esac`` branching clauses apply tests strictly in order,
  and evaluate only enough to decide which branch (``then`` or ``else`` clause) to take.

* Explicit lists like ``[this, that, the, other]`` are internally translated to nested ``cons(...)`` constructions.

* Strings are considered atomic: they will not participate in a sequence protocol.
  However, functions may be provided to examine individual characters, take substrings, or iterate through characters.

* The run-time is free to adjust the order of evaluation or internal representations of things,
  so long as it preserves the outwardly-observable behavior.

* Right now, the ``begin:`` clause lists expressions.
  Depending on what sort of expression, Sophie will do different things:

  Simple things like numbers, text, and lists of these:
      Sophie will print these values to the console.

  Messages sent to actors:
      Sophie will work on that message *and its consequences* until finished,
      meaning there are neither any messages in flight nor any busy actors or tasks.
      An active input source (such as the SDL/game event system) is considered "busy" until
      something makes it shut down.

  Registered Data Types:
      A foreign-function interface module can register a run-time handler for specific types.
      The turtle-graphics library does this for its ``drawing`` type,
      and the result is a turtle-graphics drawing.

* Module imports may not form a cycle.

The Functional / Procedural / Message Split
============================================

Sophie attempts to reconcile lazy functional purity with observable outcomes
through these rules:

* A function must return a value and have no observable side effects.
* A procedure cannot return a value, and can only express behavior
  such as creating actors and sending messages to them.
* However, a procedure *is* a value: It can be returned from a function,
  invoked (in procedural context) for its effect, or wrapped up into a
  (potentially-parametric) message.

Sophie's take on the Actor Model
=================================

* Actors encapsulate private mutable state and associate it with a
  language of messages (usually defined by roles) and implemented
  as method-procedures.
* Any given actor is running on at most one thread, servicing one
  message at a time.
* Messages from `A` to `B` arrive in the order that `A` sent them,
  possibly interleaved with other messages.
* Messages are asynchronous and one-way. If you want a response,
  build that into the protocol. (Normally that means including a
  *return-address* actor-reference in the first message.)
* Actors can change their own state, but the updates only become
  visible for subsequent messages. (Reads come from a snapshot.)
