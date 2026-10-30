"""Bounded, sampled perceptual checks; alternate views/crops are not reliably detected."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .catalogue import save
from .media import UltraError, probe


@lru_cache(maxsize=128)
def _digest(path, size, mtime, ctime, inode):
    with Path(path).open('rb') as stream:
        value = hashlib.file_digest(stream, 'sha256').hexdigest()
    stat = Path(path).stat()
    if (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino) != (size, mtime, ctime, inode):
        raise UltraError('Source changed while hashing: ' + path)
    return value


def sample_hashes(path, cache_dir, *, sample_fps=2):
    """Decode at most 115,200 32x32 samples, streaming frames instead of capturing a video."""
    path = Path(path).resolve()
    if not math.isfinite(sample_fps) or not 0 < sample_fps <= 4:
        raise UltraError('Duplicate sample FPS must be in (0, 4]')
    info = probe(path)
    if not info['has_video'] or not 0 < info['duration'] * sample_fps <= 115200:
        raise UltraError('Duplicate scan requires video within the 115200-sample limit')
    stat = path.stat()
    digest = _digest(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
    key = hashlib.sha256(f'{digest}:{sample_fps}:phash32-v2'.encode()).hexdigest()
    cache = Path(cache_dir) / (key + '.json')
    if cache.exists():
        try:
            data = json.loads(cache.read_text())
            hashes = data['hashes']
            if (data['sha256'] != digest or data['sample_fps'] != sample_fps or not isinstance(hashes, list)
                    or not hashes or len(hashes) > 115200
                    or abs(len(hashes) - info['duration'] * sample_fps) > 1.5
                    or data.get('hashes_sha256') != hashlib.sha256(json.dumps(hashes).encode()).hexdigest()
                    or any(type(h) is not int or not 0 <= h < 2**63 for h in hashes)):
                raise ValueError('invalid sample metadata')
            return dict(data, source=str(path))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise UltraError(f'Invalid duplicate cache {cache}: {exc}') from exc
    hashes = []
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
            '-vf', f'fps={sample_fps},scale=32:32,format=gray', '-an', '-f', 'rawvideo',
            '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE, stderr=errors)
        try:
            while raw := proc.stdout.read(1024):
                if len(raw) != 1024 or len(hashes) >= 115200:
                    raise UltraError('Incomplete or over-limit perceptual sample stream')
                frame = np.frombuffer(raw, np.uint8).reshape(32, 32)
                dct = cv2.dct(frame.astype(np.float32))[:8, :8].ravel()[1:]
                hashes.append(sum(int(bit) << k for k, bit in enumerate(dct > np.median(dct))))
            code = proc.wait(); errors.seek(0)
            if code:
                raise UltraError('Duplicate decode failed: ' + errors.read().decode(errors='replace')[-1000:])
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
    if not hashes:
        raise UltraError('No perceptual samples decoded')
    data = dict(source=str(path), sha256=digest, sample_fps=sample_fps, hashes=hashes,
                hashes_sha256=hashlib.sha256(json.dumps(hashes).encode()).hexdigest(),
                sample_center_seconds=.5/sample_fps, duration=info['duration'])
    save(cache, data)
    return data


def _bands(value):
    return [(i, (value >> (21*i)) & ((1 << 21)-1)) for i in range(3)]


def _get(edit, name):
    return edit[name] if isinstance(edit, dict) else getattr(edit, name)


def _scope(sample_fps, threshold):
    if type(threshold) is not int or not 0 <= threshold <= 2:
        raise UltraError('Hash threshold must be 0, 1 or 2 for the bounded three-band search')
    return dict(sample_fps=sample_fps, hamming_threshold=threshold,
                method='63-bit DCT pHash on 32x32 grayscale samples; three-band candidate index',
                semantic_duplicates_verified=False,
                scope='Sampled near-identical image runs only; no guarantee for alternate angles, crops, mirrors or events between samples')


def check_video_duplicates(video, edits, cache_dir, *, sample_fps=2, threshold=2,
                           max_comparisons=250000):
    report = _scope(sample_fps, threshold)
    sampled = sample_hashes(video, cache_dir, sample_fps=sample_fps)
    hashes = sampled['hashes']; ends = np.array([_get(e, 'timeline_end') for e in edits])
    if not len(ends) or np.any(np.diff(ends) <= 0):
        raise UltraError('Duplicate check requires ordered edit boundaries')
    owners = np.searchsorted(ends, (np.arange(len(hashes)) + .5) / sample_fps)
    buckets, pairs, flags = defaultdict(list), set(), []
    count, truncated = 0, max_comparisons <= 0
    for i in range(len(hashes)-2):
        if truncated:
            break
        if owners[i] >= len(edits) or owners[i] != owners[i+2] or (hashes[i] ^ hashes[i+2]).bit_count() <= 2:
            continue
        previous = set(j for band in _bands(hashes[i]) for j in buckets[band])
        for j in sorted(previous):
            pair = (int(owners[j]), int(owners[i]))
            if pair in pairs or pair[0] == pair[1] or i-j < 3*sample_fps:
                continue
            same = True
            for k in range(3):
                if count >= max_comparisons:
                    truncated = True; same = False; break
                count += 1
                if (hashes[i+k] ^ hashes[j+k]).bit_count() > threshold:
                    same = False; break
            if truncated:
                break
            if same:
                flags.append(dict(time_a=(j+.5)/sample_fps, time_b=(i+.5)/sample_fps,
                                  clip_a=pair[0], clip_b=pair[1], sampled_run_seconds=3/sample_fps))
                pairs.add(pair)
                if len(flags) >= 1000:
                    truncated = True; break
        for band in _bands(hashes[i]):
            buckets[band].append(i)
    report.update(source_evidence={sampled['source']: sampled['sha256']}, frames=len(hashes),
                  comparisons=count, candidates=flags, complete=not truncated, truncated=truncated)
    return report


def deduplicate_shots(shots, cache_dir, *, sample_fps=2, threshold=2,
                      max_comparisons=250000):
    """Prefer longer cores; reject >=80% moving repeats only with matching sampled edges."""
    report = _scope(sample_fps, threshold)
    sources, retained, rejected, signatures = {}, [], [], {}
    buckets = defaultdict(list)
    count, truncated, too_short = 0, max_comparisons <= 0, []
    # Process longest first, then restore caller order. A short reused prefix must
    # never discard the complete combination and its unique ending in a later file.
    order = sorted(range(len(shots)), key=lambda i: -(shots[i]['core_end']-shots[i]['core_start']))
    for index in order:
        shot = shots[index]
        source = str(Path(shot['source']).resolve())
        if source not in sources:
            sources[source] = sample_hashes(source, cache_dir, sample_fps=sample_fps)
        sample = sources[source]
        a, b = shot['core_start'], shot['core_end']
        if not 0 <= a < b <= sample['duration'] + .001:
            raise UltraError('Protected core outside duplicate scan source')
        first = max(0, math.ceil(a*sample_fps-.5))
        stop = min(len(sample['hashes']), math.ceil(b*sample_fps-.5))
        signature = sample['hashes'][first:stop]
        signatures[index] = signature
        anchors = [i for i in range(max(0, len(signature)-2))
                   if (signature[i] ^ signature[i+2]).bit_count() > 2]
        if len(signature) < 3:
            too_short.append(index)
        duplicate = None
        compared = set()
        for at in anchors[:4]:
            if truncated or duplicate is not None:
                break
            matches = set(item for band in _bands(signature[at]) for item in buckets[band])
            for prior, offset in sorted(matches):
                if str(Path(shots[prior]['source']).resolve()) == source:
                    continue
                shift = offset-at
                if (prior, shift) in compared:
                    continue
                compared.add((prior, shift))
                other = signatures[prior]
                start, end = max(0, -shift), min(len(signature), len(other)-shift)
                needed = max(3, math.ceil(.8*len(signature)))
                run, longest = 0, 0
                edges_match = start == 0 and end == len(signature)
                for k in range(start, end):
                    if count >= max_comparisons:
                        truncated = True; break
                    count += 1
                    same = (signature[k] ^ other[k+shift]).bit_count() <= threshold
                    if (k < 3 or k >= len(signature)-3) and not same:
                        edges_match = False
                    run = run+1 if same else 0
                    longest = max(longest, run)
                if truncated:
                    break
                if longest >= needed and edges_match:
                    duplicate = dict(index=index, duplicate_of=prior,
                        evidence=dict(source=source, compared_source=str(Path(shots[prior]['source']).resolve()),
                                      sampled_run_seconds=longest/sample_fps,
                                      minimum_coverage_fraction=.8, sampled_edges_match=True))
                    break
        if duplicate is not None:
            rejected.append(duplicate)
        else:
            retained.append(index)
            for at in anchors:
                for band in _bands(signature[at]):
                    buckets[band].append((index, at))
    retained.sort()
    rejected.sort(key=lambda row: row['index'])
    report.update(retained=retained, rejected=rejected, comparisons=count,
                  source_evidence={p: s['sha256'] for p, s in sources.items()},
                  too_short_for_run_check=too_short, complete=not truncated, truncated=truncated)
    return [shots[i] for i in retained], report
