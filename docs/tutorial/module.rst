Modules: Programming in the Large
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* You may have noticed the definition of ``repeat`` repeated in each of the turtle-graphics case studies.
  How can we get away from repeating ourselves in that manner?

* Up to now, all the case-studies have been composed of a single file (each).
  For larger projects, you'll probably want to split your code up into multiple files,
  each concerned with some particular aspect of the overall solution.

Sophie supports both of these ideas with a shared-module system.

Consider a file called ``library.sg``:

.. literalinclude:: ../../examples/tutorial/library.sg

And consider also another file called ``patron.sg``, which uses the library:

.. literalinclude:: ../../examples/tutorial/patron.sg

What's new here, then?

* The *shared-module* file can define both types and functions. In this case, it defines the function ``nice_book``.
* The *client* of that module can *import* the shared module, and then use types and functions defined therein.
  In this case, it uses the ``nice_book`` function from the shared library.

  * Use an ``import:`` section if you want to do this. It must come first, before any ``type:`` or ``define:`` section.
  * The phrase ``"library" as lib;`` means that words from file *library.sg* will be available with the suffix ``@lib``.
    For example, we can say ``nice_book@lib``.
  * You can import as many modules as you like, but they must all use distinct ``@`` suffixes.
  * You can import modules that import other modules.
  * You can put arbitrary file paths between the double-quotes. (However, do not use the ``\`` character.
    Use ``/`` instead.) Relative paths are interpreted relative to the file making the import,
    not the current working directory.
  * A circular chain of imports would be considered a mistake.

You can run this program as follows::

    D:\GitHub\sophie>sophie examples\tutorial\patron.sg
    Gulliver's Travels

I'll grant it's not a very imposing result, but it shows that the mechanism works -- at least to some degree.
You can read more about different ways to use modules in the :doc:`../ref/modules`.
