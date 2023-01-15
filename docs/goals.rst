Goals and Roadmap
===================

.. contents::
    :local:
    :depth: 2

Design Goals
--------------
The design goals, *in priority order,* are:

1. Have Fun!
2. Keep it simple.
3. Subjectively readable appearance in my personal opinion.
4. Be pragmatic. Trade cheap computer power for a nicer time.
5. Call-by-need pure-functional for general computation.
6. Turtle graphics.
7. A modular import system, probably with explicit exports.
8. Strong type-inference so run-time troubles are few and far between.
9. Event-driven concurrency over a sensible (maybe pluggable?) process-model. (Probably actors, as in Erlang.)
10. Other nice things to have.

When all is said and done, I'd like Sophie to be a viable alternative for learning (or deepening one's grasp of) comp-sci.
The call-by-need pure-functional design gives Sophie a very different flavor from your average introductory language,
but should produce excellent habits.

Things on Deck
----------------
The next increment will probably focus on one of:

* String-oriented functions.
* Adding "Onion" types to the type algebra.
* Improving the import mechanism.
* Simple (nay, even simplistic!) console interaction

Open Design Problems:
---------------------
* Better error messages. (I have an idea related to sentential forms.)
* *rest*-parameters
* Actor Model

Other Nice Things to Have
--------------------------

In no particular order:

* An educator's guide.
* An ecosystem.
* A nontrivial set of standard libraries.
* An interactive (REPL) mode for Sophie.
* Making it easier to get started.
* Integration with some popular IDEs. (VS-code might fit this bill.)
* Some way to pre-declare a vocabulary of parameter names along with intended types.
* Concurrency: Declarative and Transparent. (Probably a functional process abstraction seasoned with CSP.)
* A nice set of (presumably concurrent) I/O facilities.
* Some pattern for resilience -- likely *Tree-of-Supervisors* .
* More polymorphism.
* A proper GUI toolkit. This will have to wait for several other features, though.
* Approximate solution to the halting problem, thus to reject (some useful subset of) programs that would hang.
* Native Code, or perhaps running on JVM or CLR. (Transpiling is a viable option.)
* Distributed computing -- but respecting Byzantine Generals and propagation delay.
* A foreign-function interface, perhaps plugged into some high-speed numerical juice.
* A standard dictionary type, preferably with lexical tie-in.
* Smart bulk-data. An answer to *here documents* is just the beginning. Static structured data in the source code ought to keep low overhead in translation to object code. JVM fails at this.
* Various forms of optimization:
    * Scope Lifting: Internally promote functions to the outermost feasible nesting level thus to "need" fewer redundant calculations.
    * Strictness Inference: Sophie guarantees call-by-need semantics, but call-by-value is more efficient when it doesn't change the result.

Any one of these would be a proper quest in its own right.

