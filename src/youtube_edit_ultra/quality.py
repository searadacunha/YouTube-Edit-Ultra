"""Measured export QC and bounded audio-only recovery; never certify sporting semantics."""
from __future__ import annotations

import json
import math
import re
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path

from .catalogue import save, sha256
from .media import UltraError, require_space, run
from .storage import guarded_command


class VerificationError(UltraError):
    """A failed measurement, with a persisted report and a machine-readable cause."""

    def __init__(self, code: str, message: str, report: dict):
        super().__init__(message)
        self.code = code
        self.report = report


def _fail(report_path, report, code, message):
    report.update(status="FAILED", error_code=code, error=message)
    save(report_path, report)
    raise VerificationError(code, message, report)


def verify_output(path, target, *, width=None, height=None, fps=None,
                  true_peak_limit=0.0, report_path=None):
    """Fully decode an export; flags remain inspectable for the legacy produce API.

    Final delivery must use finalize_output, which also rejects all quality flags.
    Container duration tolerance is 150 ms (AAC priming included); when fps is given,
    the decoded frame count must be within one frame of the requested duration.
    """
    path = Path(path)
    report_path = Path(report_path) if report_path else path.with_suffix(".verification.json")
    if (not math.isfinite(target) or target <= 0 or not math.isfinite(true_peak_limit)
            or true_peak_limit > 0):
        raise ValueError("Positive finite duration and nonpositive finite peak limit required")
    for key, value in (("width", width), ("height", height), ("fps", fps)):
        if value is not None and (type(value) is not int or value <= 0):
            raise ValueError(f"Positive integer {key} required")
    report = dict(status="CHECKING", output=str(path), target_seconds=target,
                  duration_tolerance_seconds=.15, true_peak_limit_dbfs=true_peak_limit,
                  full_decode=False, quality_flags=[], semantic_actions_verified=False,
                  continuous_human_viewing=False, continuous_listening=False,
                  thresholds=dict(black_seconds=.5, black_pixel=.10, freeze_seconds=2,
                                  freeze_noise_db=-50, silence_seconds=1, silence_db=-50),
                  sync_scope="stream timestamps only; musical/action sync requires review")
    try:
        info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                               "-of", "json", str(path)]))
        report["probe"] = info
        v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        if not v or not a:
            _fail(report_path, report, "streams", "Export sans flux vidéo/audio")
        duration = float(info["format"]["duration"])
        rate = float(Fraction(v["avg_frame_rate"]))
        start_delta = abs(float(v.get("start_time", 0)) - float(a.get("start_time", 0)))
        end_delta = abs(float(v.get("duration", duration)) - float(a.get("duration", duration)))
        if not all(math.isfinite(x) for x in (duration, rate, start_delta, end_delta)) or rate <= 0:
            raise ValueError("Nonfinite or invalid stream timing")
        report.update(duration=duration, start_offset_seconds=start_delta,
                      end_duration_delta_seconds=end_delta, fps=rate)
    except VerificationError:
        raise
    except (UltraError, OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        _fail(report_path, report, "probe", f"Lecture du média impossible : {exc}")
    if abs(duration - target) > .15:
        _fail(report_path, report, "duration", f"Durée finale {duration}, cible {target} (tolérance 0,15 s)")
    if (path.suffix.lower() != ".mp4" or "mp4" not in info["format"].get("format_name", "")
            or v["codec_name"] != "h264" or v.get("pix_fmt") not in {"yuv420p", "yuvj420p"}
            or a.get("codec_name") != "aac"):
        _fail(report_path, report, "format", "Export MP4 H.264 8-bit 4:2:0 et AAC requis")
    if v.get("sample_aspect_ratio") not in (None, "N/A", "1:1"):
        _fail(report_path, report, "aspect_ratio", "Pixels carrés requis pour le ratio de livraison")
    if ((width is not None and v.get("width") != width)
            or (height is not None and v.get("height") != height)):
        _fail(report_path, report, "resolution", "Résolution finale différente de la demande")
    if fps is not None and abs(rate - fps) > .001:
        _fail(report_path, report, "fps", f"FPS final {rate}, cible {fps}")
    sync_tolerance = max(.05, 2 / rate)
    if start_delta > sync_tolerance or end_delta > .15:
        _fail(report_path, report, "sync", "Désalignement temporel des flux audio/vidéo")
    logpath = report_path.with_suffix(".decode_quality.log")
    try:
        cp = subprocess.run([
            "ffmpeg", "-nostdin", "-hide_banner", "-v", "info", "-nostats", "-xerror",
            "-i", str(path), "-map", "0:v:0", "-map", "0:a:0",
            "-vf", "blackdetect=d=0.5:pix_th=0.10,freezedetect=n=-50dB:d=2",
            "-af", "silencedetect=n=-50dB:d=1,ebur128=peak=true:framelog=verbose",
            "-progress", "pipe:1", "-f", "null", "-"], capture_output=True, text=True)
    except OSError as exc:
        _fail(report_path, report, "decode", f"Décodage complet impossible : {exc}")
    logpath.write_text(cp.stderr)
    report["decode_log"] = str(logpath)
    if cp.returncode:
        _fail(report_path, report, "decode", f"Décodage complet en échec ; voir {logpath}")
    report["full_decode"] = True
    report["quality_flags"] = [line for line in cp.stderr.splitlines() if any(
        k in line for k in ("black_start:", "freeze_start:", "silence_start:"))]
    frames = re.findall(r"^frame=(\d+)$", cp.stdout, re.MULTILINE)
    report["decoded_video_frames"] = int(frames[-1]) if frames else None
    if fps is not None and (not frames or abs(int(frames[-1]) - round(target * fps)) > 1):
        _fail(report_path, report, "frames", "Nombre d'images décodées différent de la durée demandée")
    peaks = [float(x) for x in re.findall(r"Peak:\s*(-?[0-9.]+) dBFS", cp.stderr)]
    if not peaks:
        _fail(report_path, report, "peak_measurement", "Mesure de crête audio finie absente")
    peak = max(peaks)
    report.update(true_peak_dbfs=peak, sha256=sha256(path))
    if peak >= 0 or peak > true_peak_limit:
        _fail(report_path, report, "true_peak",
              f"Crête audio {peak:g} dBFS ; limite {true_peak_limit:g} dBFS, corriger le mix")
    report["status"] = ("QUALITY_REVIEW_REQUIRED" if report["quality_flags"]
                        else "TECHNICAL_PASS_REVIEW_REQUIRED")
    save(report_path, report)
    return report


def video_packet_hash(path):
    """Hash encoded packets, so audio repair cannot silently re-encode the pictures."""
    value = run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0",
                 "-c", "copy", "-f", "hash", "-hash", "sha256", "-"]).strip()
    if not re.fullmatch(r"SHA256=[0-9a-f]{64}", value):
        raise UltraError("Empreinte du flux vidéo absente ou invalide")
    return value.removeprefix("SHA256=")


