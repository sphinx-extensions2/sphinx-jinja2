sphinx-jinja2
=============

    A sphinx extension to add the ``jinja`` directive, for rendering `jinja <https://jinja.palletsprojects.com/en/3.1.x/>`__ templates.

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

Warning messages are displayed in the Sphinx build output, for problematic inputs, these all have the type ``jinja2``, which can be used to `suppress them in the Sphinx configuration <https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-suppress_warnings>`__:

```python
suppress_warnings = ["jinja2"]
```

Since is difficult / impossible to map the source line numbers, from the template to the Jinja rendered content,
problems with the parsing of the rendered content always refer to the first line number either of the ``jinja`` directive, or the template file (when using the ``file`` option).

Configuration
-------------

The following global configuration variables are available:

.. jinja2-config::
