sphinx-jinja2
=============

    A sphinx extension to add the ``jinja`` directive, for rendering `Jinja <https://jinja.palletsprojects.com>`__ templates
    (powered by `minijinja <https://github.com/mitsuhiko/minijinja>`__).

.. note::

    This is an adaption of `sphinx-jinja <https://github.com/tardyp/sphinx-jinja>`__, which appears to be unmaintained.

Usage
-----

.. image:: https://img.shields.io/pypi/v/sphinx-jinja2.svg
   :target: https://pypi.org/project/sphinx-jinja2/
   :alt: PyPI

Simply install and add ``sphinx_jinja2`` to your ``conf.py`` extensions list.

.. code-block:: bash

    pip install sphinx-jinja2

.. code-block:: python

    extensions = [
        ...
        'sphinx_jinja2',
        ...
    ]

Guide
-----

The most basic usage is to render an inline template using the ``jinja`` directive, where the ``ctx`` option is a JSON dict that will be passed to the template as the context:

.. jinja2-example::

    .. jinja::
        :ctx: {"name": "World"}

        Hallo {{ name }}!

The Sphinx environment is also available by default as ``env``:

.. jinja2-example::

    .. jinja::

        This is {{ env.config.project }} version {{ env.config.version }}.

The ``env`` key is reserved for the Sphinx environment.
A context may still define ``env`` to override it (a ``jinja2.config`` warning is emitted when it does).

To set globally available variables, use the ``jinja2_contexts`` option in your ``conf.py``, and refer to them by name as the first argument to the ``jinja`` directive:

.. jinja2-example::
    :conf: jinja2_contexts = {"ctx1": {"name": "World"}}

    .. jinja:: ctx1

        Hallo {{ name }}!

Templates from files
********************

To load a template from a file, use the ``file`` option.
Similar to the `include` directive, the path is relative to the source file that contains the directive,
or relative to the source directory if the path starts with ``/``.
The file should always be encoded in UTF-8.
If these files change then Sphinx will re-build pages that use them!

.. jinja2-example::
    :template: Hallo {{ name }}!
    :template_path: templates/example1.jinja

    .. jinja::
        :file: templates/example1.jinja
        :ctx: {"name": "World"}

Templates can include or extend other templates.
Referenced templates are always relative to the source directory,
and Sphinx will also correctly re-build pages that use them.
Templates can never be loaded from outside the source directory
(absolute paths and ``..`` parent traversal are rejected).

.. jinja2-example::
    :template: Hallo {{ name }}!
    :template_path: templates/example1.jinja

    .. jinja::
        :ctx: {"name": "World", "more": "content"}

        {% include "templates/example1.jinja" %}

        More {{ more }}!

Headings in templates
*********************

Rendered templates are parsed within the context of the current document,
and so heading levels are relative to the current document.

.. jinja2-example::

    .. jinja::

        Sub-heading
        ...........

        Content

If you need a generic template containing a heading, then perhaps use a context variable to specify the heading character:

.. jinja2-example::

    .. jinja::
        :ctx: {"heading_char": "."}

        Sub-heading
        {{ heading_char * 11 }}

        Content

Custom filters and tests
************************

Custom `filters <https://docs.rs/minijinja/latest/minijinja/filters/index.html>`__ and `tests <https://docs.rs/minijinja/latest/minijinja/tests/index.html>`__ can be added to the environment,
using the ``jinja2_filters`` and ``jinja2_tests`` configuration options.
These map names to Python functions, or import strings of the form ``"module.path:func_name"``.
Import strings are preferred, since Sphinx cannot cache function objects, meaning that full re-builds are always triggered.

.. jinja2-example::
    :conf: jinja2_tests = {"is_big": "my_module:is_big"}

    .. jinja::
        :ctx: {"number": 200}

        {% if number is is_big %}{{ number }} is big!{% endif %}

Raw output
**********

By default, the rendered template is parsed as source input,
to instead output it as raw content of a given `format <https://docutils.sourceforge.io/docs/ref/rst/directives.html#raw-data-pass-through>`__,
use the ``raw`` option:

