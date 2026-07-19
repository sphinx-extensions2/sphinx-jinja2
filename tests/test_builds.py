from __future__ import annotations

from io import StringIO
from pathlib import Path
import pickle
import shutil
import sys
from textwrap import dedent

from docutils import nodes
from sphinx import version_info as sphinx_version_info
from sphinx.application import Sphinx
from sphinx.util.docutils import docutils_namespace, patch_docutils


class BuildResult:
    def __init__(self, build: Path, stdout: str, stderr: str) -> None:
        self._build = build
        self._stdout = stdout
        self._stderr = stderr

    @property
    def build(self) -> Path:
        return self._build

    @property
    def stdout(self) -> str:
        return self._stdout

    @property
    def stderr(self) -> str:
        return self._stderr

    def doctree(self, docname: str = "index") -> nodes.document:
        path = self._build / "doctrees" / f"{docname}.doctree"
        doc = pickle.loads(path.read_bytes())
        assert isinstance(doc, nodes.document)
        return doc


def run_sphinxbuild(path: Path, clear_build: bool = True) -> BuildResult:
    """Build the Sphinx project at ``path`` in-process and return the result.

    The build runs in the current process (rather than shelling out to
    ``python -m sphinx``), so that coverage of the extension is recorded and
    no external ``python``/``sphinx`` on ``PATH`` is required.  On failure the
    underlying Sphinx exception is allowed to propagate (all tests expect a
    successful build).

    :param path: the source directory (also used as the config directory).
    :param clear_build: if true, remove any previous build output first,
        forcing a full build; otherwise reuse the saved environment stored in
        the doctree directory, exercising Sphinx's incremental rebuild.
    """
    build_path = path / "_build"
    if clear_build and build_path.is_dir():
        shutil.rmtree(build_path)

    status, warning = StringIO(), StringIO()

    # A conf.py may mutate ``sys.path`` and import modules from the source
    # directory (e.g. the ``_funcs`` module used to test filter/test import
    # strings).  Snapshot ``sys.path`` and, afterwards, evict any module loaded
    # from the source directory, so that an in-process build cannot leak state
    # into (or shadow an identically-named module in) a later build.
    src = path.resolve()
    saved_sys_path = sys.path.copy()
    try:
        # ``patch_docutils`` + ``docutils_namespace`` ensure docutils global
        # registrations (directives, roles, nodes) don't leak between builds.
        with patch_docutils(str(path)), docutils_namespace():
            app = Sphinx(
                srcdir=str(path),
                confdir=str(path),
                outdir=str(build_path / "html"),
                doctreedir=str(build_path / "doctrees"),
                buildername="html",
                status=status,
                warning=warning,
            )
            app.build()
    finally:
        sys.path[:] = saved_sys_path
        for name, module in list(sys.modules.items()):
            module_file = getattr(module, "__file__", None)
            if module_file and Path(module_file).resolve().is_relative_to(src):
                del sys.modules[name]

    return BuildResult(build_path, status.getvalue(), warning.getvalue())


CONF_CONTENT = """
version = "2.0"
extensions = ["sphinx_jinja2"]
"""


def test_inline(tmp_path: Path, snapshot_doctree):
    """Test that inline templates work."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            hallo
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_inline_debug(tmp_path: Path, snapshot_doctree):
    """Test that inline templates work."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT + "\njinja2_debug = True")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            **hallo**
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_from_file(tmp_path: Path, snapshot_doctree):
    """Test that the file option works."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "template.jinja").write_text("hallo")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: template.jinja
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_file_paths(tmp_path: Path, snapshot_doctree):
    """Test that relative and absolute paths are resolved correctly."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "template.jinja").write_text("hallo")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. toctree::

            folder/other
        """
        )
    )
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "other.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: ../template.jinja
        .. jinja::
            :file: /template.jinja
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree("folder/other") == snapshot_doctree


def test_file_and_inline(tmp_path: Path, snapshot_doctree):
    """Test that a warning is emitted if both file and inline templates are set."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "template.jinja").write_text("a")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: template.jinja

            b
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    print(result.stderr)
    assert (
        "index.rst:3: WARNING: Both file and content specified, ignoring content" in result.stderr
    )


