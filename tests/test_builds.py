from __future__ import annotations

from pathlib import Path
import pickle
import shutil
import subprocess
from textwrap import dedent

from docutils import nodes


class BuildResult:
    def __init__(self, build: Path, stdout: Path, stderr: Path) -> None:
        self._build = build
        self._stdout = stdout
        self._stderr = stderr

    @property
    def build(self) -> Path:
        return self._build

    @property
    def stdout(self) -> str:
        return self._stdout.read_text()

    @property
    def stderr(self) -> str:
        return self._stderr.read_text()

    def doctree(self, docname: str = "index") -> nodes.document:
        path = self._build / "doctrees" / f"{docname}.doctree"
        doc = pickle.loads(path.read_bytes())
        assert isinstance(doc, nodes.document)
        return doc


def run_sphinxbuild(path: Path, clear_build: bool = True) -> BuildResult:
    build_path = path / "_build"
    if clear_build and build_path.is_dir():
        shutil.rmtree("_build")
    build_path.mkdir(exist_ok=True)
    log_path = build_path / "logs"
    while log_path.exists():
        log_path = log_path.with_name(log_path.name + "_")
    log_path.mkdir()
    stdout_file = log_path / "stdout.txt"
    stderr_file = log_path / "stderr.txt"
    with stdout_file.open("w") as sphinx_stdout, stderr_file.open("w") as sphinx_stderr:
        try:
            subprocess.check_call(
                ["python", "-m", "sphinx", "-M", "html", str(path), str(build_path), "-T"],
                stdout=sphinx_stdout,
                stderr=sphinx_stderr,
            )
        except subprocess.CalledProcessError:
            print(stdout_file.read_text())
            print(stderr_file.read_text())
            raise

    return BuildResult(build_path, stdout_file, stderr_file)


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
    assert (
        "index.rst:3: WARNING: Error rendering jinja template: UndefinedError: undefined value"
        in result.stderr
    )


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
    for stderr_line in result.stderr.splitlines():
        assert "cannot cache unpickleable configuration value" in stderr_line
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

            {{% include "{secret}" %}}

        .. jinja::

            {{% include "sub/../../secret.txt" %}}
        """
        )
    )
    result = run_sphinxbuild(srcdir)
    print(result.stderr)
    assert result.stderr.count("WARNING: Error rendering jinja template: TemplateNotFound") == 3
    html = (result.build / "html" / "index.html").read_text()
    assert "in-srcdir" in html
    assert "TOP_SECRET" not in html
