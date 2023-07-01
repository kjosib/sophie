First Things First
=====================

.. contents::
    :local:
    :depth: 3

A Programming Language?
~~~~~~~~~~~~~~~~~~~~~~~~~~

Sophie is first and foremost a language for expressing ideas about computations that might happen.
That means you can write *and reason about* Sophie programs without any computer.
Sophie is meant to be suitable for the blackboard or publication in a magazine.
There are no special formatting requirements.

Initial Preparations
~~~~~~~~~~~~~~~~~~~~~

But if you'd like to put your computer up to the task of evaluating (executing, running) Sophie programs,
you'll need two things:

* An interpreter.
* A code editor.

You can get an interpreter easily enough from the official Sophie repository on GitHub.
Follow the directions at :doc:`../howto/quick_start` and then come back here.

As for a code editor, you have lots of choices.
But for what we're doing, you won't need anything too sophisticated.
If you're on Windows, you can use ``notepad``.
If you're running a Macintosh or Linux machine, try searching your application menu for "text editor".

Your First Program in Sophie
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Virtually every programming tutorial starts the same way:

.. literalinclude:: ../../examples/hello_world.sg

If you followed directions earlier, you already have a copy of this program at ``examples/hello_world.sg``.

Now suppose you're at a command-prompt_ and you've set the current-directory_ to wherever you extracted Sophie.
If you then run::

    sophie examples/hello_world.sg

you will see::

    Hello, World!
    All done here.

Let's break this down:

* Sophie programs are files.
* The main program begins with the phrase ``begin:``.
* Next comes a sequence of steps. Sophie follows those steps, one after another:

    * Each step is an *expression* of some value.
    * Sophie computes the value of that expression, and then displays the result.
    * Here we've only seen one kind of expression (the humble ``string``) but there are other kinds to handle all of computing.
    * If that expression should happen to be a ``drawing``, then the display is graphical. Sophie supports something called "Turtle Graphics". Deets later.
* Finally, every Sophie program ends with the phrase ``end.`` with a period.

    * Why? Because it looks nice in print.
    * Ok, the ``end.`` is now optional in response to some random dude on the internet with an opinion.
* At the moment, Sophie is implemented as a Python program.

    * So in general, you will invoke ``sophie`` followed by the pathname_ to your program.
    * Some day, this may change. If you'd like to help that along, let's talk about something called *self-hosting*.


.. _command-prompt: https://www.google.com/search?q=define+command+prompt
.. _current-directory: https://www.google.com/search?q=define+current%20directory
.. _pathname: https://www.google.com/search?q=define+pathname
