"""A sphinx extension for peeking at internal references."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
import json
from pathlib import Path
from typing import Any, ClassVar, TypedDict

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
import jinja2
from jinja2 import meta
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from ._private import _JinjaConfigDirective, _JinjaExample

__version__ = "0.0.1"

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
        default_factory=dict, metadata={"doc": "Keyword arguments passed to jinja2.Environment"}
    )
    filters: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "doc": "A mapping of filter names to filter functions (see `<https://jinja.palletsprojects.com/en/3.1.x/api/#writing-filters>`__)"
        },
    )
    tests: dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "doc": "A mapping of test names to test functions (see `<https://jinja.palletsprojects.com/en/3.1.x/api/#writing-tests>`__)"
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


class JinjaOptions(TypedDict, total=False):
    """Options for the jinja directive."""

    ctx: str
    """JSON encoded context variables"""
    file: str
    """Read from file path,
    relative to current file, or src directory (if starts with ``/``) """
    debug: bool
    """Also output the rendered template"""


class JinjaDirective(SphinxDirective):
    has_content = True
    optional_arguments = 1
    option_spec: ClassVar[dict[str, Any]] = {
        "file": directives.path,
        "ctx": directives.unchanged,
        "debug": directives.flag,
    }
    options: JinjaOptions
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

        # create the jinja environment
        template_base = Path(str(self.env.app.srcdir))
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_base),
            undefined=jinja2.StrictUndefined,
            **conf.env_kwargs,
        )

        # add the filters and tests
        try:
            env.filters.update(conf.filters)
        except Exception as exc:
            _warn(f"Error adding filters: {exc.__class__.__name__}: {exc}")
            return []
        try:
            env.tests.update(conf.tests)
        except Exception as exc:
            _warn(f"Error adding tests: {exc.__class__.__name__}: {exc}")
            return []

        # get the jinja template, from file or content
        source, line = self.get_source_info()
        if template_filename := self.options.get("file"):
            if self.content:
                _warn("Both file and content specified, ignoring content")
            _, source = self.env.relfn2path(template_filename)
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

        # note all dependent templates
        ast = env.parse(content)
        for template in meta.find_referenced_templates(ast):
            if template is None:
                continue
            template_path = template_base / template
            if template_path.is_file():
                self.env.note_dependency(str(template_path))

        # render the template, with the context
        tpl = env.from_string(content)
        try:
            new_content = tpl.render(**ctx)
        except Exception as exc:
            _warn(f"Error rendering jinja template: {exc.__class__.__name__}: {exc}")
            return []

        # insert the new content into the source stream
        # setting the source and line number
        new_lines = StringList(
            new_content.splitlines(), items=[(source, line - 1) for _ in new_content.splitlines()]
        )
        self.state_machine.insert_input(new_lines, source)

        if conf.debug or "debug" in self.options:
            # return the rendered template
            rendered = nodes.literal_block(new_content, new_content, classes=["jinja-rendered"])
            self.set_source_info(rendered)
            return [rendered]

        return []
