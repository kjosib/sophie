Goals and Roadmap
===================

.. contents::
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
7. Other nice things to have.

When all is said and done, I'd like Sophie to be a viable alternative for learning (or deepening one's grasp of) comp-sci.
The call-by-need pure-functional design gives Sophie a very different flavor from your average introductory language,
but should produce excellent habits.

Things on Deck
----------------

The next release will probably do one of:

* Turtle-graphics in some form, so Sophie can join the ranks of Advanced Logo Substitutes and be fun to watch.
* Ahead-of-time type inference.
* Preliminary support for shared modules: an export/import mechanism.

Other Nice Things to Have
--------------------------

In no particular order:

* Concurrency: Declarative and Transparent. (Probably a functional process abstraction seasoned with CSP.)
* A nice set of (presumably concurrent) I/O facilities.
* Some pattern for resilience -- likely *Tree-of-Supervisors* .
* Native Code, or perhaps running on JVM or CLR. (Transpiling is a viable option.)
* Distributed computing -- but respecting Byzantine Generals and propagation delay.
* A nontrivial set of standard libraries.
* Making it easier to get started.
* Integration with some popular IDEs. (VS-code might fit this bill.)
* An educator's guide.

Any one of these would be a proper quest in its own right.

