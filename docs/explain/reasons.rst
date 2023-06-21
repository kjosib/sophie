Why Sophie ...
==================

.. contents::
	:local:
	:depth: 2

Exists
~~~~~~

I got a wild hair to explore the juxtaposition of algorithmic efficiency and call-by-need.
See the comments at the top of the ``primes.sg`` example for a bit more,
or you can read the paper at https://kjosib.github.io/Contrib/Primes
to see where the thought-process began.

Basically, a thought-experiment took on the characteristics of a proper hobby-project.
And then ... here we are.

Has Strictly Ordered Sections
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dividing modules into named, ordered sections may seem like an outdated idea:
Cobol and Standard Pascal have it; C++ and Python do not.
But actually, it's just a design a continuum: Lisp is older than dirt and has no sections.

Even in languages that do not *enforce* a particular grouping of elements by kind,
you see just such a consistency in the wild. Programmers need a mental model
of the "table of contents" for each file. In a free-form language,
programmers must spend mental effort on building that table.
To minimize wasted effort, certain patterns naturally emerge.
The ordering between sections is neither arbitrary nor random, but informed by experience.

Sophie consolidates decades of experience looking at what programmers *naturally* impose on themselves,
and elevates convention to the rank of a grammatical imperative.
You learn this ordering *once,* and then that's the way it is.

It's the same with human languages and patterns like subject-verb agreement for person and number,
or gender agreement for nouns and adjectives in Spanish:
they take amortized-zero mental effort over the long haul once the learner internalizes the rule.

Is Pure-Functional
~~~~~~~~~~~~~~~~~~~

It's like sticking to a poetic meter. Constraint creates creativity.

More on point, it's an appeal to more than 40 years of experience programming.
Completely insulated "pure" functions keep systems both flexible and understandable.
Furthermore, they also play well with concurrency, which is not getting any less important.

Attempts to define "effectively pure" other than "absolutely no mutable state"
invariably turn out to harbor weird corner-case problems, so I've taken the
conservative approach.

Is Call-by-Need / Lazy-Evaluation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In programming, laziness is a virtue.

Long ago, I read http://www.paulgraham.com/avg.html
wherein the author brags on about macros as the secret weapon of lisp,
the language to which he attributes his own commercial success.

	For the uninitiated, lisp macros are sort of like functions,
	but they work on the *syntax* of expressions (transforming them into new expressions)
	rather than working only on the *results* of expressions.
	They can be used to add custom language-like behaviors, for example.
	However, macros are a bit abstruse:
	Paul reports that it's good form to avoid them unless they prove strictly necessary.

So I surveyed a few sources on *what actually gets done with lisp macros*.
In fact, why don't you google that exact phrase, poke around, and come back.
I did a rather deep dive, and eventually resolved that,
in the best of all possible languages,
the programmer would not have to know or care about the distinction
between functions and macros.

And then I learned about call-by-need, principally in the context of Haskell.

See, the result of a lisp macro is again lisp code.
Once all the macros have had their say,
plain-old-ordinary macro-free lisp code comes out and wends it way through the
plain-old-ordinary eval/apply cycle. In other words, macros may well be powerful,
but their power is principally to *orchestrate* the way the components of S-expressions
ultimately get their day in the sun (or few nanoseconds in the CPU).
And why is all that orchestration necessary?
That is, why could it not be done as a regular function?
Principally, the answer is *strict (i.e. call-by-value) evaluation!*

I figured that, with lazy evaluation, you automatically get *for free*
most of the value proposition of (hygienic) lisp macros: an expression only gets
evaluated if and when its result necessarily informs a computation in progress.
To a *lazy* function, you can pass an expression that *would fail* were it needed,
and if that expression's value *is not* needed, then the failure *never happens*.

	That's not to say there might not be some super-sophisticated applications
	of lisp macros that transcend what lazy evaluation can do for you,
	but I ask the reader: How much else of what macros offer merely compensates
	for other infelicities?