def test_missing_file(tmp_path: Path):
    """Test that missing files are reported as warnings."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: template.jinja
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    print(result.stderr)
    assert "index.rst:3: WARNING: Error reading template file" in result.stderr


def test_file_not_utf8(tmp_path: Path):
    """Test that files that cannot be decoded as UTF-8 are reported as warnings."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "template.jinja").write_bytes(b"caf\xe9 {{ 1 + 1 }}")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: template.jinja
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    print(result.stderr)
    assert "index.rst:3: WARNING: Error reading template file" in result.stderr


def test_ctx(tmp_path: Path, snapshot_doctree):
    """Test that the ctx option works, globally and locally,
    and that local takes precedence over global.
    """
    (tmp_path / "conf.py").write_text(
        CONF_CONTENT + "\njinja2_contexts = {'ctx1': {'a': 'foo', 'b': 'bar'}}"
    )
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja:: ctx1
            :ctx: {"b": "baz"}

            {{ a }}{{ b }}{{ env.config.version }}
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_missing_variable(tmp_path: Path):
    """Test that missing variables are reported as warnings."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            {{ a }}
        """
        )
    )
    result = run_sphinxbuild(tmp_path, clear_build=False)
    # the error is reported at the actual failing document line (fix 4):
    # the directive is on line 3, but the failing content ``{{ a }}`` is the
    # first content line, i.e. document line 5 (content_offset 4 + template line 1)
    assert (
        "index.rst:5: WARNING: Error rendering jinja template: UndefinedError: undefined value"
        in result.stderr
    )
    # minijinja's own " (in index:N)" position suffix is stripped for inline errors
    assert "(in " not in result.stderr


def test_missing_context(tmp_path: Path):
    """Test that missing contexts are reported as warnings."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja:: xxx

            hallo
        """
        )
    )
    result = run_sphinxbuild(tmp_path, clear_build=False)
    print(result.stderr)
    assert "index.rst:3: WARNING: Context 'xxx' not found in jinja2_contexts" in result.stderr


def test_bad_ctx_option(tmp_path: Path):
    """Test that ctx that cannot be read as a JSON dict are reported as warnings."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :ctx: {"a": "b"

            hallo

        .. jinja::
            :ctx: 123

            hallo
        """
        )
    )
    result = run_sphinxbuild(tmp_path, clear_build=False)
    print(result.stderr)
    assert "index.rst:3: WARNING: Error parsing 'ctx' option as JSON" in result.stderr
    assert "index.rst:8: WARNING: Expected 'ctx' option to be a dict, got int" in result.stderr


def test_warning_inline(tmp_path: Path):
    """Test that warnings from inline templates are reported correctly."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            :unknown:`content`
        """
        )
    )
    result = run_sphinxbuild(tmp_path, clear_build=False)
    assert 'index.rst:3: ERROR: Unknown interpreted text role "unknown"' in result.stderr


def test_warning_from_file(tmp_path: Path):
    """Test that warnings from templates in files are reported correctly."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "template.jinja").write_text(":unknown:`content`")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: template.jinja
        """
        )
    )
    result = run_sphinxbuild(tmp_path, clear_build=False)
    print(result.stderr)
    assert 'template.jinja:1: ERROR: Unknown interpreted text role "unknown"' in result.stderr


