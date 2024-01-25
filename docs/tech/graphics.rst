Graphics in Sophie's VM
########################

The Simple DirectMedia Layer (SDL) is the foundation for Sophie's cross-platform game subsystem.
It gives you a basic set of tools, but its primitive drawing operations are not too sophisticated.
This article contains brief design notes on reinvented wheels.

.. contents::
    :local:
    :depth: 3


.. admonition:: Raster graphics and off-by-one errors

    Many an irritating graphical glitch grows from
    forgetting that pixels are not points.
    Pixels have height and width!

    Furthermore, pixels are not universally square,
    although modern PC displays are usually close enough.


Circles
========

As it happens, SDL does not provide for curved shapes,
so for the moment I'm not drawing circles, ellipses, or arcs in the VM.
There are third-party libraries (such as "SDL2_gfx") to handle that nicely,
but I'm wary of adding to the DLL supply chain just to run the VM.
In any case, feature parity with PyGame is probably adequate for simple stuff.
That means circles, ellipses, and arcs-of-ellipses.

It looks like the consensus is to rasterize shapes into a pre-allocated buffer of ``SDL_Point`` structures,
then call something like ``SDL_RenderDrawPoints`` or ``SDL_RenderDrawLines``. 
This is because (allegedly) calling the singular form is "slow" for some value of "slow".
`At least one source <https://discourse.libsdl.org/t/query-how-do-you-draw-a-circle-in-sdl2-sdl2/33379/2>`_
in SDL's own discourse server suggests that the underlying platforms don't provide curve primitives either,
so it's not like SDL is pointlessly incomplete.

In any case, it looks like I'll get an introduction to the "Midpoint Circle Algorithm".

The Basic Algorithm
--------------------

Observe that the boundary of a circle is given by ``x^2 + y^2 == r^2``, where ``r`` is half the diameter.
But let's write that differently: ``x^2 + y^2 - r^2 == [error_term]``.
The sign of the error term tells you if you're inside (negative) or outside (positive) the circle.

The goal is to draw those pixels that best fit the margin of a disc ``r`` units in radius.
This yields a simple algorithm for following the inside of a circle:
It goes something like this::

    Let r equal floor(diameter/2)
    Start with (x,y) at the point (0, r)
    While y <= x:
        Plot the pixel you're at.
        Go one pixel up (or down, as the case may be): ``y++;``
        If (x, y) is now outside the circle, go one pixel left: ``x--;``

This plots 1/8th of a circle, but you get the rest with rotations and reflections.

Performance
-----------------
To know very quickly if *<x,y>* is outside the circle,
keep an explicit ``error_term`` and maintain the invariant that ``x^2 + y^2 - r^2 == error_term``.
This can be done quite efficiently based on the following observation::

    error_term(x,y+1) - error_term(x,y)
    = (y+1)*(y+1) - y^2
    = y^2 + 2*y + 1 - y^2
    = 2*y + 1

The logic works identically for ``x`` and ``y``.

Devilish Details
-----------------

The algorithm needs an initial error term, which works out as follows::

    = (r - .5)^2 - r^2
    = r^2 - r - 1/4 - r^2
    = - r - 1/4

It's convenient to start with ``error_term = 0-floor(radius)``
and then interpret the ``error_term`` variable such that zero is considered inside the reference circle.

Also, it turns out there is a slight difference between plotting odd- and even-diameter circles.

Odd-Diameter Circles
....................

Consider for example a circle that fits a square 11 pixels on a side.
To make the math easy, label the axes from ``-5`` to ``+5``,
with the origin in the exact middle of pixel ``(0, 0)``.

The program variables ``x`` and ``y`` thus represent exact integer coordinates,
and so the math upon them (and the error term) is exactly as laid out above.

We get initial ``error_term = -floor(diameter/2)`` here
because ``(x + 1/2)^2 = x^2 + x + 1/4`` and we can account for the ``1/4`` by treating zero as "inside".

Even-Diameter Circles
.....................

Consider for example a circle that fits a square 10 pixels on a side.
Again to make the math easy, label the axes from ``-5`` to ``+5``,
but this time, the coordinate points fall at the corners of the pixels.

In this case, the *center of the pen* must follow a circle of radius 4.5
so that the pen's outer edge has radius 5.

