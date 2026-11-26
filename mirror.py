# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "certifi==2026.10.19",
#   "packaging==23.1",
#   "urllib3==2.0.5",
# ]
# ///
"""Update muff-pre-commit to the latest version of muff."""

import re
import subprocess
import tomllib
import typing
from pathlib import Path

import certifi
import urllib3
from packaging.requirements import Requirement
from packaging.version import Version


def main():
    with open(Path(__file__).parent / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)

    all_versions = get_all_versions()
    current_version = get_current_version(pyproject=pyproject)
    target_versions = [v for v in all_versions if v > current_version]

    for version in target_versions:
        paths = process_version(version)
        if subprocess.check_output(["git", "status", "-s"]).strip():
            subprocess.run(["git", "add", *paths], check=True)
            subprocess.run(["git", "commit", "-m", f"Mirror: {version}"], check=True)
            # Muff tags have no "v" prefix (for example, "0.17.6"), unlike Ruff's.
            subprocess.run(["git", "tag", f"{version}"], check=True)
        else:
            print(f"No change {version}")


def get_all_versions() -> list[Version]:
    http = urllib3.PoolManager(ca_certs=certifi.where())
    response = http.request("GET", "https://pypi.org/pypi/muff/json")
    if response.status != 200:
        raise RuntimeError("Failed to fetch versions from pypi")

    versions = [Version(release) for release in response.json()["releases"]]
    return sorted(versions)


def get_current_version(pyproject: dict) -> Version:
    requirements = [Requirement(d) for d in pyproject["project"]["dependencies"]]
    requirement = next((r for r in requirements if r.name == "muff"), None)
    assert requirement is not None, "pyproject.toml does not have muff requirement"

    specifiers = list(requirement.specifier)
    assert (
        len(specifiers) == 1 and specifiers[0].operator == "=="
    ), f"muff's specifier should be exact matching, but `{requirement}`"

    return Version(specifiers[0].version)


def process_version(version: Version) -> typing.Sequence[str]:
    def replace_pyproject_toml(content: str) -> str:
        return re.sub(r'"muff==.*"', f'"muff=={version}"', content)

    # README.md is not updated: its Muff examples use a `<LATEST_VERSIN_TAG>`
    # placeholder, and the `rev: vX.Y.Z` lines below them belong to the copy
    # of Ruff's README, which tracks Ruff's version via upstream merges.
    paths = {
        "pyproject.toml": replace_pyproject_toml,
    }

    for path, replacer in paths.items():
        with open(path) as f:
            content = replacer(f.read())
        with open(path, mode="w") as f:
            f.write(content)

    return tuple(paths.keys())


if __name__ == "__main__":
    main()
