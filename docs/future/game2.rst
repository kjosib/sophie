2-D Graphics and Animation
===============================

.. warning:: This chapter is under development along with the features it describes.

.. contents::
   :local:
   :depth: 3

The Situation
--------------

November 2024

It's become clear that the original *proof-of-concept* game driver is not really a great fit
for the direction I want to take Sophie. It *works* as far as it's defined to do so,
but it lacks a good path forward.

In the future, I'd rather establish that one actor will respond to input events
(such as from the mouse or keyboard) and it can send to other actors corresponding to
the screen and sound and so forth -- and these will speak well-known *protocols.*


The Plan
---------

I'd like to establish a ``role`` that *game* actors play.
In concept, they just need to respond to the wide variety of possible inputs.
These input events could come from a "keyboard" and "mouse" and perhaps even "joystick" actor,
as well as a "timer" actor -- or from a grand unified "inputs" actor.

This notion gets rid of wonky ``on_click`` messages that configure the behavior of an assumed click-source.
Instead, you'd just implement the events you care about, and at some point pass a properly-configured actor
to the driver. If you need to change modes, send in a new actor with the ``Game`` role.

The responses would presumably include sending update messages to ``screen`` and ``sound`` actors,
each playing their own roles.

Because the number and kinds of input events is subject to growth,
it probably makes sense that unimplemented methods of a ``role`` are assumed to be the empty procedure.
(Or in other words, the messages are silently dropped.)


