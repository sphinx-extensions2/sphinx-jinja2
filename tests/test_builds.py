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
        "index.rst:3: WARNING: Error rendering jinja template: UndefinedError: 'a' is undefined"
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
