Getting Started
================

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
