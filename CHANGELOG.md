# Changelog

## v0.1.0 (2026-11-10)

The first release since 2024: templates now render with [minijinja](https://github.com/mitsuhiko/minijinja)
instead of Jinja2, so a template can no longer reach Python internals through underscore-prefixed attributes.
It also adds MyST Markdown support, a `raw` option, import-string filters and tests,
line-accurate error locations and typed warnings.
It requires Python >= 3.11, Sphinx >= 7.2 and minijinja >= 2.15 (2.x and 3.x are both supported).

See also [sphinx-ub-directives](https://sphinx-ub-directives.readthedocs.io), whose `ub-template` directive
renders minijinja templates from data-only contexts, and can also render in ubCode; sphinx-jinja2 remains maintained
(see the note in the [documentation](https://sphinx-jinja2.readthedocs.io)).

### ‼️ Breaking changes

- **The template engine is now minijinja, not Jinja2** ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10)).
  Most templates render identically; the differences are listed under "Migration from Jinja2 to minijinja" below.
  `jinja2` is no longer a dependency of sphinx-jinja2 (it is still installed with Sphinx, which depends on it).
- **Templates can no longer read underscore-prefixed attributes** (e.g. `{{ obj.__class__ }}`, `{{ obj._private }}`):
  in minijinja's sandbox they are undefined, so the template fails to render, with a warning
  (with the default strict undefined behaviour; with `lenient` they render empty).
  0.0.1 rendered with an unsandboxed `jinja2.Environment`, where such attributes lead to Python internals.
  Objects in a context (including `env`, the Sphinx build environment) still expose their public attributes and methods,
  so only put objects in a context that you trust a template with ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10)).
- **Python >= 3.11 is required** (0.0.1 allowed Python >= 3.8), **Sphinx >= 7.2** (0.0.1 set no minimum),
  and **minijinja >= 2.15** is a new dependency ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10)).
- **Jinja2-only filters and decorators are unsupported**: filters such as `urlize`, `xmlattr`, `center` and `wordcount`
  are not built in to minijinja, and filters or tests using Jinja2's `@pass_context`, `@pass_environment`
  or `@pass_eval_context` fail when the template renders, with a warning
  (or, if their extra parameters have defaults, run with the wrong arguments) ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10)).
- **Jinja2-only `jinja2_env_kwargs` are ignored, with a warning** (e.g. `autoescape`, `undefined`, `loader`, `extensions`);
  `finalize` is passed on as minijinja's `finalizer` ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10)).

Upgrading: build once with `-W` (or read the warnings) to find templates that hit one of the above.
A project that needs a Jinja2-only feature can stay on `sphinx-jinja2==0.0.1` until it has migrated.

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
- How some values render depends on the installed minijinja version (any `minijinja>=2.15`, including 3.x, is supported).
  `None` and booleans render as with Jinja2 (`None`, `True`) from minijinja 2.22, and as `none`, `true` before it.
  Before minijinja 3.0, strings in lists and dicts created in a template are double-quoted
  (`{{ ['a', 1] }}` gives `["a", 1]`, where Jinja2 gives `['a', 1]`), and tuples render as lists.
  Lists and dicts passed in from Python keep their Python form on every version.
  From minijinja 3.0, the `round` filter rounds halves to even (`{{ 2.5 | round }}` is `2.0`);
  before 3.0, it rounds halves away from zero (`3.0`).
  Use `{% if var %}{{ var }}{% endif %}` guards or explicit formatting if this matters.
