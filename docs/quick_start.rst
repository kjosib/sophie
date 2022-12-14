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

    D:\sophie-main\sophie-main>py -m sophie examples\turtle.sg

   Mac and Linux have something analogous.

   .. note:: The ``turtle.sg`` example will spawn graphical windows.


6. Dive into :doc:`learn`.

   The :doc:`tutorial <learn>` covers things from the ground up.
   It's written with no assumptions that you know how to program.
   If you do already know some other language,
   be prepared to unlearn some of what you have learned.

7. Scrutinize the example code.

   I'd suggest reading and trying the examples in this order:

    * hello_world.sg
    * some_arithmetic.sg
    * newton.sg
    * primes.sg
    * turtle.sg

8. Teach your kids. Or your colleagues. Or your goldfish.

9. Contribute to the development and publicity efforts.

   Much has yet to be determined.

10. Write conference papers about how awesome Sophie is.

    or will be...
