Learn Sophie (for the absolute beginner)
=========================================

Welcome, and thank you for starting your CS journey with Sophie.
You'll find she has much of value to share, even if she is a little different than average.

.. note:: This document is under construction.

.. contents::
	:depth: 2

Why Learn with Sophie?
-----------------------

Sophie is different.

Most currently-popular first programming languages have quite a lot in common:

* You need lots of syntax to get things done, which distracts you from the essentials of comp-sci and/or software engineering.
* You have to spell out a particular ordering of sub-tasks.
* Confusing early design mistakes leave traps and zaps for newcomers and experts alike.
  They can't be fixed out of concern for backwards-compatibility.
  (JavaScript in particular is infamous for this.)
* They work by changing internal state from one step to the next,
  which puts the focus on *how it works* at the expense of *what it does*.
  (That forces you to consider time and sequence when you try to understand some code.)
* They're object-oriented, meaning ... something beyond the scope of this chapter,
  but it sure won't help you in the early stages of learning to program.
* They make only the most cursory review of your code before carrying out your instructions,
  so that you can see programming errors happen while your code is operating.
  (If you've ever seen the word "undefined" in a web page, that's an example.)
* They have enormous communities online -- which is probably an advantage.

Sophie is different on all accounts.

* Sophie is relatively small and simple. There's not a lot of fancy syntax or weird special cases.
* Sophie has *call-by-need*. That lets you focus on meaning, not a particular ordering of sub-tasks.
  Sophie will figure out a sensible ordering of tasks automatically.
* Sophie is youthful and thus able to stay consistent with a vision, not an installed base.
* Sophie is functionally pure. That means *meaning is eternal* and you don't have to worry about
  changes behind your back. That may also sound impossibly constraining, but trust me: it's fine.
* Sophie ... doesn't dirty herself with objects of the usual sort. (There is a better way.)
* Sophie is fastidious about preventing errors up front, before they cause trouble during operation.
  Through *strong static type inference*, Sophie can check in advance for many kinds of
  latent problems that testing along might not catch -- which can save you a whole mess of effort.

.. note::
	Ok, confession: That last point is not yet implemented. The current version can "crash".
	But that one feature is Sophie's main *raison d'être*. So it's coming soon.

Moreover, learning Sophie will affect you in different ways from learning a conventional starter-language.
Sophie teaches you how to think about problems and design solutions effectively.
When you get fluent in a language like Sophie, each bit of code looks like its own *proof-of-correctness*.
The mental habits you develop learning Sophie will help you write better code in other languages.
When you internalize what Sophie offers, most of the others will seem more or less handicapped.

.. note::
	Just to be clear, Sophie is not finished. You can't yet write the next hit video game in Sophie. Yet.
	But you can do some foundational things, learn some general skills, and make Sophie better along the way.

Getting Started
-----------------

If you know your way around the command line, you'll be fine.
Sooner or later this will get even easier.

1. Install Python.

   To use Sophie, you'll need Python already installed. You can get it from http://www.python.org.
   Yes, Python is one of those currently-popular first programming languages.
   It's not evil; it's just completely different. Sophie uses Python internally -- for now.
   So when you finish up with Sophie, you're still left with another popular language.

2. Install a certain oddly-named module.

   Sophie's internals rely on a package called ``booze-tools``.
   You can get it easily enough: From a command prompt, type::

		py -m pip install --upgrade booze-tools

   and press ``enter``. You'll see a load of gibberish fly past.
   Assuming you're not behind a restrictive firewall, the right things should have happened.

3. Download the code for Sophie.

   Save `this link <https://github.com/kjosib/sophie/archive/refs/heads/main.zip>`_
   to your computer somewhere you can find it easily.

   That's a direct link to an up-to-the-minute version of all of Sophie.
   If you'd prefer to browse the repository online, it's `here <https://github.com/kjosib/sophie>`_.

4. Extract the zip archive and place the juicy bits somewhere nice.

   Apparently GitHub bundles this up in several layers of ``sophie-main`` which you can strip out.
   Mainly, you'll want the ``sophie`` folder.

5. Try an example. Here's how it looks in Windows command line::

	D:\>cd sophie-main\sophie-main

	D:\sophie-main\sophie-main>dir
	 Volume in drive D is Data
	 Volume Serial Number is 54CB-A845

	 Directory of D:\sophie-main\sophie-main

	10/23/2022  03:57 PM    <DIR>          .
	10/23/2022  03:57 PM    <DIR>          ..
	10/23/2022  03:57 PM             1,833 .gitignore
	10/23/2022  03:57 PM    <DIR>          examples
	10/23/2022  03:57 PM             1,065 LICENSE
	10/23/2022  03:57 PM             5,828 README.md
	10/23/2022  03:57 PM    <DIR>          sophie
	10/23/2022  03:57 PM    <DIR>          tests
	10/23/2022  03:57 PM    <DIR>          zoo_of_fail
				   3 File(s)          8,726 bytes
				   6 Dir(s)  253,928,804,352 bytes free

	D:\sophie-main\sophie-main>py -m sophie examples\hello_world.sg
	Hello, World!
	All done here.

   Mac and Linux have something analogous.

6. Go have a look at the examples.

   If this is your first time, I'd suggest reading them, and then trying them out, in this order:

	* hello_world.sg
	* some_arithmetic.sg
	* primes.sg
	* alias.sg

Super-Fancy Calculator
--------------------------

This section starts with the ``some_arithmetic.sg`` example.

Then it should move on to talk about functions.
I will need to build a few in.

Next, it should introduce user-defined functions.

Making Decisions
--------------------

Introduce the conditional forms.