Lispers explain that lisp macros are cool because, unlike C macros,
they work on fully-parsed expressions rather than mere strings.
But in the call-by-need model, the arguments to *ordinary functions*
are also expressions, not values. You can absolutely write a (lazy-language)
function that implements a control structure, for instance. Or the moral equivalent,
since control *per se* is something you mostly leave to the compiler.

What's more, lazy evaluation also lets you define and work with infinite objects!
This capability is simply not available in a strict language.
(First-class functions can get you part of the way, but they require a design sacrifice.)

Has Algebraic Syntax
~~~~~~~~~~~~~~~~~~~~

Programming is not all *about* math, but all programs *are* math.

That's right. I'll say it again. Programs are mathematical expressions.
They are neither right nor wrong *in themselves* (assuming they are well-formed)
but we can score them for representing classes-of-computations
which (a) effectively solve interesting problems and (b) people can maintain.

It's four centuries since Leonhard Euler handed down the
mathematical syntax and rules of precedence that we all know and love.
We pick it up around the age of five, and it carries us for the rest of our life
in virtually all things mathematical.

With a bit of time and patience, people can get used to parentheses on the outside,
but I prefer to thrust one *less* obstacle in the way of neophytes.
Programs *are* math, and so they should *look* like math.

Finally, as Sophie is a functional language, I hope the classical mathematical appearance
promotes denotational thinking: a function does not *do*; a function *means*.

**Besides,** I wrote a perfectly good parser-generator and I am prepared to use it.

Has This Particular Type System?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Type System is a Verifiable Design-Language
-----------------------------------------------

	Show me your code and conceal your data structures,
	and I shall continue to be mystified.
	Show me your data structures, and I won't usually need your code;
	it'll be obvious.

	-- Eric S. Raymond, in *The Cathedral and the Bazaar,* in 1997,
	paraphrasing Fred Brooks's 1975 comment in Chapter 9 of *The Mythical Man-Month,*
	identical but for "flowchart" and "tables" in place of "code" and "data structures".

Software development is mostly maintenance.
Half of maintenance is figuring out how the different parts of a system fit together.
The simple question of *what data goes where* is singularly important,
but the answers are often diffuse and obscure in a duck-typed language.
In Sophie, it is easy to find a definitive answer.

What's more, the compiler highlights disagreements between design (i.e. type declarations)
and other code without missing a beat. Adjust the "design" and promptly see what would break in consequence.
That's a powerful facility, if properly managed.

Some people say that type systems don't catch the kinds of errors they care about.
I believe it's nevertheless shortsighted to dismiss the benefits,
*so long as the type system does not get in your way.*
After all, I am much more likely to make a mistake than the computer is.

How do I turn the knobs on this facility towards *helpful assistant* rather than *annoying pedant?*
My answers are:

