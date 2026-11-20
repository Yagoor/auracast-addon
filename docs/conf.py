"""Sphinx configuration for the Auracast add-on documentation."""

import os
from importlib.metadata import version as package_version

project = "Auracast add-on"
author = "Yagoor"
copyright = "Yagoor"
release = package_version("auracast-player")
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.plantuml",
]

exclude_patterns = ["_build", "design/*.puml", "design/*.png"]

# The diagrams are rendered from docs/design/*.puml on every build. CI points PLANTUML at its
# pinned jar; locally the `plantuml` on the PATH is used.
plantuml = os.environ.get("PLANTUML", "plantuml")
plantuml_output_format = "svg_img"

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "show-inheritance": True}
autodoc_typehints = "description"
# Only this project's docstrings: the libraries' (python-statemachine, Bumble) use other markup.
autodoc_inherit_docstrings = False

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

html_theme = "furo"
html_title = "Auracast add-on"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_favicon = "_static/icon.png"
html_theme_options = {
    "light_logo": "logo.png",
    "dark_logo": "dark_logo.png",
    "sidebar_hide_name": True,
    "source_repository": "https://github.com/Yagoor/auracast-addon/",
    "source_branch": "main",
    "source_directory": "docs/",
    "light_css_variables": {"color-brand-primary": "#0064d2", "color-brand-content": "#0064d2"},
    "dark_css_variables": {"color-brand-primary": "#5eaaff", "color-brand-content": "#5eaaff"},
}
