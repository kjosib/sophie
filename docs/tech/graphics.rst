Graphics in Sophie's VM
########################

The Simple DirectMedia Layer (SDL) is the foundation for Sophie's cross-platform game subsystem.


.. contents::
    :local:
    :depth: 3

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

Observe that the boundary of a circle is given by ``x^2 + y^2 == r^2``.
But let's write that differently: ``x^2 + y^2 - r^2 == [error_term]``.
The sign of the error term tells you if you're inside (negative) or outside (positive) the circle.

So now we have a simple algorithm for following a curve:
It goes like this::

    Start at the point (x, y) = (r, 0)
    While y < x:
        Plot the pixel you're at.
        Go one pixel up (or down, as the case may be: ``y++;``
        If you're now outside the circle go one pixel left: ``x--;``

This plots 1/8th of a circle, but you get the rest with rotations and reflections.

Refinements
------------

To know very quickly if *<x,y>* is outside the circle,
keep track of ``x^2`` and ``y^2``. This can be done quite efficiently,
as squares are also sums of successive odd numbers.
It should be easy to work out how to add and subtract from an error term.

The algorithm as described so far has a stark cosmetic flaw:
It always draws four lonely single points at the extreme cardinal directions.

If we start the error term with a somewhat negative bias,
then it's equivalent to drawing a slightly bigger circle,
which will yield pleasingly-straight segments in the cardinal directions.
But how big of a correction is proper?
I suspect most sources are using about 1/2 pixel,
which gives an initial error term of ``r^2 - (r+0.5)^2``.
Applying FOIL, the square terms cancel and the spare 1/4 unit we can just ignore.
We're left with ``-r`` as the initial error term.
Personally, I think this sometimes leaves warts on the 45-degree points,
so I might try a 1/4 pixel bias of ``-r/2``.

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

