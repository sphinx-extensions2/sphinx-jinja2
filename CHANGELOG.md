# Changelog

## v0.1.0 (unreleased)

### ⬆️ Migration from Jinja2 to minijinja

Templates are now rendered with [minijinja](https://github.com/mitsuhiko/minijinja),
a modern re-implementation of the Jinja template engine,
rather than [Jinja2](https://jinja.palletsprojects.com).

Most templates should render identically, however, note the following differences:

- `jinja2_env_kwargs` are now passed to [`minijinja.Environment`](https://github.com/mitsuhiko/minijinja/tree/main/minijinja-py).
  Common keyword arguments (e.g. `trim_blocks`, `lstrip_blocks`, `keep_trailing_newline`, custom delimiters)
  are unchanged; Jinja2-only arguments are ignored, with a warning.
- Undefined variables still raise errors (as previously, with `StrictUndefined`),
  but this can now be relaxed with `jinja2_env_kwargs = {"undefined_behavior": "lenient"}`.
- `None` values are rendered as `none` rather than `None`
  (use `{% if var %}{{ var }}{% endif %}` guards if this matters).
- A small number of Jinja2-only filters (e.g. `wordwrap`, `urlize`, `xmlattr`, `center`, `wordcount`)
  are not built in to minijinja; they can be re-added via `jinja2_filters` if required.
- Custom filters and tests receive values as plain arguments;
  Jinja2's `@pass_context`, `@pass_environment` and `@pass_eval_context` decorators
  are not supported by minijinja (such filters fail when the template is rendered, with a warning).
- Python methods on objects (e.g. `{{ "a,b".split(",") }}`) continue to work,
  via minijinja's [Python compatibility mode](https://github.com/mitsuhiko/minijinja/tree/main/minijinja-py#python-methods-on-objects).
- Templates referenced by `{% include %}` / `{% extends %}` remain restricted
  to files within the source directory
  (absolute paths and `..` parent traversal are rejected, as previously).

### ✨ New features

- The `jinja` directive now works within MyST Markdown documents
  (the rendered content is parsed as MyST Markdown)
  ([#3](https://github.com/sphinx-extensions2/sphinx-jinja2/issues/3))
- New `raw` option, to output the rendered template as raw content of a given format (e.g. `html`),
  rather than parsing it as source input
  (thanks to [@eudoxos](https://github.com/eudoxos),
  [#4](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/4))
- `jinja2_filters` and `jinja2_tests` values can now be import strings,
  such as `"module.path:func_name"`, as opposed to function objects.
  This is now the recommended usage, since function objects cannot be cached by Sphinx,
  and so always trigger full re-builds.

### 🐛 Fixes

- Template files (loaded via `:file:` or `{% include %}`) that begin with a UTF-8
  byte-order mark are now decoded correctly (the BOM is stripped, rather than
  injected into the rendered output).
- The `raw` option's format is now normalized (lower-cased and whitespace-collapsed),
  so e.g. `:raw: HTML` is recognized by docutils writers rather than silently
  dropping the content; an empty format is also validated before rendering.
- Warnings now carry a subtype (`jinja2.config`, `jinja2.template` or `jinja2.render`),
  for granular control via `suppress_warnings`, and the warning-type tag is no longer
  duplicated in the message text on Sphinx >=8 (nor, on Sphinx <8, appended to it at all;
  suppression via the warning type/subtype is unaffected on all versions).
- Rendering errors in inline templates are now reported at the actual failing line in
  the document (rather than the directive's first line); errors in template files include
  the position within the file, and the `debug` option / `jinja2_debug` now includes
  minijinja's code-frame in the error message.
- A misconfigured non-dict `jinja2_contexts` now emits a warning, instead of aborting the
  whole build with an unhandled error.
- Overriding the reserved `env` context key now emits a warning (the override is still
  applied).

### 🧰 Maintenance

- Support Python 3.11-3.14, Sphinx 7.2-9.x
- Use `env.srcdir` instead of the deprecated `env.app.srcdir` (avoids a `RemovedInSphinx11Warning`)
- PEP 639 license expression in packaging metadata
- PyPI trusted publishing (OIDC) in CI
- Updated CI actions, pre-commit hooks, Read the Docs config

## v0.0.1 (2024-01-26)

Initial release.
