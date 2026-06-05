from pathlib import Path

from backend.video.preview import (
    resolve_youtube_slides_pdf,
    youtube_video_id_from_source,
)


def test_youtube_video_id_from_source():
    assert youtube_video_id_from_source("youtube:KAlCMLHBXNQ") == "KAlCMLHBXNQ"
    assert youtube_video_id_from_source("data/raw/report.pdf") is None


def test_resolve_youtube_slides_pdf(tmp_path: Path):
    video_id = "KAlCMLHBXNQ"
    slides_dir = tmp_path / "youtube" / video_id
    slides_dir.mkdir(parents=True)
    slides_pdf = slides_dir / "slides.pdf"
    slides_pdf.write_bytes(b"%PDF-1.4 slides")

    resolved = resolve_youtube_slides_pdf(f"youtube:{video_id}", tmp_path)
    assert resolved == slides_pdf.resolve()


def test_resolve_youtube_slides_pdf_missing(tmp_path: Path):
    assert resolve_youtube_slides_pdf("youtube:missing", tmp_path) is None
