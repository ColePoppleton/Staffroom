"""The issue forms outside reporters see on *New issue* (#15).

The repository is public, so an issue is the one route by which a real marks
file or a screenshot with names could reach the project. Each form must:

* load as YAML and have the shape GitHub's issue-form schema asks for (a
  malformed form silently disappears from the chooser);
* carry a **required** tick box saying nothing from school is attached;
* go to triage, never straight onto the board as ``status:ready``.

``config.yml`` turns blank issues off and links the docs, the Privacy page and
the private reporting route; ``SECURITY.md`` and the contributing guide point
at them.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"
TEMPLATES = GITHUB / "ISSUE_TEMPLATE"
CONFIG = TEMPLATES / "config.yml"
FORMS = sorted(p for p in TEMPLATES.glob("*.yml") if p.name != "config.yml")
REPO = "https://github.com/ColePoppleton/Staffroom"
SITE = "https://colepoppleton.github.io/Staffroom/"
PRIVATE_REPORT = f"{REPO}/security/advisories/new"

# Element types GitHub accepts in an issue form body.
TYPES = {"markdown", "textarea", "input", "dropdown", "checkboxes"}
TRIAGE = "status:triage"


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path.name} has no front matter"
    data = yaml.safe_load(match.group(1))
    assert isinstance(data, dict)
    return data


def labels_of(data: dict[str, Any]) -> list[str]:
    labels = data.get("labels") or []
    if isinstance(labels, str):
        labels = [part.strip() for part in labels.split(",")]
    return list(labels)


def test_there_is_a_bug_form_and_an_idea_form() -> None:
    names = {load(p)["name"] for p in FORMS}
    assert {"Bug report", "Idea for a tool or change"} <= names


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_form_matches_the_issue_form_schema(path: Path) -> None:
    form = load(path)
    assert isinstance(form, dict)
    for key in ("name", "description", "body"):
        assert form.get(key), f"{path.name}: missing {key}"
    ids: list[str] = []
    for element in form["body"]:
        kind = element.get("type")
        assert kind in TYPES, f"{path.name}: unknown element type {kind!r}"
        attributes = element.get("attributes") or {}
        if kind == "markdown":
            assert attributes.get("value"), f"{path.name}: empty markdown block"
            assert "id" not in element
            continue
        assert attributes.get("label"), f"{path.name}: a {kind} has no label"
        if kind in ("dropdown", "checkboxes"):
            assert attributes.get("options"), f"{path.name}: a {kind} has no options"
        if "id" in element:
            assert re.fullmatch(r"[A-Za-z0-9_-]+", element["id"]), element["id"]
            ids.append(element["id"])
    assert len(ids) == len(set(ids)), f"{path.name}: duplicate element ids"
    assert any(e["type"] != "markdown" for e in form["body"]), "a form needs a field"


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_form_requires_the_no_school_files_tick_box(path: Path) -> None:
    required = [
        option["label"]
        for element in load(path)["body"]
        if element["type"] == "checkboxes"
        for option in element["attributes"]["options"]
        if (option.get("required") is True)
    ]
    assert any(
        "real marks" in label and "names" in label and "invented" in label for label in required
    ), f"{path.name}: no required tick box about real marks, names and invented examples"


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_form_warns_before_the_first_field_and_points_at_the_examples(path: Path) -> None:
    body = load(path)["body"]
    first = body[0]
    assert first["type"] == "markdown", f"{path.name}: the warning must come first"
    text = first["attributes"]["value"]
    assert "public" in text
    assert f"{REPO}/tree/main/examples" in text


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_form_goes_to_triage_not_the_board(path: Path) -> None:
    labels = labels_of(load(path))
    assert TRIAGE in labels
    assert "status:ready" not in labels


def test_bug_form_asks_for_version_macos_and_install() -> None:
    form = next(load(p) for p in FORMS if load(p)["name"] == "Bug report")
    fields = {e.get("id"): e for e in form["body"] if e["type"] != "markdown"}
    for key in ("did", "expected", "happened", "version", "macos", "install"):
        assert key in fields, f"bug form has no {key!r} field"
        assert fields[key].get("validations", {}).get("required") is True, key
    assert "sidebar" in fields["version"]["attributes"]["description"]
    assert "staff version" in fields["version"]["attributes"]["description"]


def test_no_template_puts_a_report_straight_on_the_board() -> None:
    for path in TEMPLATES.glob("*.md"):
        assert "status:ready" not in labels_of(front_matter(path)), path.name


def test_the_maintainer_task_template_stays() -> None:
    task = front_matter(TEMPLATES / "3-task.md")
    assert "maintainers" in task["name"].lower()
    assert not labels_of(task)


def test_config_disables_blank_issues_and_links_docs_and_privacy() -> None:
    config = load(CONFIG)
    assert config["blank_issues_enabled"] is False
    urls = [link["url"] for link in config["contact_links"]]
    for link in config["contact_links"]:
        assert link.get("name") and link.get("about"), link
    assert SITE in urls
    assert f"{SITE}guide/privacy/" in urls
    assert PRIVATE_REPORT in urls
    assert (ROOT / "docs" / "guide" / "privacy.md").is_file()


def test_security_note_names_the_private_route() -> None:
    text = (GITHUB / "SECURITY.md").read_text(encoding="utf-8")
    assert PRIVATE_REPORT in text
    assert "privacy" in text.lower()


def test_contributing_guide_links_the_forms() -> None:
    text = (ROOT / "docs" / "contributing.md").read_text(encoding="utf-8")
    assert f"{REPO}/issues/new/choose" in text
    assert "SECURITY.md" in text