This means the program variables can still be integers,
but ``x`` and ``y`` *actually represent* the real-valued coordinate 1/2 higher than what's in the variable.

That changes the ``error_term`` increment and decrement slightly:
The *mathematical* expression *2y+1* turns into the *program code* ``2*y + 2``.
The extra 1 comes from doubling the implied 1/2 in the value that ``y`` really represents.

The initial ``error_term`` in this case is still the same ``-floor(diameter/2)``.
If you work through the math, you end up with 3/4 residual instead of 1/4,
but that doesn't make any difference to the algorithm.

Ellipses
=========

The ordinary rectilinear ellipse is a straightforward extension.
Most of the difference falls right out from a bit of algebra.
An ellipse has a major and minor radius,
but for our purpose we'll say it has an X and a Y radius.
The characteristic equation is ``(x/r.x)^2 + (y/r.y)^2 - 1 = [error_term]``.
To get rid of those pesky divisions,
multiply through by the constant ``(r.x * r.y)^2``.
That obtains ``(x * r.y)^2 + (y * r.x)^2 - [constant] = [error_term]``.

Once again the essential concept serves:
Move up and in to follow a portion of the curve.
This time, the algorithm must run a vertical phase
from ``(r.x, 0)`` and a horizontal phase from ``(0, r.y)``
because ellipses lack diagonal symmetry.

Adjusting the Basic Algorithm
------------------------------

One could simply recalculate the characteristic equation for each step.
However, we can do better. The key is to update an error term properly.
That depends on this observation::

    Given f(x) = (Ax)^2, then
    = f(x+1) - f(x)
    = (Ax + B)^2 - (Ax)^2
    = (Ax)^2 + 2ABx + B^2 + (Ax)^2
    = 2ABx + B^2

Now let ``A = r.y`` and let ``B = r.x``.
The constants ``2AB`` and ``B^2`` are easy to calculate once up front.
Now the error increment for ``x`` involves only one multiplication.

There is one other thing to figure out, which is a proper stopping criterion.
That's going to be whenever the increment for the fast dimension
gets bigger than the decrement for the slow dimension.
If we keep the increments ``dx`` and ``dy`` in their own variables,
then their updates and comparisons become trivial.

Once again, cosmetic concerns suggest biasing the error term slightly negative.
Similar reasoning suggests 1/4 pixel's worth should be sufficient.
That comes with a bit of extra trouble:
The error associated with 1/4 pixel depends on the influence of each radius.
For ellipses with significant aspect ratio,
that could leave a small kink where the horizontal and vertical portions meet.
A proper solution would need a correction to the bias at each step.
That will take some additional cogitation.

Other Curves
=============

The general concept extends to lots of different kinds of curves.
General conic sections should pose little challenge.
The hard part is to figure out the critical points from which to start each curve segment.

The basic algorithm works for any curve you can define as ``f(x,y) == c``.
It works quite a bit better if ``f(x+1,y) - f(x,y)`` and ``f(x,y+1) - f(x,y)`` have simpler forms.

Obvious next steps would be to produce rotated ellipses and arcs.

The challenge with arcs is to define what exactly we mean by an angle in the context of an ellipse.
One way is to consider the ellipse as just a squashed circle: Find the sine and cosine, then scale.
Another way is to figure out the point where a ray from the origin and
that angle from the positive X axis intersects the ellipse.
And yet a third would be to find the point where the ellipse is normal to that angle.
Both of those last ideas seem hard, so chances are the first one is the most popular.
But I think it makes the least sense.

See Also
=========

* Naturally I'm not the first to think up this particular strategy for ellipses:
  `A Fast Bresenham Type Algorithm For Drawing Ellipses <https://dai.fmph.uniba.sk/upload/0/01/Ellipse.pdf>`_

* This recent approach does ellipses parametrically, using some fixed-point arithmetic:
  `A Fast Parametric Ellipse Algorithm <https://arxiv.org/pdf/2009.03434.pdf>`_

* This Master's thesis/project from 1989 probably holds merit:
  `Raster Algorithms for 2D Primitives <https://cs.brown.edu/research/pubs/theses/masters/1989/dasilva.pdf>`_
