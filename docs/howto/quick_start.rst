Getting Started
================

If you know your way around the command line, you'll be fine.
Sooner or later this will get even easier.

1. Install Python.

   To use Sophie, you'll need Python already installed. You can get it from http://www.python.org.
   Yes, Python is one of those currently-popular first programming languages.
   It's not evil; it's just completely different. Sophie uses Python internally -- for now.
   So when you finish up with Sophie, you're still left with another popular language.

2. Install prerequisite modules.

   Sophie's internals rely on a package called ``booze-tools``.
   You can get it easily enough: From a command prompt, type::

        py -m pip install --upgrade booze-tools pygame

   and press ``enter``. You'll see a load of gibberish fly past.
   Assuming you're not behind a restrictive firewall, the right things should have happened.

3. Download the code for Sophie.

   Option One: Get a current snap-shot
        Save `this link <https://github.com/kjosib/sophie/archive/refs/heads/main.zip>`_
        to your computer somewhere you can find it easily.
        That's a direct link to an up-to-the-minute version of all of Sophie.

   Option Two: Get a stable release
        `Click here <https://github.com/kjosib/sophie/releases>`_
        and fetch the most recent "Source code (zip)" asset
        to your computer somewhere you can find it easily.

        If you use this option, you should look for the corresponding version
        of the documentation, for there have been a few changes in the language.

   If you'd prefer to browse the repository online, it's `here <https://github.com/kjosib/sophie>`_.

4. Extract the zip archive and place the juicy bits somewhere nice.

   Apparently GitHub bundles this up in several layers of ``sophie-main`` which you can strip out.
   (If you got a version-coded release, then ``main`` is replaced by the version-code.)
   Mainly, you'll want the ``sophie`` folder.

5. Try an example. Here's how it looks in Windows command line::

    D:\>cd sophie-main\sophie-main

    D:\sophie-main\sophie-main>py -m sophie examples\turtle\turtle.sg

   Mac and Linux have something analogous.

   .. note:: The ``turtle.sg`` example will spawn graphical windows.

6. Make Sophie accessible from anywhere. On the Windows command line::

    D:\sophie-main\sophie-main>py -m pip install -e .

   Now you can invoke Sophie from anywhere::

    D:\sophie-main\sophie-main>cd \

    D:\>py -m sophie
    This is an interpreter for the Sophie programming language.

    usage: py -m sophie [-h] [-c] [-x] program


    For example:

        py -m sophie program.sg

    will run program.sg if possible, or else try to explain why not.

        py -m sophie -h

    will explain all the arguments.

    For more information, see:

    Documentation: https://sophie.readthedocs.io/en/latest/
           GitHub: https://github.com/kjosib/sophie

7. Dive into :doc:`../tutorial/index`.

   The :doc:`tutorial <../tutorial/index>` covers things from the ground up.
   It's written with no assumptions that you know how to program.
   If you do already know some other language,
   be prepared to unlearn some of what you have learned.

8. Scrutinize the example code.

   I'd suggest reading and trying the examples in this order:

    * hello_world.sg
    * some_arithmetic.sg
    * newton.sg
    * primes.sg
    * turtle.sg

9. Teach your kids. Or your colleagues. Or your goldfish.

10. Contribute to the development and publicity efforts.

    Much has yet to be determined.

11. Write conference papers about how awesome Sophie is.

    or will be...