def test_rebuild_on_file_change(tmp_path: Path, snapshot_doctree):
    """Test that the doctree is rebuilt when the template file changes."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "template.jinja").write_text("hallo")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: template.jinja
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    (tmp_path / "template.jinja").write_text("hallo2")
    result = run_sphinxbuild(tmp_path, clear_build=False)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_filters_and_tests(tmp_path: Path, snapshot_doctree):
    """Test that custom filters and tests can be added via the configuration.

    Note, function objects cannot be cached by Sphinx (warning expected),
    import strings (see following test) are preferred.
    """
    (tmp_path / "conf.py").write_text(
        CONF_CONTENT
        + "\njinja2_filters = {'double': lambda x: x * 2}"
        + "\njinja2_tests = {'big': lambda x: x > 100}"
    )
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            {{ 2 | double }}{% if 200 is big %} is big{% endif %}
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    # Sphinx >=7.3 warns that function objects cannot be cached;
    # the exact spelling varies ("unpickable" on 7.4.x, "unpickleable" on >=8.0),
    # and older Sphinx emits no such warning at all.
    lines = result.stderr.splitlines()
    # no other (unexpected) warnings should be emitted
    assert all("cannot cache unpick" in line for line in lines)
    if sphinx_version_info >= (7, 3):
        # on supported Sphinx the warning must actually be present
        # (guarding against it silently disappearing, which the all() check
        # above would pass vacuously for)
        assert any("cannot cache unpick" in line for line in lines)
    assert result.doctree() == snapshot_doctree


def test_filters_and_tests_import_strings(tmp_path: Path, snapshot_doctree):
    """Test that custom filters and tests can be given as import strings,
    which (unlike function objects) are cacheable by Sphinx.
    """
    (tmp_path / "_funcs.py").write_text(
        dedent(
            """\
        def double(x):
            return x * 2

        def big(x):
            return x > 100
        """
        )
    )
    (tmp_path / "conf.py").write_text(
        CONF_CONTENT
        + "\nimport os, sys; sys.path.insert(0, os.path.dirname(__file__))"
        + "\njinja2_filters = {'double': '_funcs:double'}"
        + "\njinja2_tests = {'big': '_funcs.big'}"
    )
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            {{ 2 | double }}{% if 200 is big %} is big{% endif %}
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_filters_bad_import_string(tmp_path: Path):
    """Test that unresolvable import strings are reported as warnings."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT + "\njinja2_filters = {'double': 'not_a_mod'}")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            hallo
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert "index.rst:3: WARNING: Error adding filters: ImportError" in result.stderr


def test_env_kwargs(tmp_path: Path, snapshot_doctree):
    """Test that supported env_kwargs are passed to the environment,
    and unsupported (jinja2 only) ones are reported as warnings.
    """
    (tmp_path / "conf.py").write_text(
        CONF_CONTENT + "\njinja2_env_kwargs = {'trim_blocks': True, 'autoescape': True}"
    )
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            {% if true %}
            hallo
            {% endif %}
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert (
        "index.rst:3: WARNING: Ignoring jinja2_env_kwargs not supported by minijinja.Environment:"
        " 'autoescape' (use 'auto_escape_callback')" in result.stderr
    )
    assert result.doctree() == snapshot_doctree


def test_raw(tmp_path: Path, snapshot_doctree):
    """Test that the raw option outputs the rendered template as raw content."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :ctx: {"name": "World"}
            :raw: html

            Hello <em>{{ name }}</em>
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_raw_no_format(tmp_path: Path):
    """Test that a raw option with no format argument is reported as a warning."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :raw:

            <b>{{ 1 + 1 }}</b>
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    print(result.stderr)
    assert "index.rst:3: WARNING: 'raw' option requires an output format" in result.stderr


def test_myst(tmp_path: Path, snapshot_doctree):
    """Test that the directive works in MyST Markdown documents,
    where the rendered content is parsed as MyST (see issue #3).
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT + "\nextensions.append('myst_parser')")
    (tmp_path / "index.md").write_text(
        dedent(
            """\
        # Test

        ```{jinja}
        :ctx: {"name": "World"}

        Hello *{{ name }}*

        ## Sub-heading

        In section
        ```

        After directive
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_myst_render_error_location(tmp_path: Path):
    """A render error in a MyST ``{jinja}`` fence is attributed to the
    directive's line, not a bogus ``content_offset``-derived line (fix 4).

    Under myst-parser's MockState, ``content_offset`` is a fixed internal
    value (not document-relative), so the inline line-offset math must be gated
    on a real docutils state machine and otherwise fall back to the directive.
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT + "\nextensions.append('myst_parser')")
    # the fence is pushed well down the document (content above it) so that a
    # bogus content_offset-derived line would land far from the real location
    (tmp_path / "index.md").write_text(
        dedent(
            """\
        # Heading

        First paragraph of content.

        Second paragraph of content.

        Third paragraph here.

        ```{jinja}

        {{ undefined_variable }}
        ```

        After.
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    # the ``{jinja}`` fence opens on document line 9
    assert "index.md:9: WARNING: Error rendering jinja template: UndefinedError" in result.stderr
    # and specifically NOT at the bogus content_offset-derived line near the top
    assert "index.md:2:" not in result.stderr


