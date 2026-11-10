# sphinx-jinja2

[![PyPI][pypi-badge]][pypi-link]

> A sphinx extension to add the `jinja` directive, for rendering Jinja templates (powered by [minijinja](https://github.com/mitsuhiko/minijinja)).

**Note:** This is an adaption of [https://github.com/tardyp/sphinx-jinja](https://github.com/tardyp/sphinx-jinja), which appears to be unmaintained.

**See also: sphinx-ub-directives.** The `ub-template` directive in
[sphinx-ub-directives](https://pypi.org/project/sphinx-ub-directives/) renders minijinja templates with the same
`:file:`, `:ctx:`, `:debug:` and `:raw:` options; with its configuration in `ubproject.toml`, the same project also renders in ubCode.
It is stricter by design: contexts are data only (no `env`, Python objects or functions),
there are no custom filters, tests or environment options, and template output may not contain headings.
The two extensions can be used side by side. sphinx-jinja2 remains maintained;
to switch, see [Migrating from sphinx-jinja2](https://sphinx-ub-directives.readthedocs.io/en/latest/migrating.html).

See [the documentation](https://sphinx-jinja2.readthedocs.io) for more information.

[pypi-badge]: https://img.shields.io/pypi/v/sphinx-jinja2.svg
[pypi-link]: https://pypi.org/project/sphinx-jinja2
