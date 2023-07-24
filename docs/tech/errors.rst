Respectable Error Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These days you can't promote a language unless its reference compiler has user-friendly error messages.
*(The irony inherent in this state of affairs is left as an exercise for the reader.)*

.. contents::
    :local:
    :depth: 2

Diagnostics Module
------------------

The main idea here is that virtually every conceivable kind of error message maps to a
method on ``class Report``. That keeps the mainline code cleaner and provides a layer of
control over when and how messages get displayed. The report also conveys the fact of errors
back to the main flow of control. This makes it convenient to report all the errors a pass
detects, rather than the irritating fail-fast approach of only reporting the very first error.

The report consists primarily of a list ``Pic`` objects which are individually responsible
for rendering themselves as text. As this part stands, it's not too ugly,
but some colorful ANSI-art might be nice. Or unicode-art, since we live in the 21st century now.

At any rate, the point is that there's an API and an injected dependency.
In principle, it would be possible to swap out the report-object for something aimed at IDE integration.
Internationalization is another direction this could go.

Parse Errors
---------------

If the parser blocks, the front-end gets back a list of symbols representing the contents of the parse stack,
as well as the identity (and location) of the look-ahead token.

The front-end now creates, and can use, a tree-structure to represent error scenarios/patterns and suggested messages.
The patterns are:

* structured like filename globs.
* ranked from most to least specific.

Nice-to-have but *not* implemented:

* validated internally against the parse tables.
* exhaustive in covering the entire space of possible situations.
* additional right-context beyond the look-ahead token.

Basically, the concept is to walk the stack backwards looking for the longest-matching pattern,
and then use the corresponding message as the front-end's best guess at what advice to give.

If no rule matches, then instead the message contains a so-called "Guru Meditation" which is
just a stack-picture. I can then pick one of these up and use it directly to construct a suitable rule,
once I've looked the situation over and decided what text I want to provide.

The specific code is ``_hint`` and ``_best_hint`` in ``front_end.py``.

    Right now, there are only four hint-patterns.
    Kind of underwhelming I know, but the machinery works and is tested.

* **Observation:** It's theoretically possible to tell the complete set of valid next tokens.
  That might be a nice gesture. But it also might be information-overload.

Scan Errors
------------

The answer to a blocked scan is to present the next character as a token
and let the parse-error machinery deal with it.

Type Errors
--------------

Current Behavior:
    The type-checker keeps something like a stack of activation records so that,
    in the event of an error, it can provide something like a stack-trace,
    along with the deduced types of all the parameters leading up to the problem.
    This turns out to be pretty helpful in practice.

Might Be Nice To Have:
    Showing wrong-types along with *where they came from* probably would help
    programmers to track down the root-causes of type errors.
    This would require the type-checker to pass around a slightly more complex object,
    consisting of both the type per-se (i.e. ``calculus.SophieType``) and also the provenance,
    or why the computer judged a particular type. Provenance can be
    nontrivial -- maybe even recursive -- but traces a path of reasoning.

