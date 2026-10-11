"""The release check of an installed copy (#11): GitHub's Releases API over
HTTPS, a short timeout, no git, one plain sentence on failure, and the last
answer kept for the next start. A fake HTTP layer stands in for GitHub."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from staffroom.core import update
from staffroom.core.update import Release, ReleaseCheck

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
# Taken at import, before the root conftest swaps in its offline transport.
REAL_HTTPS_GET = update.https_get


def github(tag: str = "v0.9.0", **extra: object) -> bytes:
    data: dict[str, object] = {
        "tag_name": tag,
        "name": tag,
        "html_url": f"https://github.com/ColePoppleton/Staffroom/releases/tag/{tag}",
        "published_at": "2026-10-14T15:29:17Z",
        "draft": False,
        "prerelease": False,
        "body": "### Changed\n- A thing.\n",
    }
    data.update(extra)
    return json.dumps(data).encode()


class FakeGitHub:
    def __init__(self, body: bytes = b"", error: Exception | None = None) -> None:
        self.body, self.error = body, error
        self.asked: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout: float) -> bytes:
        self.asked.append((url, timeout))
        if self.error is not None:
            raise self.error
        return self.body


@pytest.fixture(autouse=True)
def no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"the release check ran a command: {args}")

    monkeypatch.setattr(update.subprocess, "run", refuse)


def test_a_newer_release_is_read_from_the_releases_api() -> None:
    fake = FakeGitHub(github())
    check = update.check_latest_release(fake, now=NOW)
    assert fake.asked == [(update.RELEASES_API, update.RELEASE_TIMEOUT)]
    assert update.RELEASES_API.startswith("https://api.github.com/")
    assert update.RELEASE_TIMEOUT <= 10
    assert check.ok and check.error == ""
    assert check.release == Release(
        "0.9.0",
        "https://github.com/ColePoppleton/Staffroom/releases/tag/v0.9.0",
        "2026-10-14",
        "### Changed\n- A thing.\n",
    )
    assert check.checked_at == NOW
    assert check.newer_than("0.8.1") is True
    assert check.newer_than("0.9.0") is False
    assert check.newer_than("1.0.0") is False


@pytest.mark.parametrize(
    "error",
    [
        OSError("no route to host"),
        urllib.error.URLError("nodename nor servname provided"),
        urllib.error.HTTPError(update.RELEASES_API, 403, "rate limited", {}, None),  # type: ignore[arg-type]
        TimeoutError("timed out"),
    ],
)
def test_a_failed_check_is_one_plain_sentence_and_claims_nothing(error: Exception) -> None:
    check = update.check_latest_release(FakeGitHub(error=error), now=NOW)
    assert not check.ok and check.release is None
    assert check.error == update.UNREACHABLE
    assert check.error.count(".") == 1 and "up to date" not in check.error
    assert check.newer_than("0.8.1") is None  # neither newer nor "up to date"


@pytest.mark.parametrize(
    "body",
    [
        b"<html>captive portal</html>",
        b"[]",
        github(tag="nightly"),
        github(draft=True),
        github(prerelease=True),
        b"\xff\xfe",
    ],
)
def test_an_answer_without_a_release_is_unreadable_not_up_to_date(body: bytes) -> None:
    check = update.check_latest_release(FakeGitHub(body), now=NOW)
    assert check.error == update.UNREADABLE
    assert check.newer_than("0.8.1") is None


def test_a_strange_release_url_falls_back_to_the_releases_page() -> None:
    check = update.check_latest_release(FakeGitHub(github(html_url="javascript:x")), now=NOW)
    assert check.release is not None
    assert check.release.url == f"{update.RELEASES_PAGE}/tag/v0.9.0"


def test_the_real_transport_is_https_only_and_sends_nothing_about_the_teacher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[urllib.request.Request] = []

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            assert limit == update.MAX_RESPONSE
            return b"{}"

    def urlopen(request: urllib.request.Request, timeout: float) -> Response:
        seen.append(request)
        assert timeout == 5.0
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert REAL_HTTPS_GET(update.RELEASES_API, 5.0) == b"{}"
    (request,) = seen
    assert request.full_url == update.RELEASES_API
    assert request.get_method() == "GET" and request.data is None
    assert {k.lower(): v for k, v in request.header_items()} == {
        "accept": "application/vnd.github+json",
        "user-agent": "Staffroom",
    }
    with pytest.raises(ValueError, match="non-HTTPS"):
        REAL_HTTPS_GET("http://api.github.com/repos/x", 5.0)


def test_tests_never_reach_the_network() -> None:
    """The root conftest's guard: an unfaked check fails like no network."""
    assert update.check_latest_release().error == update.UNREACHABLE