.. jinja2-example::

    .. jinja::
        :ctx: {"name": "World"}
        :raw: html

        Hello <em>{{ name }}</em>!

MyST Markdown documents
***********************

The ``jinja`` directive can also be used within `MyST Markdown <https://myst-parser.readthedocs.io>`__ documents,
in which case the rendered template is parsed as MyST Markdown:

.. code-block:: markdown

    ```{jinja}
    :ctx: {"name": "World"}

    Hello *{{ name }}*!
    ```

Debugging
*********

To see the rendered templates in the built documentation, use the ``debug`` option for a single directive, or the ``jinja2_debug`` option in your ``conf.py`` to enable it globally:

.. jinja2-example::

    .. jinja::
        :ctx: {"name": "World"}
        :debug:

        Hallo **{{ name }}**!

Warning messages
****************

Warning messages are displayed in the Sphinx build output for problematic inputs.
These all have the type ``jinja2``, with a subtype identifying the category of problem:

- ``jinja2.config`` -- configuration problems (an unknown or malformed context, ``ctx`` option, ``jinja2_env_kwargs``, filter/test, ...)
- ``jinja2.template`` -- problems reading a template file
- ``jinja2.render`` -- problems rendering a template

These types can be used to `suppress them in the Sphinx configuration <https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-suppress_warnings>`__, either all together or by subtype:

.. code-block:: python

    suppress_warnings = ["jinja2"]  # suppress all
    suppress_warnings = ["jinja2.render"]  # suppress only render errors

Rendering errors (such as an undefined variable) are reported at the line where they occur:

- In reStructuredText documents, an inline template's rendering error is attributed to the actual failing line in the document; for a template file (``file`` option), the position within the template file is appended to the message (e.g. ``(template.jinja:2)``).
- Problems with *parsing* the rendered content (as opposed to rendering it) are difficult / impossible to map back to the template source, and so refer to the first line number either of the ``jinja`` directive, or the template file (when using the ``file`` option).
- In MyST Markdown documents, rendering errors are reported at the ``jinja`` directive's line; problems with *parsing* the rendered content refer to a line number within the rendered content, offset from the ``jinja`` directive (and with myst-parser >=5, they are always attributed to the document containing the directive, rather than the template file).

Migration from Jinja2
---------------------

Since v0.1.0, templates are rendered using `minijinja <https://github.com/mitsuhiko/minijinja>`__,
a modern re-implementation of the Jinja template engine, rather than `Jinja2 <https://jinja.palletsprojects.com>`__.
Most templates will render identically, but note the following differences:

- ``jinja2_env_kwargs`` are now passed to `minijinja.Environment <https://github.com/mitsuhiko/minijinja/tree/main/minijinja-py>`__.
  Common keyword arguments (``trim_blocks``, ``lstrip_blocks``, ``keep_trailing_newline``, custom delimiters, ...) are unchanged;
  Jinja2-only arguments are ignored, with a warning.
- Undefined variables raise errors (as previously, with ``StrictUndefined``),
  but this can now be relaxed with ``jinja2_env_kwargs = {"undefined_behavior": "lenient"}``.
- ``None`` values are rendered as ``none`` rather than ``None``
  (use ``{% if var %}{{ var }}{% endif %}`` guards if this matters).
- A small number of Jinja2-only filters (e.g. ``wordwrap``, ``urlize``, ``xmlattr``, ``center``, ``wordcount``)
  are not built in to minijinja; they can be re-added via ``jinja2_filters`` if required.
- Custom filters and tests receive values as plain arguments;
  Jinja2's ``@pass_context``, ``@pass_environment`` and ``@pass_eval_context`` decorators
  are not supported by minijinja (such filters fail when the template is rendered, with a warning).
- Python methods on objects (e.g. ``{{ "a,b".split(",") }}``) continue to work,
  via minijinja's `Python compatibility mode <https://github.com/mitsuhiko/minijinja/tree/main/minijinja-py#python-methods-on-objects>`__.

Configuration
-------------

The following global configuration variables are available:

.. jinja2-config::
