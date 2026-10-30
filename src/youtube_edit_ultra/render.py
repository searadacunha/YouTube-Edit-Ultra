"""FFmpeg renderer: natural color, original movement, ambience under music."""
from __future__ import annotations

import hashlib
import math
import os
import shutil
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from .media import UltraError, ffmpeg_encode_args, fingerprint, floor_bytes, probe, require_space, run
from .planner import Edit


# Disable limiter auto-gain; encoded AAC true peak is still measured by finalization.
AUDIO_LIMITER = "alimiter=limit=0.89:level=0:latency=1"


def estimate_streamed_bytes(duration: float, video_kbps: int = 4000) -> int:
    """Bounded video/audio, muxing margin and temporary 16-bit ambience storage."""
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(video_kbps) or video_kbps <= 0:
        raise ValueError("Positive finite duration and video bitrate required")
    return (int(duration * (video_kbps * 1.25 + 256) * 1000 / 8 * 1.08)
            + int(duration * 48000 * 4))


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
                 source_volume: float = 0.22, music_volume: float = 0.86,
                 reserve_bytes: int | None = None) -> dict:
    if output.exists() or output.is_symlink():
        raise UltraError(f"Preserve existing output: {output}")
    if not edits:
        raise UltraError("Timeline vide")
    if any(e.audio_intent != 'auto' for e in edits):
        raise UltraError('Explicit audio_intent requires the streaming renderer')
    cache_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    reserve = floor_bytes() if reserve_bytes is None else reserve_bytes
    keys = [hashlib.sha256((f"{fingerprint(Path(e.source))}:{e.source_start:.4f}:"
                            f"{e.source_end:.4f}:{width}:{height}:{fps}:v1").encode()).hexdigest()[:24] for e in edits]
    # Upper bound for CRF 21 veryfast at 0.2 bit/pixel plus audio (Canelo V1 1080p: 0.94 MB/s measured, 1.59 bound).
    rate = width * height * fps * 0.2 / 8 + 32_000
    todo = sum(e.duration for e, k in zip(edits, keys) if not (cache_dir / f"clip-{k}.mp4").is_file())
    require_space(cache_dir, int((todo + edits[-1].timeline_end) * rate), "segment render and final mix", reserve)
    segments: list[Path] = []
    for idx, (edit, key) in enumerate(zip(edits, keys), 1):
        segment = cache_dir / f"clip-{key}.mp4"
        if not segment.is_file():
            if shutil.disk_usage(cache_dir).free < reserve:
                raise UltraError(f"Disk reserve reached ({reserve / 1e9:.1f} GB floor) before segment {idx}; "
                                 "finished segments stay cached for a rerun, no partial segment left")
            tmp = cache_dir / f".clip-{key}.partial.mp4"
            print(f"Rendu action {idx}/{len(edits)} : {edit.label} ({edit.duration:.1f}s)")
            render_segment(edit, tmp, width=width, height=height, fps=fps)
            tmp.replace(segment)
        segments.append(segment)
    # concat list written in cache_dir, paths escaped for ffmpeg demuxer.
    # AAC packet padding must not accumulate between actions or truncate the final one.
    lines = ["file '" + str(p.resolve()).replace("'", "'\\''") + "'\n"
             + f"duration {edit.duration:.6f}" for p, edit in zip(segments, edits)]
    manifest = cache_dir / "concat-list.txt"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Two simultaneous sound layers: preserve original stadium/crowd/ring ambience.
    graph = (f"[0:a:0]aresample=48000:async=1:first_pts=0,volume={source_volume:.4f}[atmo];"
             f"[1:a:0]volume={music_volume:.4f}[song];"
             f"[atmo][song]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
             f"{AUDIO_LIMITER}[aout]")
    target = edits[-1].timeline_end
    # The final mix copies every cached segment: re-check with their real size before writing it.
    require_space(output.parent, sum(p.stat().st_size for p in segments), "final mix", reserve)
    run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
         "-f", "concat", "-safe", "0", "-i", str(manifest), "-i", str(soundtrack), "-filter_complex", graph,
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