def test_heading(tmp_path: Path, snapshot_doctree):
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====

        .. jinja::

            Same level
            ==========

        .. jinja::

            Different level
            ---------------
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_template_inheritance(tmp_path: Path, snapshot_doctree):
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "base.jinja").write_text(
        dedent(
            """\
        Hallo
        {% block content %}
        {% endblock %}
        """
        )
    )
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====

        .. jinja::

            {% extends "base.jinja" %}
            {% block content %}
            there
            {% endblock %}
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree

    # test that changing the base template triggers a rebuild of index
    (tmp_path / "base.jinja").write_text(
        dedent(
            """\
        Goodbye
        {% block content %}
        {% endblock %}
        """
        )
    )
    result = run_sphinxbuild(tmp_path, clear_build=False)
    assert not result.stderr
    assert result.doctree() == snapshot_doctree


def test_include_outside_srcdir(tmp_path: Path):
    """Test that templates outside the source directory cannot be loaded,
    via absolute paths or parent-directory traversal
    (a leading '/' is simply treated as relative to the source directory).
    """
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP_SECRET")
    (srcdir / "conf.py").write_text(CONF_CONTENT)
    (srcdir / "inside.jinja").write_text("in-srcdir")
    (srcdir / "index.rst").write_text(
        dedent(
            f"""\
        Test
        ====
        .. jinja::

            {{% include "/inside.jinja" %}}

        .. jinja::

            {{% include "../secret.txt" %}}

        .. jinja::

            {{% include "{secret.as_posix()}" %}}

        .. jinja::

            {{% include "sub/../../secret.txt" %}}
        """
        )
    )
    result = run_sphinxbuild(srcdir)
    print(result.stderr)
    assert result.stderr.count("WARNING: Error rendering jinja template: TemplateNotFound") == 3
    html = (result.build / "html" / "index.html").read_text(encoding="utf8")
    assert "in-srcdir" in html
    assert "TOP_SECRET" not in html


def test_file_bom(tmp_path: Path):
    """A UTF-8 BOM at the start of a :file: template is stripped (fix 1).

    Without stripping, the leading U+FEFF widens the heading text past its
    underline, producing a "Title underline too short" warning.
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "template.jinja").write_bytes(b"\xef\xbb\xbfHeading\n=======\n")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: template.jinja
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    assert "\ufeff" not in result.doctree().astext()


def test_include_bom(tmp_path: Path):
    """A UTF-8 BOM in an ``{% include %}``-d template is stripped (fix 1)."""
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "partial.jinja").write_bytes(b"\xef\xbb\xbfincluded")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            before {% include "partial.jinja" %} after
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    text = result.doctree().astext()
    assert "\ufeff" not in text
    assert "included" in text


def test_raw_format_normalized(tmp_path: Path):
    """A non-normalized :raw: format (upper case) is lower-cased (fix 2),
    so docutils writers recognize it and the content is not silently dropped.
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :ctx: {"name": "World"}
            :raw: HTML

            Hello <em>{{ name }}</em>
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert not result.stderr
    raw_formats = [node["format"] for node in result.doctree().findall(nodes.raw)]
    assert raw_formats == ["html"]
    html = (result.build / "html" / "index.html").read_text(encoding="utf8")
    assert "Hello <em>World</em>" in html


