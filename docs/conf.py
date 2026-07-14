from pathlib import Path
import sys

from sphinx_jinja2 import __version__

# allow _jinja_funcs.py (example filters/tests) to be importable
sys.path.insert(0, str(Path(__file__).parent))

project = "sphinx-jinja2"
copyright = "Chris Sewell"
version = __version__

extensions = ["sphinx_jinja2"]

html_theme = "furo"
html_title = "sphinx-jinja2"
# html_favicon = "_static/favicon.svg"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
# html_theme_options = {
#     "light_logo": "logo-light-mode.png",
#     "dark_logo": "logo-dark-mode.png",
# }

jinja2_contexts = {"ctx1": {"name": "World"}}
# jinja2_debug = True
jinja2_tests = {"is_big": "_jinja_funcs:is_big"}
