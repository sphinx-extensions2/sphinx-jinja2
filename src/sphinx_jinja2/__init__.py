"""A sphinx extension to render jinja templates, using minijinja."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
import importlib
import json
from pathlib import Path
from typing import Any, ClassVar, TypedDict

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StateMachine, StringList
import minijinja
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from ._private import _JinjaConfigDirective, _JinjaExample

__version__ = "0.1.0"

LOGGER = logging.getLogger(__name__)


def setup(app: Sphinx) -> dict[str, Any]:
    """Setup the sphinx extension."""

    Jinja2Config.to_config(app)
    app.add_directive("jinja", JinjaDirective)
    # private directives to document the jinja2 extension
    app.add_directive("jinja2-config", _JinjaConfigDirective)
    app.add_directive("jinja2-example", _JinjaExample)

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


@dataclass
class Jinja2Config:
    """Configuration for the sphinx-jinja2 extension."""

    contexts: dict[str, dict[str, Any]] = field(
        default_factory=dict, metadata={"doc": "A mapping of context names to context variables"}
    )
    env_kwargs: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "doc": "Keyword arguments passed to ``minijinja.Environment`` (see `<https://github.com/mitsuhiko/minijinja/tree/main/minijinja-py>`__)"
        },
    )
    filters: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "doc": "A mapping of filter names to filter functions, "
            "or import strings like ``'module.path:func_name'`` (preferred, since it is cacheable)"
        },
    )
    tests: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "doc": "A mapping of test names to test functions, "
            "or import strings like ``'module.path:func_name'`` (preferred, since it is cacheable)"
        },
    )
    debug: bool = field(default=False, metadata={"doc": "Output the rendered template"})

    @classmethod
    def from_config(cls, config: Config) -> Jinja2Config:
        """Update configuration from sphinx config."""
        inst = cls()
        for _field in fields(cls):
            setattr(inst, _field.name, config[f"jinja2_{_field.name}"])
        return inst

    @classmethod
    def to_config(cls, app: Sphinx) -> None:
        """Add configuration values."""
        for _field in fields(cls):
            app.add_config_value(f"jinja2_{_field.name}", getattr(cls(), _field.name), "env")


_ENVIRONMENT_KWARGS = frozenset(
    {
        "auto_escape_callback",
        "block_end_string",
        "block_start_string",
        "comment_end_string",
        "comment_start_string",
        "debug",
        "finalizer",
        "fuel",
        "keep_trailing_newline",
        "line_comment_prefix",
        "line_statement_prefix",
        "lstrip_blocks",
        "pycompat",
        "trim_blocks",
        "undefined_behavior",
        "variable_end_string",
        "variable_start_string",
    }
)
"""``minijinja.Environment`` keyword arguments settable via ``jinja2_env_kwargs``."""

_RENAMED_KWARGS = {"finalize": "finalizer"}
"""``jinja2.Environment`` keyword arguments transparently mapped to their minijinja name."""

_KWARG_HINTS = {
    "autoescape": "use 'auto_escape_callback'",
    "undefined": "use e.g. undefined_behavior='lenient'",
    "loader": "templates are always loaded from the source directory",
}
"""Hints for unsupported ``jinja2.Environment`` keyword arguments with a minijinja equivalent."""


def _resolve_callable(value: Any) -> Any:
    """Resolve a filter/test function from the configuration.

    This is either the function itself,
    or an import string of the form ``module.path:qualified.name``
    (also accepting ``module.path.name``).
    Import strings are preferred in ``conf.py``,
    since function objects cannot be cached by Sphinx,
    and so always trigger full re-builds.
    """
    if not isinstance(value, str):
        return value
    if ":" in value:
        modname, qualname = value.split(":", 1)
    else:
        modname, _, qualname = value.rpartition(".")
    if not modname:
        raise ImportError(f"could not import {value!r}")
    obj: Any = importlib.import_module(modname)
    for attr in qualname.split("."):
        obj = getattr(obj, attr)
    return obj


class JinjaOptions(TypedDict, total=False):
    """Options for the jinja directive."""

    ctx: str
    """JSON encoded context variables"""
    file: str
    """Read from file path,
    relative to current file, or src directory (if starts with ``/``) """
    debug: bool
    """Also output the rendered template"""
    raw: str
    """Output the rendered template as raw content of the given format (e.g. ``html``),
    rather than parsing it as source input."""


class JinjaDirective(SphinxDirective):
    has_content = True
    optional_arguments = 1
    option_spec: ClassVar[dict[str, Any]] = {
        "file": directives.path,
        "ctx": directives.unchanged,
        "debug": directives.flag,
        "raw": directives.unchanged,
    }
    options: JinjaOptions  # type: ignore[assignment]
    arguments: list[str]

    def run(self) -> list[nodes.Node]:
        conf = Jinja2Config.from_config(self.config)
        location = (self.env.docname, self.get_source_info()[1])

        def _warn(msg: str) -> None:
            LOGGER.warning(msg + " [jinja2]", location=location, type="jinja2")

        # create the context
        # precedence level: default < global < directive
        ctx = {"env": self.env}
        if self.arguments:
            name = self.arguments[0]
            if name not in conf.contexts:
                _warn(f"Context {self.arguments[0]!r} not found in jinja2_contexts")
                return []
            if not isinstance(conf.contexts[name], dict):
                _warn(
                    f"Expected context {name!r} to be a dict, got {type(conf.contexts[name]).__name__}"
                )
                return []
            ctx.update(conf.contexts[name])
        if "ctx" in self.options:
            try:
                ctx_option = json.loads(self.options["ctx"])
            except json.JSONDecodeError:
                _warn("Error parsing 'ctx' option as JSON")
                return []
            if not isinstance(ctx_option, dict):
                _warn(f"Expected 'ctx' option to be a dict, got {type(ctx_option).__name__}")
                return []
            ctx.update(ctx_option)

        # create the minijinja environment,
        # loading referenced templates from the source directory,
        # and recording them, so they can be noted as dependencies of this document
        template_base = Path(str(self.env.app.srcdir))
        loaded_templates: list[Path] = []

        def _load_template(name: str) -> str | None:
            path = template_base / name
            if not path.is_file():
                return None
            loaded_templates.append(path)
            try:
                return path.read_text("utf8")
            except OSError:
                return None

        env_kwargs: dict[str, Any] = {"undefined_behavior": "strict"}
        unsupported: list[str] = []
        for key, value in conf.env_kwargs.items():
            new_key = _RENAMED_KWARGS.get(key, key)
            if new_key in _ENVIRONMENT_KWARGS:
                env_kwargs[new_key] = value
            else:
                unsupported.append(
                    f"{key!r} ({_KWARG_HINTS[key]})" if key in _KWARG_HINTS else repr(key)
                )
        if unsupported:
            _warn(
                "Ignoring jinja2_env_kwargs not supported by minijinja.Environment: "
                + ", ".join(unsupported)
            )
        try:
            env = minijinja.Environment(loader=_load_template, **env_kwargs)
        except Exception as exc:
            _warn(f"Error creating environment: {exc.__class__.__name__}: {exc}")
            return []

        # add the filters and tests
        try:
            for filter_name, filter_func in conf.filters.items():
                env.add_filter(filter_name, _resolve_callable(filter_func))
        except Exception as exc:
            _warn(f"Error adding filters: {exc.__class__.__name__}: {exc}")
            return []
        try:
            for test_name, test_func in conf.tests.items():
                env.add_test(test_name, _resolve_callable(test_func))
        except Exception as exc:
            _warn(f"Error adding tests: {exc.__class__.__name__}: {exc}")
            return []

        # get the jinja template, from file or content
        source, line = self.get_source_info()
        template_name = self.env.docname
        if template_filename := self.options.get("file"):
            if self.content:
                _warn("Both file and content specified, ignoring content")
            _, source = self.env.relfn2path(template_filename)
            template_name = template_filename
            line = 1
            try:
                with open(source, encoding="utf8") as f:
                    content = f.read()
            except OSError as exc:
                _warn(f"Error reading template file {source}: {exc}")
                return []
            self.env.note_dependency(source)
        else:
            content = "\n".join(self.content)

        # render the template, with the context
        try:
            new_content = env.render_str(content, template_name, **ctx)
        except minijinja.TemplateError as exc:
            _warn(f"Error rendering jinja template: {exc.kind}: {exc.message}")
            return []
        except Exception as exc:
            _warn(f"Error rendering jinja template: {exc.__class__.__name__}: {exc}")
            return []
        finally:
            # note all templates loaded during the render (e.g. via include/extends),
            # so that this document is re-built if they change
            for template_path in loaded_templates:
                self.env.note_dependency(str(template_path))

        return_nodes: list[nodes.Node] = []

        if raw_format := self.options.get("raw"):
            # return the rendered template as raw (non-parsed) content
            raw_node = nodes.raw("", new_content, format=raw_format)
            self.set_source_info(raw_node)
            return_nodes.append(raw_node)
        elif isinstance(self.state_machine, StateMachine):
            # insert the new content into the source stream
            # setting the source and line number
            new_lines = StringList(
                new_content.splitlines(),
                items=[(source, line - 1) for _ in new_content.splitlines()],
            )
            self.state_machine.insert_input(new_lines, source)
        elif (renderer := getattr(self.state, "_renderer", None)) is not None and hasattr(
            renderer, "nested_render_text"
        ):
            # myst-parser does not use a docutils state machine (no insert_input),
            # so render the content at the current position in the document,
            # in the same manner as its own include directive
            # (note the content is parsed as MyST Markdown, not RST).
            # We temporarily point the document/reporter at the template source,
            # so that any warnings/errors are correctly attributed.
            document = self.state.document
            orig_source = document["source"]
            orig_reporter_source = renderer.reporter.source
            orig_line_func = getattr(renderer.reporter, "get_source_and_line", None)
            try:
                document["source"] = source
                renderer.reporter.source = source
                renderer.reporter.get_source_and_line = lambda li: (source, li)
                renderer.nested_render_text(new_content, line)
            finally:
                document["source"] = orig_source
                renderer.reporter.source = orig_reporter_source
                if orig_line_func is not None:
                    renderer.reporter.get_source_and_line = orig_line_func
                else:
                    del renderer.reporter.get_source_and_line
        else:
            # an unknown state implementation,
            # so fall back to a nested parse of the rendered content
            new_lines = StringList(
                new_content.splitlines(),
                items=[(source, line - 1) for _ in new_content.splitlines()],
            )
            base_node = nodes.Element()
            base_node.document = self.state.document
            self.state.nested_parse(new_lines, self.content_offset, base_node, match_titles=True)
            return_nodes.extend(base_node.children)

        if conf.debug or "debug" in self.options:
            # also output the rendered template
            rendered = nodes.literal_block(new_content, new_content, classes=["jinja-rendered"])
            self.set_source_info(rendered)
            return_nodes.append(rendered)

        return return_nodes
