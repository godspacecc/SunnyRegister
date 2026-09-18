from pathlib import Path

import install_camoufox


def test_browser_asset_url_is_pinned() -> None:
    assert install_camoufox.browser_asset_url("x86_64") == (
        "https://github.com/daijro/camoufox/releases/download/"
        "v152.0.4-beta.28/camoufox-152.0.4-beta.28-lin.x86_64.zip"
    )


def test_download_with_resume_retries_partial_response(monkeypatch, tmp_path: Path) -> None:
    payload = b"complete-browser-archive"
    ranges: list[str | None] = []

    class FakeResponse:
        def __init__(self, start: int, interrupted: bool) -> None:
            self.status_code = 206 if start else 200
            self.headers = {
                "Content-Length": str(len(payload) - start),
                "Content-Range": f"bytes {start}-{len(payload) - 1}/{len(payload)}",
            }
            self._start = start
            self._interrupted = interrupted

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            del chunk_size
            if self._interrupted:
                yield payload[:8]
                raise install_camoufox.requests.ConnectionError("connection reset")
            yield payload[self._start :]

    def fake_get(_url, *, headers, stream, timeout):
        del stream, timeout
        range_header = headers.get("Range")
        ranges.append(range_header)
        start = int(range_header.removeprefix("bytes=").removesuffix("-")) if range_header else 0
        return FakeResponse(start, interrupted=len(ranges) == 1)

    monkeypatch.setattr(install_camoufox.requests, "get", fake_get)
    monkeypatch.setattr(install_camoufox.time, "sleep", lambda _seconds: None)
    target = tmp_path / "camoufox.zip"

    install_camoufox.download_with_resume("https://example.invalid/camoufox.zip", target)

    assert target.read_bytes() == payload
    assert ranges == [None, "bytes=8-"]


def test_download_with_resume_accepts_complete_cached_file(monkeypatch, tmp_path: Path) -> None:
    payload = b"complete-browser-archive"
    target = tmp_path / "camoufox.zip"
    target.write_bytes(payload)

    class RangeNotSatisfiableResponse:
        status_code = 416
        headers = {"Content-Range": f"bytes */{len(payload)}"}

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def raise_for_status(self) -> None:
            raise install_camoufox.requests.HTTPError("range not satisfiable")

    monkeypatch.setattr(
        install_camoufox.requests,
        "get",
        lambda *_args, **_kwargs: RangeNotSatisfiableResponse(),
    )

    install_camoufox.download_with_resume(
        "https://example.invalid/camoufox.zip",
        target,
        attempts=1,
    )

    assert target.read_bytes() == payload


def test_install_browser_uses_resumable_fetcher(monkeypatch) -> None:
    installers: list[str] = []

    class DirectFetcher:
        def __init__(self, **_kwargs) -> None:
            pass

        def install(self, *, replace: bool) -> None:
            del replace
            installers.append("direct")

    class ResumableFetcher(DirectFetcher):
        def install(self, *, replace: bool) -> None:
            del replace
            installers.append("resumable")

    monkeypatch.setattr(install_camoufox, "CamoufoxFetcher", DirectFetcher)
    monkeypatch.setattr(
        install_camoufox,
        "ResumableCamoufoxFetcher",
        ResumableFetcher,
        raising=False,
    )

    install_camoufox.install_browser()

    assert installers == ["resumable"]
