"""Private module for sphinx-jinja2."""
from __future__ import annotations

from dataclasses import fields
from typing import ClassVar

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx.util.docutils import SphinxDirective


class _JinjaConfigDirective(SphinxDirective):
    """A private directive to document the configuration."""

    def run(self) -> list[nodes.Element]:
        """Run the directive."""
        container = nodes.admonition()
        container["classes"].append("info")
        title = nodes.title("Configuration Options", "Configuration Options")
        container += title

        content = []
        from . import Jinja2Config

        for _field in fields(Jinja2Config):
            name = f"jinja2_{_field.name}"
            default = getattr(Jinja2Config(), _field.name)
            content.append(f":{name}: {_field.metadata['doc']} (default: ``{default!r}``)\n")

        content_list = StringList(content)
        self.state.nested_parse(content_list, 0, container)
        return [container]


class _JinjaExample(SphinxDirective):
    """A private directive to create an example, showing the source and output."""

    option_spec: ClassVar = {
        "conf": directives.unchanged,
        "template": directives.unchanged,
        "template_path": directives.unchanged,
    }
    has_content = True

    def run(self) -> list[nodes.Element]:
        """Run the directive."""
        example_number = self.env.metadata[self.env.docname].setdefault("_jinja_example_number", 1)
        self.env.metadata[self.env.docname]["_jinja_example_number"] += 1
        container = nodes.admonition()
        container["classes"].extend(["jinja-example", "tip"])
        title = nodes.title(f"Example {example_number}", f"Example {example_number}")
        container += title

        if conf := self.options.get("conf", ""):
            # create the conf.py node
            container += nodes.strong("conf.py:", "conf.py:", classes=["jinja-conf-title"])
            conf_node = nodes.literal_block(conf, conf, language="python")
            conf_node["classes"].append("jinja-conf")
            container += conf_node

        if template := self.options.get("template", ""):
            # create the template node
            template_path = self.options.get("template_path", "template.jinja")
            container += nodes.strong(
                template_path + ":", template_path + ":", classes=["jinja-template-title"]
            )
            template_node = nodes.literal_block(template, template, language="jinja")
            template_node["classes"].append("jinja-template")
            container += template_node

        # create the source node
        source_content = "\n".join(self.content)
        source_node = nodes.literal_block(
            source_content, source_content, language="restructuredtext"
        )
        source_node["classes"].append("jinja-source")
        container += source_node

        # create the output node
        output_node = nodes.container()
        output_node["classes"].append("jinja-output")
        container += output_node
        self.state.nested_parse(self.content, self.content_offset, output_node, match_titles=True)

        return [container]
