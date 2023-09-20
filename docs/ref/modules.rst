Modularity, Imports, and Exports
--------------------------------

Sophie has *almost* nothing to say about how you name your module files.
They're yours to name and organize as you wish.
If you want spaces in your filenames, that should be no problem at all.
So Sophie separates the notion of *where to find the module's code*
from the notion of *how to refer, in code, to the module.*


.. contents::
    :local:
    :depth: 2


Simple Whole-Module Imports
............................

You can import a module *as a name*.

Suppose we have a module called ``path/to/feline.sg`` which defines a function called ``tabby``.
And suppose further that you wish to call ``tabby`` from some other module.
Then, you can first import the module, perhaps assigning it the (local) module-identifier ``cat``::

    import:
    "path/to/feline" as cat;  # Assume this cat-module defines a function called "tabby";

Now ``cat`` shows up as a named-namespace from which you can draw qualified-names.
You can refer to the aforementioned ``tabby`` function as follows::

    define:
        kitten = tabby@cat(123);  # We can use the word "tabby" but must mention where it came from.

Note that the module-identifier ``cat`` comes *after* the function name.
This works like an internet e-mail address: You specify just enough to find the thing in context.

Benefits:
    * You can see at a glance where everything's definition comes from, wherever the word may be used.
      This can be helpful in a large file that orchestrates several other modules.

Drawbacks:
    * Tagging every mention of an imported symbol with the name of its origin can get tiresome and distracting.

Importing Specific Symbols
...........................

You can import specific words from a module::

    import:
        "path/to/cat/in/hat" (thing_one, thing_two);
    define:
        big_mess = thing_one + thing_two;

In this case, ``thing_one`` and ``thing_two`` behave exactly as if you had defined them yourself.
You cannot separately define another ``thing_one`` or ``thing_two`` in the same file,
because you've already assigned those words via the ``import:`` declaration.

Benefits:
    * Code might read more naturally when not splattered with ``@this_module`` and ``@that_module`` all over.
    * You retain a quick-reference to where imported words come from.

Drawbacks:
    * Different import-modules might define the same name to mean different things, both of which you need.

Some of Column A, Some of Column B
.......................................

You can combine the above techniques::

    import:
        "path/to/cat/in/hat" as cat (thing_one, thing_two);
    define:
        even_bigger_mess = thing_one + thing_two + worried_goldfish@cat;

The situation here is that, although ``thing_one`` and ``thing_two`` are available directly,
you can also pick up extra bits from the ``cat`` module as you need them. That's a handy
middle-ground if there are a few imported words you use frequently and others you mention only once or twice.
It also solves the problem of what if you need ``worried_goldfish`` from more than one import-module.

Importing with Local Renaming
..............................

You can import specific symbols with alternative local names::

    import:
        "path/to/famous/people" (Lincoln as President);
        "path/to/Nebraska/cities" (Lincoln as Capitol);

This style of import can also deal with the problem of homonyms, but use this with care.
It's probably OK for a short, self-contained program,
but it can lead to confusion in a large system with many people working on different parts at different times.

Importing from a Package of Shared Code
........................................

**Code you did not write yourself** is probably part of a package.
Sophie's package system is still in its infancy. For now, there is only one pacakge, called ``sys``.
You can import a module *from a package* by specifying the package's *symbol* before the import path::

    import:
        sys."turtle" (drawing, forward, reverse, left, right);

.. note:: This is only the second version of the modularity system. In time, it may get a few more features.


