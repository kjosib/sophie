Division by Zero and Other Stories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sophie's type checker is now fully adequate to rule out *type* errors of all kinds,
but not *value* errors. Problem is, at the time of this writing, the evaluator crashes
if native code raises a Python exception. Except in concurrent code, "crash" means
"print a stack trace and keep on trucking".

Here's the plan:

1. [DONE] The type-checker was first to use ``class ActivationRecord`` for nice structured things.
   The evaluator now uses it too, instead of playing weird games with special dictionary keys.
   It might consume a hair more CPU, but that's the least of my worries.
2. [SORT OF DONE] The ``ActivationRecord`` class must gain the power to generate a detailed stack trace.
   Probably each trace element should indicate the call site and also the parameters to the
   function that contained that call site.
   In particular, closure-calls merit special attention, as they should also note relevant captures.
3. [DONE] All the places in the type checker that note an error must generate a stack trace.
   I believe this will prove to be a most enlightening productivity aid for confused programmers.
4. The evaluator can wrap ``try``/``except`` around native-method calls,
   and thus generate a stack trace at appropriate times.
   The exact strategy for printing parameter values will evolve with experience.
5. Eventually some notions of process-supervision join the semantic fray.
   The exact shape of those notions is not today's problem except to say
   that it certainly will differ from conventional exception-handling.