def finalize_output(path, target, *, job_dir, max_attempts=2, true_peak_limit=-1.0,
                    width=None, height=None, fps=None):
    """Verify, repair only true-peak failures, reverify; preserve every input artifact.

    The caller owns the job directory and reserves disk for this stage. This helper
    additionally checks actual free space before every replacement-sized write.
    """
    if type(max_attempts) is not int or not 0 <= max_attempts <= 3:
        raise ValueError("Audio recovery attempts must be between 0 and 3")
    original = Path(path).absolute()
    job_dir = Path(job_dir).resolve()
    if original.is_symlink() or not original.resolve().is_relative_to(job_dir):
        raise UltraError("Audio recovery requires a file owned by this job directory")
    current, corrections = original, []
    options = dict(width=width, height=height, fps=fps, true_peak_limit=true_peak_limit)
    recipe = dict(quality_revision=1, target=target, **options)
    source_hash = sha256(original) if original.is_file() else None
    completion = original.with_suffix(".finalization.json")
    try:
        cached = json.loads(completion.read_text())
        artifact = Path(cached["output"])
        if (source_hash is not None and cached.get("recipe") == recipe
                and cached.get("input_sha256") == source_hash
                and cached.get("status") == "TECHNICAL_PASS_REVIEW_REQUIRED"
                and cached.get("full_decode") and not cached.get("quality_flags")
                and not artifact.is_symlink() and artifact.resolve().is_relative_to(job_dir)
                and sha256(artifact) == cached["sha256"]):
            return cached
    except (OSError, ValueError, TypeError, KeyError):
        pass  # Invalid or interrupted cache is re-measured, never considered a successful export.
    for attempt in range(max_attempts + 1):
        try:
            report = verify_output(current, target, **options)
            if report["quality_flags"]:
                _fail(current.with_suffix(".verification.json"), report, "quality_flags",
                      "Noir, gel ou silence détecté : livraison refusée")
        except VerificationError as exc:
            if exc.report["quality_flags"] or exc.code != "true_peak" or attempt >= max_attempts:
                raise
            report = exc.report
        else:
            report.update(output=str(current), corrections=corrections,
                          input_sha256=source_hash, recipe=recipe)
            save(current.with_suffix(".verification.json"), report)
            save(completion, report)
            return report
        # AAC reconstruction can overshoot the applied gain; leave another 1 dB and measure again.
        gain = min(-1.0, true_peak_limit - report["true_peak_dbfs"] - 1.0)
        candidate = original.with_name(f"{original.stem}.audio-fixed-{uuid.uuid4().hex[:12]}.mp4")
        # Video bytes remain intact; budget a complete new audio track and muxing margin.
        estimate = int(current.stat().st_size + target * 40_000 + 1_000_000)
        require_space(job_dir, estimate, "audio repair")
        before = video_packet_hash(current)
        run(guarded_command(
            ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-n", "-i", str(current),
             "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-af", f"volume={gain:.6f}dB",
             "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(candidate)],
            need=estimate, path=job_dir, label="audio repair"))
        after = video_packet_hash(candidate)
        correction = dict(input=str(current), output=str(candidate), gain_db=gain,
                          measured_input_peak_dbfs=report["true_peak_dbfs"],
                          video_packet_hash_before=before, video_packet_hash_after=after,
                          video_packets_identical=before == after)
        corrections.append(correction)
        save(original.with_suffix(".audio_corrections.json"), corrections)
        if before != after:
            raise UltraError("Audio repair changed the video packets; delivery refused")
        current = candidate
    raise AssertionError("Unreachable audio recovery state")