# -- kept for the next start --------------------------------------------------


def test_the_answer_round_trips_through_the_cache(isolated_home: Path) -> None:
    check = update.check_latest_release(FakeGitHub(github()), now=NOW)
    assert update.save_release_check(check)
    assert update.release_cache_file() == isolated_home / "release-check.json"
    assert update.load_release_check() == check
    failed = ReleaseCheck(NOW, error=update.UNREACHABLE)
    update.save_release_check(failed)
    assert update.load_release_check() == failed


@pytest.mark.parametrize(
    "text",
    ["", "not json", "[]", '{"checked_at": "x"}', '{"checked_at": "2026-10-15T09:00:00+00:00"}'],
)
def test_an_unreadable_cache_is_no_answer(isolated_home: Path, text: str) -> None:
    isolated_home.mkdir(parents=True, exist_ok=True)
    (isolated_home / "release-check.json").write_text(text)
    assert update.load_release_check() is None


def test_a_cache_that_cannot_be_written_is_not_an_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("")
    assert not update.save_release_check(ReleaseCheck(NOW, error="x"), blocker / "c.json")


def test_the_start_check_asks_at_most_once_a_day() -> None:
    assert update.release_check_due(None, NOW)
    for hours, due in [(0, False), (23, False), (24, True), (48, True), (-2, True)]:
        last = ReleaseCheck(NOW - timedelta(hours=hours), error=update.UNREACHABLE)
        assert update.release_check_due(last, NOW) is due, hours


# -- words --------------------------------------------------------------------


def test_versions_dates_ages_and_notes() -> None:
    assert update.version_key("v0.10.0") == (0, 10, 0) > (update.version_key("0.9.9") or ())
    assert update.version_key("0.9.0rc1") is None
    assert update.release_date_text("2026-10-04T08:00:00Z") == "4 Oct 2026"
    assert update.release_date_text("") == ""
    assert update.age_text(NOW - timedelta(seconds=5), NOW) == "just now"
    assert update.age_text(NOW - timedelta(minutes=1), NOW) == "1 minute ago"
    assert update.age_text(NOW - timedelta(minutes=2), NOW) == "2 minutes ago"
    assert update.age_text(NOW - timedelta(hours=3), NOW) == "3 hours ago"
    assert update.age_text(NOW - timedelta(hours=30), NOW) == "yesterday"
    assert update.age_text(NOW - timedelta(days=9), NOW) == "on 6 Oct 2026"
    notes = "Intro\n\n![Settings](https://x/y.png)\n<img src='z.png'>\n<!-- hidden -->\n\n\n- one"
    assert update.notes_for_display(notes) == "Intro\n\n- one"
    assert update.notes_for_display("  ") == "This release has no notes."
    # The release body folds the contributors' list (scripts/release.py).
    folded = (
        "Teachers.\n\n<details>\n<summary>For contributors</summary>\n\n### Added\n- a\n</details>"
    )
    assert update.notes_for_display(folded) == (
        "Teachers.\n\n#### For contributors\n\n### Added\n- a"
    )