* Inference over nominal record-style types (which is mostly implemented).
* Typed vocabularies (a meta-mathematical idea I've not yet begun to implement).
* Eventually, and maybe, dimensional analysis -- but that's a bit down the road.

That means I can usually say things once (or implicitly),
but I get to be redundant-on-purpose anywhere I think it will help.

The Antidote to Structural Coupling
-----------------------------------

There is a down-side to Haskell-style product-types, which is why Sophie has nominal records instead.

	In Haskell, whenever you want to get some field from a value of a product-type,
	you pattern-match on the structure of that product-type to un-bundle the bit you want.
	This creates a structural coupling, so that if the type-definition ever changes
	*even in the slightest*, then a zillion places in the code must also adjust to catch up.

	And worse: product-types have no labels! If ``data person`` is ``string * string * number * number * number``,
	then where does it say what each of those five fields mean? Nowhere!
	This definition has failed to communicate the most important thing you need to know about your data.
	Names are essential.

In contrast, Sophie has true record-types: You access their fields by name, not by position.
This fact drastically simplifies the type-case system and makes code resilient in the face of typical changes.
Adjust a record definition slightly, and most places are probably still just fine:
The code is in terms of the *nominal* type which people think of,
not the *structural* type which is a meaningless irrelevant clerical detail.
The compiler can worry about structure.

There is one exception, and I mean to overcome it some day:
*Record* definitions are also *constructor* definitions,
and (at least for now) constructor calls remain positional, just like all other function calls.
Therefore, I recommend to keep individual record definitions relatively short.
Compose larger structures from middle-sized ones, and middle-sized ones from small ones.
This practice of *chunking* plays well with how people's brains work,
and also supports design flexibility.

	Some time back in a different stab at language design, I tried getting rid of positional arguments altogether
	and using keyword-arguments for *everything.*
	It seemed like a good idea at the time, but I soon decided this cure was no better than the disease.
	In truth *most* functions don't take enough arguments to cause a memorability problem.
	When I run across one that does, it is usually a design mistake such as:

	1. Certain of the arguments hang together in a wider context, and ought to form a record.
	2. The function's body attempts to handle too many concerns at once, and should be split up.
	3. Both of the above.

"Just enough" type safety
--------------------------

These days, you hear a lot about dependent-types as a path to fully-verified software.
Technically this may be correct, but it opens meta-questions:
Did we verify the highest and best properties? And was the effort worthwhile?
Code may perfectly meet its specification, but if the specification is ill-conceived or misunderstood,
then no proof-system is going to help.

	To be sure, I respect what CoQ and Agda and Idris bring to the table.
	There are rarefied domains where those systems shine brightly.
	The use of formal methods *in and of itself* is insufficient reason to trust a heart pacemaker,
	but if I ever need one, I'll much prefer if the developers did use formal methods *for their proper purpose.*
	This is nothing less than a question of what the formalities actually mean:
	Which properties of the code were verified, and why were those the properties of interest and concern?
	But of course the proof-system *itself* is silent on these matters.

I think dependent-types would be significant overkill for what I'm trying to do with Sophie, at least for now.
I cut teeth on languages like BASIC, Pascal, C, and 6502 machine code,
but most of my professional programming has been with dynamic-typed languages
on long-lived bespoke business systems (and some occasional Java).
In this domain, the requirements are constantly growing and changing to track the client's strategic decisions,
so the systems promptly grow beyond what a person can keep track of comfortably.
Business success relies on these things working as intended on a schedule, but safety-critical they are not.
The overall theme is a responsible balance between *right* and *right now*.
Types can help with *right* if they stay out of your way,
but the time and effort of formal verification with *dependent* types runs counter to *right now*.

In this context, strong algebraic generic inferred nominal types offer an undeniable
combination of benefits *without* promising the moon.

* Such a system *on its own* can prevent the majority of accidental crash-bugs, independent of what testing and code review offer.
  (Tests can focus on demonstrating higher-level properties than *XYZ does not crash.*)
* Furthermore, the type-check is basically free, paid for by virtue of the fact that you wrote down some scraps of design documentation
  in the one place on Earth where it *definitely* won't get lost or forgotten or fall out of sync with the code.
* The field of Computer Science has known how to make this work for the past 50 years or so,
  and the vast majority of code I've ever seen would play along just fine or else had bugs anyway.

	Ironically, Sophie's chosen parse-engine is apparently a counterexample:
	Certainly it *could* be made to cooperate with a static type system,
	but the effort would be a heavy lift.

Anyway, Sophie doesn't have to be all things to all programmers.
It only needs to be *fit for purpose* for some reasonable array of purposes.

One day, it may come to pass that Sophie gains some *dependent-lite* capabilities,
but they'll be opt-in and gradual, with a focus on pushing error-reports back as
close as possible to the true original cause of the error.

Is Written in Python
~~~~~~~~~~~~~~~~~~~~~

Why not?

Long ago, I concluded that one should start with the highest-level language available for a task.
There's really no excuse to go straight to C or Java.
Python is (at least in principle) a dialect of lisp with a very heavy accent,
so it's certainly up to the task.
Also, I remember Python well enough to make the attempt.
I'd have to re-learn anything else.
