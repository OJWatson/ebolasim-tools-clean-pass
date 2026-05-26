import json
from pathlib import Path

import yaml


def _nav_paths(items):
    for item in items:
        for value in item.values():
            if isinstance(value, str):
                yield value
            else:
                yield from _nav_paths(value)


def test_mkdocs_nav_points_to_notebooks():
    config = yaml.safe_load(Path("mkdocs.yml").read_text(encoding="utf-8"))
    nav_paths = list(_nav_paths(config["nav"]))

    assert "index.ipynb" in nav_paths
    assert "parameters.ipynb" in nav_paths
    assert "vignettes/ebola2/comparison.ipynb" in nav_paths
    assert "vignettes/ebola2/evidence/comparison_summary.md" in nav_paths
    assert all(path.endswith((".ipynb", ".md")) for path in nav_paths)


def test_documentation_notebooks_are_valid_json():
    for path in [
        Path("docs/index.ipynb"),
        Path("docs/parameters.ipynb"),
        Path("docs/maintainers.ipynb"),
        Path("docs/vignettes/ebola2/comparison.ipynb"),
    ]:
        notebook = json.loads(path.read_text(encoding="utf-8"))
        assert notebook["nbformat"] == 4
        assert notebook["metadata"]["kernelspec"]["name"] == "python3"
        assert notebook["cells"]