- A small number of Jinja2-only filters (e.g. `urlize`, `xmlattr`, `center`, `wordcount`)
  are not built in to minijinja; they can be re-added via `jinja2_filters` if required.
  minijinja has a built-in `wordwrap` only from 2.24, and it takes keyword arguments only
  (`wordwrap(width=79)`; Jinja2's `wordwrap(79)` fails);
  a `wordwrap` added via `jinja2_filters` replaces it.
- Custom filters and tests receive values as plain arguments;
  Jinja2's `@pass_context`, `@pass_environment` and `@pass_eval_context` decorators
  are not supported by minijinja (such filters fail when the template is rendered, with a warning,
  or, if their extra parameters have defaults, run with the wrong arguments).
- Underscore-prefixed attributes (e.g. `__class__`, `_private`) are not accessible from templates;
  they are undefined, so the template fails to render, with a warning
  (with the default strict undefined behaviour; with `lenient` they render empty).
- Python methods on objects (e.g. `{{ "a,b".split(",") }}`) continue to work,
  via minijinja's [Python compatibility mode](https://github.com/mitsuhiko/minijinja/tree/main/minijinja-py#python-methods-on-objects).
- Templates referenced by `{% include %}` / `{% extends %}` remain restricted
  to files within the source directory
  (absolute paths and `..` parent traversal are rejected, as previously).

### ✨ New features

- The `jinja` directive now works within MyST Markdown documents
  (the rendered content is parsed as MyST Markdown)
  ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10), reported by @ice-tong in [#3](https://github.com/sphinx-extensions2/sphinx-jinja2/issues/3))
- New `raw` option, to output the rendered template as raw content of a given format (e.g. `html`),
  rather than parsing it as source input
  ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10), adapted from [#4](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/4), thanks to @eudoxos)
- `jinja2_filters` and `jinja2_tests` values can now be import strings,
  such as `"module.path:func_name"`, as opposed to function objects.
  This is now the recommended usage, since function objects cannot be cached by Sphinx,
  and so always trigger full re-builds ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10)).
- The package now ships a `py.typed` marker, so type checkers use its annotations ([#11](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/11)).

### 🐛 Fixes

- Template files (loaded via `:file:` or `{% include %}`) that begin with a UTF-8
  byte-order mark are now decoded correctly (the BOM is stripped, rather than
  injected into the rendered output) ([#12](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/12)).
- The `raw` option's format is now normalized (lower-cased and whitespace-collapsed),
  so e.g. `:raw: HTML` is recognized by docutils writers rather than silently
  dropping the content; an empty format is also validated before rendering ([#12](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/12)).
- Warnings now carry a subtype (`jinja2.config`, `jinja2.template` or `jinja2.render`),
  for granular control via `suppress_warnings`, and the warning-type tag is no longer
  duplicated in the message text on Sphinx >=8 (nor, on Sphinx <8, appended to it at all;
  suppression via the warning type/subtype is unaffected on all versions) ([#12](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/12)).
- Rendering errors in inline templates are now reported at the actual failing line in
  the document (rather than the directive's first line), including inside `.. include::`-d files;
  errors in template files, and in templates an inline template extends or imports,
  keep the directive's line and include the position within that template file,
  and the `debug` option / `jinja2_debug` now includes minijinja's code-frame in the error message ([#12](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/12)).
- A misconfigured non-dict `jinja2_contexts` now emits a warning for directives that name a context,
  instead of aborting the whole build with an unhandled error
  (directives that name no context are unaffected) ([#12](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/12)).
- Overriding the reserved `env` context key now emits a warning (the override is still
  applied) ([#12](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/12)).
- Use `env.srcdir` instead of the deprecated `env.app.srcdir` (avoids a `RemovedInSphinx11Warning`) ([#12](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/12)).

### 🧰 Maintenance

- Tested on Python 3.11-3.14 and Sphinx 7.2-9.x, with minijinja 2.15 (lower-bounds leg) and the latest 3.x; neither Sphinx nor minijinja is capped ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10), [#11](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/11))
- CI: in-process test builds with a real coverage gate (`--cov-fail-under=80`), a Windows job, a lower-bounds job, a lint job and a package smoke test ([#11](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/11))
- PEP 639 license expression in packaging metadata, and flit_core 4 allowed as the build backend ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10), [#17](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/17))
- PyPI trusted publishing (OIDC) in CI ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10))
- Updated CI actions, pre-commit hooks (ruff 0.17.4 with its base rule set pinned, mypy 2.4.1) and the Read the Docs config ([#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10), [#13](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/13), [#14](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/14), [#15](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/15), [#16](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/16))

**Full changelog**: [v0.0.1...v0.1.0](https://github.com/sphinx-extensions2/sphinx-jinja2/compare/v0.0.1...v0.1.0)

## v0.0.1 (2024-02-01)

Initial release.
