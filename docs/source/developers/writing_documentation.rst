Documentation
=============

Orbtrace must be properly documented! The documentation is maintained at
[Read The Docs](https://orbtrace.readthedocs.io) and is auto-built from the
committed github main repository.

Editing
-------

Edit the contents of ``docs/source/*.rst`` to update the documentation. If you have
the [Sphinx Documentation Generator] (https://www.sphinx-doc.org/en/master/) installed locally you can get a live preview of the current code by running something like;

```sphinx-autobuild --port 1232 ~/Develop/orbtrace/docs/source/ /tmp/sp```

...and then pointing your browser at ``localhost:1232``.

Style
-----

Documentation is not a tutorial, it's there to tell users what to do, not nessesarily
to teach them how to do it. Keep it brief but content rich, and link to other sources
whenever possible so folks aren't left flapping in the wind.
