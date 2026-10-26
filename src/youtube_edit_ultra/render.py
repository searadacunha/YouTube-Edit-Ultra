"""FFmpeg renderer: natural color, original movement, ambience under music."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .media import UltraError, ffmpeg_encode_args, fingerprint, probe, run
from .planner import Edit


def render_segment(edit: Edit, out: Path, *, width: int, height: int, fps: int) -> None:
    """Source windows are never shortened, sped up, or interrupted at music beats."""
    source = Path(edit.source)
    d = edit.duration
    info = probe(source)
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p")
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{edit.source_start:.4f}", "-i", str(source)]
    if info["has_audio"]:
        audio_source = "0:a:0"
    else:
        cmd += ["-f", "lavfi", "-t", f"{d:.4f}", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_source = "1:a:0"
    # Timestamp zero for every segment prevents concat DTS issues.
    graph = (f"[0:v:0]{vf},trim=duration={d:.4f},setpts=PTS-STARTPTS[v];"
             f"[{audio_source}]aresample=48000,aformat=channel_layouts=stereo,"
             f"atrim=duration={d:.4f},asetpts=PTS-STARTPTS[a]")
    cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", f"{d:.4f}",
            *ffmpeg_encode_args(), "-r", str(fps), "-c:a", "aac", "-b:a", "128k",
            "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(out)]
    run(cmd)
    result = probe(out)
    if abs(result["duration"] - d) > max(0.12, 3 / fps):
        raise UltraError(f"Écart de durée segment rendu : {source.name}, {result['duration']} au lieu de {d}")


def render_edits(edits: list[Edit], soundtrack: Path, output: Path, cache_dir: Path,
                 *, width: int = 1280, height: int = 720, fps: int = 30,
                 source_volume: float = 0.22, music_volume: float = 0.86) -> dict:
    if not edits:
        raise UltraError("Timeline vide")
    cache_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []
    for idx, edit in enumerate(edits, 1):
        payload = (f"{fingerprint(Path(edit.source))}:{edit.source_start:.4f}:"
                   f"{edit.source_end:.4f}:{width}:{height}:{fps}:v1")
        key = hashlib.sha256(payload.encode()).hexdigest()[:24]
        segment = cache_dir / f"clip-{key}.mp4"
        if not segment.is_file():
            tmp = cache_dir / f".clip-{key}.partial.mp4"
            print(f"Rendu action {idx}/{len(edits)} : {edit.label} ({edit.duration:.1f}s)")
            render_segment(edit, tmp, width=width, height=height, fps=fps)
            tmp.replace(segment)
        segments.append(segment)
    # concat list written in cache_dir, paths escaped for ffmpeg demuxer.
    lines = ["file '" + str(p.resolve()).replace("'", "'\\''") + "'" for p in segments]
    manifest = cache_dir / "concat-list.txt"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assembled = cache_dir / "assembled-video.mp4"
    run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", str(assembled)])
    # Two simultaneous sound layers: preserve original stadium/crowd/ring ambience.
    graph = (f"[0:a:0]volume={source_volume:.4f}[atmo];"
             f"[1:a:0]volume={music_volume:.4f}[song];"
             f"[atmo][song]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
             f"alimiter=limit=0.95[aout]")
    target = edits[-1].timeline_end
    run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(assembled), "-i", str(soundtrack), "-filter_complex", graph,
         "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "256k", "-t", f"{target:.4f}", "-movflags", "+faststart", str(output)])
    actual = probe(output)
    if not actual["has_video"] or not actual["has_audio"]:
        raise UltraError("Validation MP4 échouée : flux vidéo ou musical absent")
    if abs(actual["duration"] - target) > 0.45:
        raise UltraError(f"Durée finale incorrecte : attendu {target:.2f}s, obtenu {actual['duration']:.2f}s")
    return {"output": str(output), "duration": actual["duration"],
            "resolution": f"{actual['width']}x{actual['height']}",
            "audio_mixed": True, "source_ambience_volume": source_volume}
