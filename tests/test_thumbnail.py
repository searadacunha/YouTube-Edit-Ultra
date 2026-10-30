import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image

from youtube_edit_ultra import thumbnail
from youtube_edit_ultra.media import UltraError
from youtube_edit_ultra.planner import Edit


def shot(source, peak=.5):
    return Edit(str(source), 0, 1, 0, 1, "fixture", peak, "heuristic", .2)


@pytest.mark.parametrize("status,data", [(1, b""), (0, b""), (0, b"broken jpeg")])
def test_storyboard_frame_failure_is_explicit(tmp_path, monkeypatch, status, data):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=status, stdout=data, stderr=b"decoder failure"))
    out = tmp_path / "storyboard.jpg"
    with pytest.raises(UltraError, match=r"plan 1.*source.mp4.*0.500"):
        thumbnail.create_storyboard([shot(tmp_path / "source.mp4")], out, columns=1, rows=1)
    assert not out.exists()


def test_storyboard_uses_zero_peak_and_writes_actual_frames(tmp_path):
    source = tmp_path / "tiny.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "color=red:s=32x32:r=10:d=0.4", "-c:v", "libx264", str(source)],
                   check=True, capture_output=True)
    # The midpoint is beyond EOF: only the explicit zero peak is a valid frame.
    out = thumbnail.create_storyboard([shot(source, peak=0)], tmp_path / "storyboard.jpg",
                                      columns=1, rows=1)
    with Image.open(out) as image:
        red, green, blue = image.getpixel((100, 90))
    assert red > 200 and green < 30 and blue < 30