def render_streamed(edits, soundtrack, output, *, width=1920, height=1080, fps=30,
                    video_kbps=4000, reserve_bytes=None,
                    source_volume=.14, music_volume=1.):
    """One bounded-rate MP4, no disk clip cache; existing originals remain untouched."""
    import shutil
    import subprocess
    from contextlib import suppress
    # Default: the Mac-wide floor (12 GB), checked before and between shots, so a render never pauses PolySentinel.
    reserve_bytes = floor_bytes() if reserve_bytes is None else reserve_bytes
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        raise UltraError(f'Preserve existing output: {output}')
    if not edits or fps <= 0 or video_kbps <= 0:
        raise UltraError('Nonempty timeline, positive FPS and bitrate required')
    if not all(math.isfinite(v) and v >= 0 for v in (source_volume, music_volume)):
        raise UltraError('Audio volumes must be finite and nonnegative')
    at = 0.
    for e in edits:
        if e.duration <= 0 or abs(e.timeline_start-at) > 1e-5 or abs(e.timeline_end-e.timeline_start-e.duration) > 1e-5:
            raise UltraError('Noncontiguous timeline or changed action speed')
        if abs(e.duration*fps-round(e.duration*fps)) > 1e-3:
            raise UltraError('Streaming cuts must be on the output frame grid')
        at = e.timeline_end
    target = edits[-1].timeline_end
    if probe(Path(soundtrack))['duration'] < target-.05:
        raise UltraError('Existing soundtrack shorter than timeline')
    # VBV upper bound plus audio, muxing, the 16-bit ambience file and a separate safety reserve.
    estimate = estimate_streamed_bytes(target, video_kbps)
    if shutil.disk_usage(output.parent).free < estimate + reserve_bytes:
        raise UltraError(f'Insufficient space: need {estimate + reserve_bytes} bytes before streaming render')
    import numpy as np
    def pcm(path, start, k):
        cp = subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(start),'-i',str(path),'-t',str(k/48000),
                             '-vn','-ac','2','-ar','48000','-f','f32le','-'],capture_output=True)
        if cp.returncode:raise UltraError(f'Audio decode failed: {path}: {cp.stderr[-300:]!r}')
        x = np.frombuffer(cp.stdout,np.float32).reshape(-1,2)[:k]
        return np.pad(x,((0,k-len(x)),(0,0)))
    rms = lambda x: float(np.sqrt(np.mean(np.square(x,dtype=np.float64))))+1e-9
    infos = []
    for e in edits:
        info=probe(Path(e.source))
        if not info['has_video'] or e.source_start < 0 or e.source_end > info['duration']+.001:
            raise UltraError(f'Segment outside available video: {e.source}')
        if e.audio_intent == 'featured' and not info['has_audio']:
            raise UltraError(f'Featured audio requested but source has no audio: {e.source}')
        infos.append(info)
    featured = [(e.timeline_start, e.timeline_end) for e in edits if e.audio_intent == 'featured']
    logpath = output.with_suffix('.render.log')
    with NamedTemporaryFile(dir=output.parent, prefix=f'.{output.stem}-',
                            suffix='.ambience.flac', delete=False) as temporary:
        ambience = Path(temporary.name)
    with logpath.open('w') as log:
      try:
        # Mix on the sample clock: per-segment AAC drifted into the next shot (Canelo V2).
        # The same one temporary FLAC now holds music plus ambience; no extra disk copy.
        enc = subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-f','f32le','-ar','48000',
            '-ac','2','-i','pipe:0','-af',AUDIO_LIMITER,'-c:a','flac','-sample_fmt','s16',str(ambience)],stdin=subprocess.PIPE,stdout=log,stderr=log)
        try:
            for e,info in zip(edits,infos):
                k = round(e.timeline_end*48000)-round(e.timeline_start*48000)
                x = np.zeros((k,2),np.float32)
                song = pcm(soundtrack,e.timeline_start,k)
                # Preserve the historical auto behavior. Explicit metadata takes priority;
                # no speech or crowd importance is inferred from a filename or waveform.
                legacy_muted = 'insert' in e.label.lower() or 'intro' in e.label.lower()
                audible = e.audio_intent in ('ambience', 'featured') or (e.audio_intent == 'auto' and not legacy_muted)
                if info['has_audio'] and audible:
                    x = pcm(e.source,e.source_start,k)
                    if e.audio_intent == 'featured':
                        # Bounded gain: quiet material is never amplified more than 6 dB.
                        x *= min(2., .12/rms(x), .7/(float(np.max(np.abs(x)))+1e-9))
                    else:
                        # Ordinary fight ambience remains at least 20 dB under music.
                        x *= min(source_volume,.1*rms(song)/rms(x))
                    ramp = np.linspace(0,1,min(480,k//2),dtype=np.float32)[:,None]
                    x[:len(ramp)] *= ramp
                    x[k-len(ramp):] *= ramp[::-1]
                gain = np.ones(k, dtype=np.float32)
                for start, end in featured:
                    if e.timeline_end <= start-.15 or e.timeline_start >= end+.2:
                        continue
                    times = e.timeline_start + np.arange(k)/48000
                    amount = np.minimum(np.clip((times-start+.15)/.15, 0, 1),
                                        np.clip((end+.2-times)/.2, 0, 1))
                    gain = np.minimum(gain, 1-(1-10**(-7/20))*amount)
                mixed = x + song*(gain*music_volume)[:,None]
                # The streaming limiter runs before integer quantization, so summing
                # unusually loud sources cannot silently clip the FLAC intermediary.
                enc.stdin.write(mixed.astype('<f4').tobytes())
        finally:
            with suppress(OSError):enc.stdin.close()
            code=enc.wait()
        if code:raise UltraError(f'Ambience encode failed; see {logpath}')
        with NamedTemporaryFile(dir=output.parent, prefix=f'.{output.stem}-',
                                suffix='.partial.mp4', delete=False) as temporary:
            rendered = Path(temporary.name)
        master = subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','warning','-y',
            '-copyts','-start_at_zero','-f','mpegts','-i','pipe:0','-i',str(ambience),
            '-filter_complex',f'[1:a]{AUDIO_LIMITER},afade=t=out:st={target-.3}:d=0.3[m]',
            '-map','0:v:0','-map','[m]','-c:v','copy','-c:a','aac','-b:a','256k',
            '-t',str(target),'-movflags','+faststart',str(rendered)],stdin=subprocess.PIPE,stdout=log,stderr=log)
        try:
            for i,e in enumerate(edits):
                if shutil.disk_usage(output.parent).free < reserve_bytes:
                    raise UltraError(f'Disk reserve reached ({reserve_bytes/1e9:.1f} GB floor); render stopped, partial output kept as .incomplete')
                n=round(e.duration*fps)
                vf=f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},trim=end_frame={n},setpts=PTS-STARTPTS,format=yuv420p'
                cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-ss',str(e.source_start),'-i',e.source,
                     '-vf',vf,'-an','-t',str(n/fps),'-c:v','libx264','-preset','fast','-b:v',f'{video_kbps}k',
                     '-maxrate',f'{round(video_kbps*1.25)}k','-bufsize',f'{video_kbps*2}k',
                     '-pix_fmt','yuv420p','-bf','0','-g','60',
                     '-output_ts_offset',str(e.timeline_start),'-mpegts_flags','+initial_discontinuity',
                     '-muxdelay','0','-muxpreload','0','-f','mpegts','pipe:1']
                print(f'Stream {i+1}/{len(edits)} {e.timeline_start:.2f}s {e.label}',flush=True)
                child=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=log)
                try:
                    shutil.copyfileobj(child.stdout,master.stdin,length=256*1024)
                finally:
                    child.stdout.close()
                    if child.poll() is None and master.poll() is not None:child.terminate()
                    code=child.wait()
                if code:raise UltraError(f'Segment {i+1} failed; see {logpath}')
            master.stdin.close()
            if master.wait():raise UltraError(f'Final mux failed; see {logpath}')
        except BaseException:
            # SIGTERM alone left ffmpeg blocked on its open stdin pipe forever; EOF lets it write its trailer and exit.
            master.terminate()
            with suppress(OSError):master.stdin.close()
            try:master.wait(timeout=30)
            except subprocess.TimeoutExpired:master.kill();master.wait()
            # Only rename our unique temporary file, never an output created by another writer.
            if rendered.exists():rendered.rename(output.with_name(f'{output.stem}.incomplete-{uuid.uuid4().hex[:12]}{output.suffix}'))
            raise
      finally:
        ambience.unlink(missing_ok=True)
    try:
        info=probe(rendered)
        if not info['has_video'] or not info['has_audio'] or abs(info['duration']-target)>.15:
            raise UltraError(f'Streamed duration mismatch: {info}')
        try:
            # Atomic, no overwrite and no second copy of the video bytes.
            os.link(rendered, output)
        except FileExistsError:
            raise UltraError(f'Preserve existing output: {output}') from None
    except BaseException:
        rendered.rename(output.with_name(f'{output.stem}.incomplete-{uuid.uuid4().hex[:12]}{output.suffix}'))
        raise
    rendered.unlink()
    return dict(output=str(output),duration=info['duration'],video_kbps=video_kbps,
                estimated_upper_bytes=estimate,bytes=output.stat().st_size,temporary_video_bytes=0,
                audio_mix=dict(sample_rate=48000, featured_music_duck_db=7,
                               featured_source_max_gain=2,
                               intents={intent: sum(e.audio_intent == intent for e in edits)
                                        for intent in ('auto', 'mute', 'ambience', 'featured')}),
                finalization='atomic hardlink; temporary mux becomes final without copying')