def test_raw_empty_validated_before_render(tmp_path: Path):
    """An empty :raw: option is validated *before* rendering (fix 2):
    combined with an undefined variable, only the raw warning fires and the
    render never runs (so no render-error warning appears).
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :raw:

            {{ undefined_variable }}
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert "'raw' option requires an output format" in result.stderr
    assert "Error rendering jinja template" not in result.stderr


def test_warning_subtypes_suppressible(tmp_path: Path):
    """Warnings carry a ``jinja2.<subtype>`` so they can be suppressed
    granularly (fix 3). A render error is suppressed by ``jinja2.render`` but
    not by ``jinja2.config`` (version-independent, unlike asserting the tag).
    """
    index = dedent(
        """\
        Test
        ====
        .. jinja::

            {{ undefined_variable }}
        """
    )
    # suppressing the render subtype removes the warning entirely
    (tmp_path / "conf.py").write_text(CONF_CONTENT + '\nsuppress_warnings = ["jinja2.render"]')
    (tmp_path / "index.rst").write_text(index)
    result = run_sphinxbuild(tmp_path)
    assert result.stderr == ""

    # suppressing a different subtype leaves the render warning in place
    (tmp_path / "conf.py").write_text(CONF_CONTENT + '\nsuppress_warnings = ["jinja2.config"]')
    result = run_sphinxbuild(tmp_path, clear_build=False)
    assert "Error rendering jinja template" in result.stderr


def test_render_error_inline_line_accurate(tmp_path: Path):
    """An inline render error is reported at the actual failing document line,
    not the directive's first line (fix 4).
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::

            line one ok
            line two ok
            {{ boom }} here
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    # the directive is on line 3, but the failing content is the 3rd content
    # line, i.e. document line 7 (content_offset 4 + template line 3)
    assert "index.rst:7: WARNING: Error rendering jinja template: UndefinedError" in result.stderr
    # the directive's own line is no longer reported for the render error
    assert "index.rst:3: WARNING: Error rendering" not in result.stderr
    # minijinja's own " (in index:N)" position suffix is stripped for inline errors
    assert "(in " not in result.stderr


def test_render_error_file_position(tmp_path: Path):
    """A render error in a :file: template keeps the directive location, but
    appends the (relative) template position to the message (fix 4).
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "template.jinja").write_text("ok line\n{{ boom }}\n")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :file: template.jinja
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert (
        "index.rst:3: WARNING: Error rendering jinja template: UndefinedError: "
        "undefined value (template.jinja:2)" in result.stderr
    )


def test_render_error_debug_code_frame(tmp_path: Path):
    """In debug mode, a render error includes minijinja's caret code-frame,
    ideal for debugging (fix 4).
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :debug:

            {{ missing }}
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert "Error rendering jinja template:" in result.stderr
    # the caret code-frame (only present in debug mode) points at the token;
    # the one-line non-debug message would contain no carets
    assert "^^^" in result.stderr


def test_non_dict_contexts(tmp_path: Path):
    """A non-dict ``jinja2_contexts`` is handled gracefully with a warning,
    rather than aborting the whole build with an unhandled TypeError (fix 5).
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT + "\njinja2_contexts = ['item']")
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja:: item

            hallo
        """
        )
    )
    # must not raise (previously an unhandled TypeError aborted the build)
    result = run_sphinxbuild(tmp_path)
    assert "Expected jinja2_contexts to be a dict, got list" in result.stderr
    assert (result.build / "html" / "index.html").exists()


def test_reserved_env_key(tmp_path: Path):
    """Defining ``env`` in a context warns (it shadows the reserved Sphinx
    environment variable), but the override is still applied (fix 6).
    """
    (tmp_path / "conf.py").write_text(CONF_CONTENT)
    (tmp_path / "index.rst").write_text(
        dedent(
            """\
        Test
        ====
        .. jinja::
            :ctx: {"env": "overridden"}

            value is {{ env }}
        """
        )
    )
    result = run_sphinxbuild(tmp_path)
    assert "reserved key 'env'" in result.stderr
    assert "value is overridden" in result.doctree().astext()
