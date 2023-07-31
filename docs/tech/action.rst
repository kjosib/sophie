Imperative Vocabulary
=========================

This note explains the (evolving) interface between pure-functional calculation
and pure-imperative actor-oriented *causing-things-to-actually-happen* in Sophie.

.. contents::
   :local:
   :depth: 2

Overview
~~~~~~~~~~

On one level, there is a data-type called ``act``, which is implicitly the data
type of doing observable things like sending messages. So a function can evaluate
to some action. The action is an element of data like any other. Pass it around,
store it in a list, do whatever.

If an expression in a ``begin:`` block evaluates to an action,
then Sophie will perform that action. If it's a compound action,
Sophie will evaluate and then perform each element of the compound in turn.
And if one of these elements itself evaluates to a compound-action,
then the notion is recursive in the usual (synchronous) sense.

There appear to be four kinds of action:

* Skip (i.e. do nothing)
* Send Message by name, to some particular actor
* Invoke Call-Back (the host-actor (if any) is implied in the value of the call-back)
* Do-Block (i.e. compound-action, possibly creating actors along the way)

.. note:: I *intend* for Sophie to guarantee tail-call optimization (a'la Scheme) but it probably does not work yet.

Apples and Oranges
~~~~~~~~~~~~~~~~~~~~

It's tricky to avoid mixing apples and oranges in ``runtime.py`` and ``scheduler.py``.
The apropos terms are all pretty abstract and interchangeable in English,
so if you want to follow the code, you'll want this quick guide:

Action
    Abstractly, this is a unit of imperative behavior,
    bereft of concern for how, when, or where it happens.
    You can *perform* an action.
    This should not go to the scheduler as-is, but packed inside of an AsyncTask.

Task
    A thing that can be scheduled to a worker-thread.
    Varieties of ``Task`` include ``Actor``, ``ClosureTask``, and ``PlainTask``.

BoundMethod
    The pair of a receiver and a method-name, where the method takes arguments.
    You can apply arguments to such a thing and end up with a MessageAction.
    These are one form of asynchronous call-back.

    At the moment there's a slightly hacky overlap here.
    If the named method takes no parameters,
    then you can use it like an action directly 

MessageAction
    An object consisting of a receiver, a method-name, and corresponding arguments.
    To *perform* a message is to put it in the receiver's mailbox.


A Few Good Verbs
~~~~~~~~~~~~~~~~~~~

Quite a number of things could be ``foo.run()`` but that would overload the term ``run``
to the point that it lacks meaning. So here are some terms:

apply
    Call this *with arguments* on something that looks like a function, to get a value.
    This happens inside the part that evaluates pure functions.
    Perhaps confusingly, this is a method of ``class Procedure``,
    which got its name before Sophie had any inkling of actor-like concepts.

perform
    Call this on an ``Action`` to *do the thing* synchronously in the current thread.

proceed
    Call this on a ``Task`` to *do the thing* synchronously in the current thread.
    Any relevant static state is attached to the object exposing this method.
    This can apply to a free-floating action or to an actor (which handles messages).

handle
    The abstract idea of how an actor deals with a message at some point *after* receiving it,
    when it's the actor's turn to consume some CPU.

accept_message
    This is about inserting a message into an actor's mailbox.
    In consequence, the actor must end up scheduled on some task queue if it isn't already.

