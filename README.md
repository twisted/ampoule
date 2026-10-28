
Ampoule - a process pool for Twisted, based on AMP
==================================================

Ampoule is a process pool written on top of
[Twisted](https://twistedmatrix.com/). Its name comes from the use of
[AMP](https://amp-protocol.net/) as the default communication protocol between
the pool and all its children.

It provides an API very close to that of the built-in Twisted `ThreadPool`. As
an helper function it also provides a `deferToAMPProcess` function that creates
the `ProcessPool` and submits jobs to it.

AI Policy
---------

Ampoule follows the [Twisted AI Policy](https://docs.twisted.org/en/latest/development/ai-policy.html). This means this project does not allow the inclusion of the outputs of generative AI tools.
