from pathlib import Path


def test_playwright_browser_downloads_use_separate_cacheable_layers() -> None:
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")

    assert "python -m playwright install-deps chromium" in dockerfile
    assert "python -m playwright install --no-shell chromium" in dockerfile
    assert "python -m playwright install --only-shell chromium" not in dockerfile
    assert "python -m playwright install --with-deps chromium" not in dockerfile
