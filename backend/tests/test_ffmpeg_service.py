import zipfile

from app.services import ffmpeg_service


def test_extract_binaries_keeps_shared_build_dlls(tmp_path, monkeypatch):
    bin_dir = tmp_path / "installed" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "stale.dll").write_bytes(b"old")
    archive = tmp_path / "ffmpeg.zip"

    with zipfile.ZipFile(archive, "w") as zf:
        root = "ffmpeg-master-latest-win64-gpl-shared/bin"
        zf.writestr(f"{root}/ffmpeg.exe", b"ffmpeg")
        zf.writestr(f"{root}/ffprobe.exe", b"ffprobe")
        zf.writestr(f"{root}/avdevice-63.dll", b"avdevice")
        zf.writestr("ffmpeg-master-latest-win64-gpl-shared/README.txt", b"docs")

    monkeypatch.setattr(ffmpeg_service, "_get_bundled_bin_dir", lambda: bin_dir)

    ffmpeg_service._extract_binaries(str(archive))

    assert (bin_dir / "ffmpeg.exe").read_bytes() == b"ffmpeg"
    assert (bin_dir / "ffprobe.exe").read_bytes() == b"ffprobe"
    assert (bin_dir / "avdevice-63.dll").read_bytes() == b"avdevice"
    assert not (bin_dir / "stale.dll").exists()
    assert not (bin_dir / "README.txt").exists()
