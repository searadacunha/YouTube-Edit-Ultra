"""Narrated fight documentaries: evidence-bound script, synthetic voice, burnt subtitles,
tactical annotations, slow motion, freezes and split screens, rendered as one streamed MP4.

Reuses the job checkpoints, disk floor and finalize_output of the music pipeline. Detectors
and contact sheets only propose candidates; a visual is admitted only with an explicit
provenance, an action description and a confidence written in the spec.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
import uuid
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

from .catalogue import save, sha256
from .media import UltraError, probe, require_space

FONTS = Path('/System/Library/Fonts')
CATEGORIES = {'verified_fact', 'technical_interpretation', 'prediction', 'rhetorical_hook'}
# An agent never self-assigns these: they mean a person watched the footage.
FORBIDDEN_PROVENANCE = {'visual_review', 'human_review'}
VISUALS = {'clip', 'freeze', 'card', 'split'}
YELLOW, RED, WHITE = (255, 210, 40), (235, 60, 50), (255, 255, 255)


def font(size, heavy=False, condensed=False):
    name = 'Avenir Next Condensed.ttc' if condensed else 'Avenir Next.ttc'
    try:
        return ImageFont.truetype(str(FONTS / name), size, index=8 if heavy else 2)
    except OSError:  # non-macOS fixtures
        return ImageFont.load_default(size)


# ---------------------------------------------------------------- review helpers

def source_fps(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=avg_frame_rate', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True).stdout.strip()
    num, _, den = out.partition('/')
    return float(num) / float(den or 1) if num and float(den or 1) else 30.0


def frames_at(source, start, end, step, width=256):
    """(time, RGB array) at exact decoded timestamps, read from showinfo, not inferred."""
    k = max(1, round(step * source_fps(source)))
    height = round(width * 9 / 16 / 2) * 2
    cmd = ['ffmpeg', '-nostdin', '-hide_banner', '-v', 'info', '-ss', f'{start:.3f}', '-i', str(source),
           '-t', f'{end - start:.3f}', '-an', '-vf',
           f"select='not(mod(n\\,{k}))',showinfo,scale={width}:{height},format=rgb24",
           '-vsync', 'vfr', '-f', 'rawvideo', '-']
    cp = subprocess.run(cmd, capture_output=True)
    if cp.returncode:
        raise UltraError(f'Frame extraction failed: {source}')
    times = [start + float(t) for t in re.findall(rb'pts_time:([0-9.]+)', cp.stderr)]
    data = np.frombuffer(cp.stdout, np.uint8).reshape(-1, height, width, 3)
    return list(zip(times, data))


def contact_sheet(source, out, start, end, step, cols=6, width=256):
    shots = frames_at(source, start, end, step, width)
    if not shots:
        raise UltraError('No frame in requested window')
    h = shots[0][1].shape[0]
    rows = math.ceil(len(shots) / cols)
    sheet = Image.new('RGB', (cols * width, rows * h), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    f = font(15, heavy=True)
    for i, (t, a) in enumerate(shots):
        x, y = i % cols * width, i // cols * h
        sheet.paste(Image.fromarray(a), (x, y))
        d.rectangle((x, y, x + 62, y + 18), fill=(0, 0, 0))
        d.text((x + 3, y + 1), f'{t:7.2f}', fill=YELLOW, font=f)
    sheet.save(out, quality=88)
    return dict(sheet=str(out), source=str(source), start=start, end=end, step=step,
                frames=[round(t, 3) for t, _ in shots])


# ---------------------------------------------------------------- spec and evidence

def load_spec(path):
    path = Path(path).expanduser().resolve()
    spec = yaml.safe_load(path.read_text())
    spec['_path'] = str(path)
    spec['_out'] = str((path.parent / spec['output']).resolve())
    if spec.get('sources_file') and out_path(spec, spec['sources_file']).exists():
        spec['sources'] = json.loads(out_path(spec, spec['sources_file']).read_text())
    spec.setdefault('sources', {})
    return spec


def out_path(spec, rel):
    return Path(spec['_out']) / rel


def src_path(spec, rel):
    """Footage folder; a revision points here at the previous job's verified proxies and HD windows."""
    return Path(spec['_out']) / spec.get('sources_dir', 'sources') / rel


def iter_blocks(spec):
    for chapter in spec['chapters']:
        for block in chapter['blocks']:
            yield chapter, block


def load_facts(spec):
    facts = {}
    for rel in spec.get('facts', []):
        for row in json.loads(out_path(spec, rel).read_text()):
            facts[row['id']] = row
    return facts


def validate(spec):
    """Every narrated claim is categorised; every visual names its source, action and provenance."""
    errors, seen = [], set()
    facts = load_facts(spec)
    for chapter, block in iter_blocks(spec):
        bid = block.get('id')
        if not bid or bid in seen:
            errors.append(f'duplicate or missing block id {bid}')
        seen.add(bid)
        if not block.get('text', '').strip():
            errors.append(f'{bid}: empty narration')
        for claim in block.get('claims', []):
            if claim.get('cat') not in CATEGORIES:
                errors.append(f"{bid}: category {claim.get('cat')} not narratable")
            for fid in claim.get('facts', []):
                if facts.get(fid, {}).get('status') != 'verified':
                    errors.append(f'{bid}: fact {fid} missing or not verified')
            if claim.get('cat') == 'verified_fact' and not claim.get('facts'):
                errors.append(f'{bid}: verified_fact without fact reference')
        if not block.get('visuals'):
            errors.append(f'{bid}: no visual')
        for v in block.get('visuals', []):
            kind = v.get('type')
            if kind not in VISUALS:
                errors.append(f'{bid}: unknown visual {kind}')
                continue
            for part in ([v['left'], v['right']] if kind == 'split' else [v] if kind != 'card' else []):
                if part.get('src') not in spec['sources']:
                    errors.append(f"{bid}: unknown source {part.get('src')}")
                if part.get('provenance') in FORBIDDEN_PROVENANCE or not part.get('provenance'):
                    errors.append(f'{bid}: provenance must be explicit and agent-honest')
                if not part.get('action') or not 0 <= float(part.get('confidence', -1)) <= 1:
                    errors.append(f'{bid}: action description and confidence required')
                if spec.get('require_boxer'):
                    subject = block.get('subject') or []
                    if not part.get('boxer'):
                        errors.append(f'{bid}: footage without the identity of its main boxer')
                    elif not set(part['boxer'].split('+')) & set(subject):
                        errors.append(f"{bid}: shows {part['boxer']} while the narration is about {subject}")
                t = part.get('t') or [part.get('at'), part.get('at')]
                if t[0] is None or t[1] < t[0]:
                    errors.append(f'{bid}: invalid source window {t}')
    for sid, src in spec['sources'].items():
        if not src.get('rights') or not src.get('url'):
            errors.append(f'source {sid}: rights status and url required')
    return errors


# ---------------------------------------------------------------- narration

def _key(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]


def voice_jobs(spec):
    v = spec['voice']
    items = []
    for _, block in iter_blocks(spec):
        text = ' '.join(block.get('say', block['text']).split())  # say: spelled for the voice
        name = f"{block['id']}-{_key(text, v['model'], v.get('ref_text'), v.get('ref_audio'), v.get('seed'), v.get('temperature'))}.wav"
        items.append(dict(id=block['id'], text=text, out=str(out_path(spec, f'audio/vo/{name}'))))
    return dict(lang=v.get('lang', 'french'), ref_audio=str(out_path(spec, v['ref_audio'])),
                ref_text=v.get('ref_text'), seed=v.get('seed', 7), temperature=v.get('temperature', .7),
                asr_lang=v.get('asr_lang', 'fr'), generator=2, items=items)  # 2: runaway generations are retried


def tempo_files(spec, files):
    """Faster delivery without chipmunk pitch: cut long internal pauses, then atempo towards target_wpm.

    Natural generation stays untouched; the processed copy is what is aligned, mixed and heard.
    """
    v = spec['voice']
    target, trim = v.get('target_wpm'), v.get('trim_pauses')
    fixed, cap = float(v.get('tempo', 1.0)), float(v.get('max_tempo', 1.45))
    if not target and not trim and fixed == 1.0:
        return files
    words = {i['id']: len(i['text'].split()) for i in voice_jobs(spec)['items']}
    out, report = {}, {}
    for bid, f in files.items():
        fast = Path(f).with_name(f'{Path(f).stem}-{_key(target, trim, fixed, cap)}.wav')
        if not fast.exists():
            src = Path(f)
            if trim:
                src = fast.with_name(f'.{fast.stem}.trim.wav')
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', f, '-af',
                                f'silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:'
                                f'stop_duration={trim}:stop_threshold=-45dB:stop_silence={trim * .7:.3f}', str(src)], check=True)
            dur = probe(src)['duration']
            factor = fixed if not target else min(cap, max(1.0, target / (words[bid] / dur * 60)))
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(src), '-af', f'atempo={factor:.4f}',
                            str(fast)], check=True)
            if src != Path(f):
                src.unlink()
        out[bid] = str(fast)
        d = probe(Path(out[bid]))['duration']
        report[bid] = dict(seconds=round(d, 2), wpm=round(words[bid] / d * 60, 1),
                           natural_seconds=round(probe(Path(f))['duration'], 2))
    save(out_path(spec, 'audio/tempo_report.json'), report)
    return out


def run_voice(spec, command, files=None):
    v = spec['voice']
    base = Path(spec['_path']).parent
    jobs = voice_jobs(spec)
    if files:  # align what will actually be heard
        for item in jobs['items']:
            item['out'] = files[item['id']]
    jobs_file = out_path(spec, f'audio/voice_jobs{"_align" if files else ""}.json')
    jobs_file.parent.mkdir(parents=True, exist_ok=True)
    jobs_file.write_text(json.dumps(jobs, ensure_ascii=False, indent=1))
    # normpath, not resolve: the venv interpreter is a symlink that must stay inside its venv
    cmd = [os.path.normpath(base / v['python']), '-I', str((base / v['script']).resolve()), command,
           '--jobs', str(jobs_file)]
    if command == 'tts':
        cmd += ['--model', v['model']]
    else:
        cmd += ['--model', v.get('align_model', 'base'), '--output', str(out_path(spec, 'audio/align.json'))]
    subprocess.run(cmd, check=True)
    return jobs


def pcm(path, start=0.0, duration=None, rate=48000, channels=2):
    cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-ss', f'{start:.4f}', '-i', str(path)]
    if duration is not None:
        cmd += ['-t', f'{duration:.4f}']
    cmd += ['-vn', '-ac', str(channels), '-ar', str(rate), '-f', 'f32le', '-']
    cp = subprocess.run(cmd, capture_output=True)
    if cp.returncode:
        raise UltraError(f'Audio decode failed: {path}')
    return np.frombuffer(cp.stdout, np.float32).reshape(-1, channels).copy()


# ---------------------------------------------------------------- subtitles

def norm(word):
    word = unicodedata.normalize('NFD', word.lower())
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in word if unicodedata.category(c) != 'Mn'))


def timed_tokens(text, asr, duration):
    """Script words carry Whisper times; display text is always the script, never the ASR."""
    toks = text.split()
    a = [norm(w['w']) for w in asr]
    b = [norm(t) for t in toks]
    times = [None] * len(toks)
    for blk in difflib.SequenceMatcher(None, b, a, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            w = asr[blk.b + k]
            times[blk.a + k] = (w['start'], w['end'])
    known = [i for i, t in enumerate(times) if t]
    if not known:
        step = duration / max(1, len(toks))
        return [(t, i * step, (i + 1) * step) for i, t in enumerate(toks)]
    for i in range(len(toks)):
        if times[i] is None:  # interpolate between matched neighbours
            lo = max([k for k in known if k < i], default=None)
            hi = min([k for k in known if k > i], default=None)
            t0 = times[lo][1] if lo is not None else 0.0
            t1 = times[hi][0] if hi is not None else duration
            n = (hi if hi is not None else len(toks)) - (lo if lo is not None else -1)
            j = i - (lo if lo is not None else -1)
            times[i] = (t0 + (t1 - t0) * (j - 1) / n, t0 + (t1 - t0) * j / n)
    return [(t, *times[i]) for i, t in enumerate(toks)]


def make_cues(tokens, offset, max_chars=40, max_dur=6.5):
    cues, cur = [], []

    def flush():
        if cur:
            lines, line = [], []
            for tok in cur:
                if line and len(' '.join(line + [tok[0]])) > max_chars:
                    lines.append(line)
                    line = []
                line.append(tok[0])
            lines.append(line)
            cues.append(dict(start=offset + cur[0][1], end=offset + cur[-1][2], lines=lines))
            cur.clear()

    def n_lines(words):
        lines, length = 1, -1
        for w in words:
            if length >= 0 and length + 1 + len(w) > max_chars:
                lines, length = lines + 1, len(w)
            else:
                length += 1 + len(w)
        return lines

    for tok in tokens:
        if cur and (n_lines([t[0] for t in cur + [tok]]) > 2 or tok[2] - cur[0][1] > max_dur):
            flush()
        cur.append(tok)
        if tok[0][-1] in '.!?…' or (tok[0][-1] in ',:;' and len(' '.join(t[0] for t in cur)) > max_chars):
            flush()
    flush()
    for a, b in zip(cues, cues[1:]):  # hold briefly, never overlap the next cue
        a['end'] = min(max(a['end'] + .25, a['start'] + .9), b['start'] - .02)
    if cues:
        cues[-1]['end'] = max(cues[-1]['end'] + .25, cues[-1]['start'] + .9)
    return cues


def word_color(word, spec):
    hl = spec.get('subtitles', {})
    n = norm(word)
    if any(norm(w) == n for w in hl.get('red', [])):
        return RED
    if any(norm(w) == n for w in hl.get('yellow', [])) or re.search(r'\d', word):
        return YELLOW
    return WHITE


def write_subtitles(spec, cues, ass_path, srt_path):
    import pysubs2
    subs = pysubs2.SSAFile()
    subs.info.update(PlayResX=str(spec['video']['width']), PlayResY=str(spec['video']['height']))
    st = subs.styles['Default']
    st.fontname, st.fontsize, st.bold = 'Avenir Next Demi Bold', 46, True
    st.outline, st.shadow, st.marginv = 3, 1, 60
    for c in cues:
        def tag(w):
            col = word_color(w, spec)
            return w if col == WHITE else '{\\c&H%02X%02X%02X&}%s{\\c&HFFFFFF&}' % (col[2], col[1], col[0], w)
        text = '\\N'.join(' '.join(tag(w) for w in line) for line in c['lines'])
        subs.append(pysubs2.SSAEvent(start=round(c['start'] * 1000), end=round(c['end'] * 1000), text=text))
    subs.save(str(ass_path))
    plain = pysubs2.SSAFile()
    for c in cues:
        plain.append(pysubs2.SSAEvent(start=round(c['start'] * 1000), end=round(c['end'] * 1000),
                                      text='\\N'.join(' '.join(line) for line in c['lines'])))
    plain.save(str(srt_path))


# ---------------------------------------------------------------- HD windows

def _parts(v):
    return [v['left'], v['right']] if v['type'] == 'split' else [] if v['type'] == 'card' else [v]


def needed_windows(spec, margin=1.0, gap=4.0):
    need = {}
    for _, block in iter_blocks(spec):
        for v in block['visuals']:
            for p in _parts(v):
                a, b = p['t'] if 't' in p else (p['at'], p['at'])
                need.setdefault(p['src'], []).append([max(0, a - margin), b + margin])
    merged = {}
    for sid, wins in need.items():
        out = []
        for a, b in sorted(wins):
            if out and a - out[-1][1] < gap:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b])
        merged[sid] = out
    return merged


def motion_signature(path, start, duration, rate=10):
    cp = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', f'{start:.3f}', '-i', str(path),
                         '-t', f'{duration:.3f}', '-an', '-vf', f'fps={rate},scale=32:18,format=gray',
                         '-f', 'rawvideo', '-'], capture_output=True)
    a = np.frombuffer(cp.stdout, np.uint8).reshape(-1, 18, 32).astype(np.float32)
    return np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))


def measure_offset(proxy, a, b, hd, rate=10, search=15):
    """Source time t is HD local time t - offset; correlation proves the window shows the reviewed shots."""
    p, h = motion_signature(proxy, a, b - a, rate), motion_signature(hd, 0, b - a, rate)
    best = (-2.0, 0)
    for lag in range(-search, search + 1):
        x = p[max(0, lag):][:len(h) - max(0, -lag)]
        y = h[max(0, -lag):][:len(x)]
        if len(x) > 20 and x.std() > 0 and y.std() > 0:
            best = max(best, (float(np.corrcoef(x, y)[0, 1]), lag))
    return a + best[1] / rate, best[0]


def fetch_hd(spec, downloader):
    index_path = src_path(spec, 'hd_index.json')
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    hd_dir = src_path(spec, 'hd')
    hd_dir.mkdir(parents=True, exist_ok=True)
    for sid, windows in needed_windows(spec).items():
        src = spec['sources'][sid]
        for a, b in windows:
            if any(e['a'] <= a and b <= e['b'] for e in index.get(sid, [])):
                continue
            target = hd_dir / f'{sid}_{a:07.2f}-{b:07.2f}.mp4'
            require_space(hd_dir, int((b - a) * 1.2e6), f'HD window {sid}')
            if not target.exists():
                subprocess.run([*downloader, '--no-progress', '-f',
                                'bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]',
                                '--download-sections', f'*{a:.2f}-{b:.2f}', '--force-keyframes-at-cuts',
                                '--merge-output-format', 'mp4', '-o', str(target), src['url']], check=True)
            offset, corr = measure_offset(src_path(spec, f'proxies/{sid}.mp4'), a, b, target)
            if corr < .5:
                raise UltraError(f'{target.name}: window does not match reviewed proxy (r={corr:.2f})')
            info = probe(target)
            index.setdefault(sid, []).append(dict(a=a, b=b, path=str(target), offset=offset, match_r=corr,
                                                  height=info['height'], sha256=sha256(target)))
            save(index_path, index)
            print(f'{sid} {a:.1f}-{b:.1f}s {info["height"]}p offset={offset - a:+.2f}s r={corr:.2f}', flush=True)
    return index


def resolve(spec, sid, t0, t1, proxy=False):
    if proxy:
        return src_path(spec, f'proxies/{sid}.mp4'), t0
    index = json.loads(src_path(spec, 'hd_index.json').read_text())
    for e in index.get(sid, []):
        if e['a'] <= t0 and t1 <= e['b']:
            return Path(e['path']), t0 - e['offset']
    raise UltraError(f'No verified HD window covers {sid} {t0}-{t1}')


# ---------------------------------------------------------------- plan

def visual_duration(v):
    if v['type'] == 'clip':
        return (v['t'][1] - v['t'][0]) / v.get('speed', 1)
    if v['type'] == 'split' and not v.get('duration'):
        return max((p['t'][1] - p['t'][0]) / p.get('speed', 1) for p in (v['left'], v['right']))
    return v.get('duration')


def build_plan(spec, vo_durations):
    fps = spec['video']['fps']
    frame, segments, blocks = 0, [], []
    for chapter, block in iter_blocks(spec):
        pace = spec.get('pacing', {})
        lead = block.get('lead', pace.get('lead', .45))
        breathe = block.get('breathe', pace.get('breathe', .8))
        need = lead + vo_durations[block['id']] + breathe
        durs = [None if v.get('flex') else visual_duration(v) for v in block['visuals']]
        fixed = sum(d for d in durs if d)
        flex = [i for i, d in enumerate(durs) if not d]
        if flex:
            # a flexible clip only ends earlier inside its reviewed window; it never starts later or speeds up.
            # Shortest windows are served first so whatever they cannot hold goes to the others.
            cap = lambda i: visual_duration(block['visuals'][i]) if block['visuals'][i]['type'] == 'clip' else 1e9
            left = need - fixed
            for k, i in enumerate(sorted(flex, key=cap)):
                durs[i] = min(cap(i), max(1.0, left / (len(flex) - k)))
                left -= durs[i]
            if sum(durs) < need - (breathe - .1):
                raise UltraError(f"{block['id']}: flexible windows too short for narration {need:.2f}s")
        elif fixed < need - 1e-6 and fixed < need - (breathe - .2):  # the pause after the voice may shrink, not vanish
            raise UltraError(f"{block['id']}: visuals {fixed:.2f}s shorter than narration {need:.2f}s; add a flex visual")
        start = frame
        for v, d in zip(block['visuals'], durs):
            n = max(1, round(d * fps))
            seg = dict(v, block=block['id'], chapter=chapter['id'], start_frame=frame, frames=n)
            if v.get('flex') and v['type'] == 'clip':
                seg['t'] = [v['t'][0], v['t'][0] + n / fps * v.get('speed', 1)]
                seg['reviewed_window'] = v['t']
            segments.append(seg)
            frame += n
        blocks.append(dict(id=block['id'], chapter=chapter['id'], start=start / fps, end=frame / fps,
                           vo_start=start / fps + lead, vo_duration=vo_durations[block['id']]))
    return dict(fps=fps, frames=frame, duration=frame / fps, segments=segments, blocks=blocks)


# ---------------------------------------------------------------- graphics

BG_TOP, BG_BOTTOM = (46, 50, 64), (32, 35, 46)  # dark, yet above blackdetect's 10 % luma threshold


def _background(W, H, seed=0):
    g = np.linspace(0, 1, H)[:, None, None]
    img = np.array(BG_TOP) * (1 - g) + np.array(BG_BOTTOM) * g
    img = np.repeat(img, W, axis=1)
    img += np.random.default_rng(seed).normal(0, 3, (H, W, 1))
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def _center(d, text, f, y, W, fill=WHITE):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def render_card(card, W, H, base=None):
    if card.get('kind') == 'image':  # a supplied still, e.g. Benjamin's title, fitted on black
        src = Image.open(Path(base or '.') / card['path']).convert('RGB')
        scale = min(W / src.width, H / src.height)
        src = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
        img = Image.new('RGB', (W, H))
        img.paste(src, ((W - src.width) // 2, (H - src.height) // 2))
        return img
    img = _background(W, H, seed=len(json.dumps(card, ensure_ascii=False)))
    d = ImageDraw.Draw(img)
    s = W / 1920
    kind = card.get('kind', 'title')
    d.rectangle((0, 0, W, int(8 * s)), fill=RED)
    if kind in ('title', 'chapter'):
        lines = card.get('lines', [])
        if kind == 'chapter':
            _center(d, card.get('kicker', ''), font(int(44 * s), heavy=True), H * .32, W, YELLOW)
        f = font(int(card.get('size', 150) * s), heavy=True, condensed=True)
        y = H * (.42 if kind == 'chapter' else .5) - len(lines) * 75 * s
        for line in lines:
            text, col = (line, WHITE) if isinstance(line, str) else (line['text'], tuple(line.get('color', WHITE)))
            _center(d, text, f, y, W, col)
            y += card.get('size', 150) * s * 1.05
        if card.get('sub'):
            _center(d, card['sub'], font(int(40 * s)), y + 30 * s, W, (210, 214, 224))
    elif kind == 'stat':
        _center(d, card['value'], font(int(230 * s), heavy=True, condensed=True), H * .22, W, YELLOW)
        y = H * .58
        for line in card.get('caption', '').split('\n'):
            _center(d, line, font(int(54 * s), heavy=True), y, W)
            y += 66 * s
    elif kind in ('table', 'compare'):
        _center(d, card.get('title', ''), font(int(64 * s), heavy=True, condensed=True), H * .1, W, YELLOW)
        if card.get('subtitle'):
            _center(d, card['subtitle'], font(int(36 * s)), H * .1 + 80 * s, W, (210, 214, 224))
        rows = card['rows']
        top = H * .3
        rh = min(110 * s, H * .55 / max(1, len(rows)))
        if kind == 'compare':
            for x, name in ((W * .62, card['left']), (W * .82, card['right'])):
                w = d.textlength(name, font=font(int(44 * s), heavy=True))
                d.text((x - w / 2, top - 70 * s), name, font=font(int(44 * s), heavy=True), fill=YELLOW)
        for i, row in enumerate(rows):
            y = top + i * rh
            hl = isinstance(row[-1], dict) and row[-1].get('hl')
            cells = [c for c in row if not isinstance(c, dict)]
            d.rectangle((W * .1, y, W * .9, y + rh - 10 * s), fill=(70, 30, 34) if hl else (58, 62, 78))
            fl = font(int(min(48, rh / s * .45) * s), heavy=True)
            d.text((W * .12, y + rh * .2), cells[0], font=fl, fill=WHITE)
            xs = [W * .62, W * .82] if kind == 'compare' else [W * .85]
            for x, c in zip(xs, cells[1:]):
                w = d.textlength(c, font=fl)
                d.text((x - w / (2 if kind == 'compare' else 1), y + rh * .2), c, font=fl,
                       fill=RED if hl else YELLOW)
    elif kind == 'quote':
        f = font(int(64 * s), heavy=True)
        words, lines, line = card['text'].split(), [], ''
        for w in words:
            if line and d.textlength(line + ' ' + w, font=f) > W * .78:
                lines.append(line)
                line = w
            else:
                line = (line + ' ' + w).strip()
        lines.append(line)
        y = H / 2 - len(lines) * 40 * s - 40 * s
        for line in lines:
            _center(d, line, f, y, W)
            y += 80 * s
        _center(d, card.get('author', ''), font(int(38 * s)), y + 30 * s, W, YELLOW)
    if card.get('source'):
        d.text((W * .05, H - 60 * s), card['source'], font=font(int(26 * s)), fill=(190, 194, 206))
    return img


def _box_label(d, text, x, y, f, accent=YELLOW):
    w, h = d.textlength(text, font=f), f.size
    d.rectangle((x - 14, y - 10, x + w + 14, y + h + 14), fill=(10, 12, 18, 200))
    d.rectangle((x - 14, y - 10, x - 6, y + h + 14), fill=accent + (255,))
    d.text((x, y), text, font=f, fill=WHITE + (255,))


def draw_overlay(layer, ov, p, W, H):
    d = ImageDraw.Draw(layer)
    col = tuple(ov.get('color', YELLOW)) + (255,)
    if ov['type'] == 'arrow':
        (x0, y0), (x1, y1) = [(x * W, y * H) for x, y in (ov['from'], ov['to'])]
        xe, ye = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
        d.line((x0, y0, xe, ye), fill=col, width=int(9 * W / 1920))
        if p > .5:
            ang, k = math.atan2(ye - y0, xe - x0), 34 * W / 1920
            d.polygon([(xe, ye), (xe - k * math.cos(ang - .45), ye - k * math.sin(ang - .45)),
                       (xe - k * math.cos(ang + .45), ye - k * math.sin(ang + .45))], fill=col)
    elif ov['type'] == 'circle':
        cx, cy, r = ov['center'][0] * W, ov['center'][1] * H, ov['r'] * H * (.6 + .4 * p)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=int(7 * W / 1920))
    elif ov['type'] == 'line':
        (x0, y0), (x1, y1) = [(x * W, y * H) for x, y in (ov['from'], ov['to'])]
        d.line((x0, y0, x0 + (x1 - x0) * p, y0 + (y1 - y0) * p), fill=col, width=int(6 * W / 1920))
    if ov['type'] == 'panel':
        x, y = ov.get('pos', [.035, .09])
        x, y = x * W - (1 - p) * 80 * W / 1920, y * H
        big, small = font(int(52 * W / 1920), heavy=True, condensed=True), font(int(34 * W / 1920), heavy=True)
        lines = ov['lines']
        width = max(d.textlength(t, font=big if i == 0 else small) for i, t in enumerate(lines)) + 50 * W / 1920
        height = 62 * W / 1920 + 44 * W / 1920 * (len(lines) - 1) + 24 * W / 1920
        alpha = int(255 * p)
        d.rectangle((x, y, x + width, y + height), fill=(8, 10, 16, int(195 * p)))
        d.rectangle((x, y, x + 9 * W / 1920, y + height), fill=tuple(ov.get('color', YELLOW)) + (alpha,))
        yy = y + 10 * W / 1920
        for i, t in enumerate(lines):
            d.text((x + 28 * W / 1920, yy), t, font=big if i == 0 else small,
                   fill=(YELLOW if i == 0 else WHITE) + (alpha,))
            yy += (62 if i == 0 else 44) * W / 1920
        return
    if ov.get('label') or ov['type'] == 'label':
        x, y = ov.get('pos', ov.get('to', ov.get('center', [.5, .5])))
        _box_label(d, ov.get('label', ov.get('text', '')), x * W, y * H, font(int(40 * W / 1920), heavy=True))


def text_patch(lines, spec, W, size=46):
    """Subtitle cue rendered once: white words, highlighted keywords, black outline."""
    f = font(int(size * W / 1920), heavy=False)
    stroke = max(2, int(4 * W / 1920))
    widths = [sum(f.getlength(w + ' ') for w in line) for line in lines]
    h = int(len(lines) * size * 1.25 * W / 1920 + 2 * stroke + 8)
    img = Image.new('RGBA', (int(max(widths)) + 4 * stroke, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        x, y = (img.width - widths[i]) / 2, stroke + i * size * 1.25 * W / 1920
        for w in line:
            d.text((x, y), w, font=f, fill=word_color(w, spec) + (255,), stroke_width=stroke,
                   stroke_fill=(0, 0, 0, 255))
            x += f.getlength(w + ' ')
    return np.asarray(img)


def blend(frame, patch, x, y):
    h, w = patch.shape[:2]
    x, y = int(max(0, min(frame.shape[1] - w, x))), int(max(0, min(frame.shape[0] - h, y)))
    a = patch[:, :, 3:4].astype(np.float32) / 255
    region = frame[y:y + h, x:x + w]
    region[:] = (patch[:, :, :3] * a + region * (1 - a)).astype(np.uint8)


# ---------------------------------------------------------------- sources and rights

RIGHTS_NOTE = ('Mise en ligne officielle publique. AUCUNE licence de réutilisation : extrait court, commenté, '
               'revendiqué au titre de la citation / fair use. '
               'Ni la présence officielle ni l’absence de revendication Content ID ne valent autorisation.')


def build_sources(spec, registry):
    """Provenance from the uploader's own metadata; rights stay a claim, never a licence."""
    decision = spec.get('rights') or {}
    if not decision.get('decided_by') or not decision.get('decided_on'):
        raise UltraError('spec rights: decided_by and decided_on required (who claimed fair use, and when)')
    rows = {}
    for line in Path(registry).read_text().splitlines()[1:]:
        sid, yid, _, fight, date, purpose = line.split('\t')
        info = json.loads(src_path(spec, f'proxies/{sid}.info.json').read_text())
        rows[sid] = dict(url=f'https://www.youtube.com/watch?v={yid}', youtube_id=yid,
                         channel=info.get('channel'), channel_id=info.get('channel_id'),
                         channel_verified=info.get('channel_is_verified'), title=info.get('title'),
                         upload_date=info.get('upload_date'), duration=info.get('duration'),
                         youtube_license=info.get('license'), fight=fight, fight_date=date,
                         purpose=purpose, credit=info.get('channel'),
                         rights=dict(status='official_upload_fair_use_claim', licence=None,
                                     decided_by=decision['decided_by'], decided_on=str(decision['decided_on']),
                                     note=decision.get('note', RIGHTS_NOTE)))
    save(out_path(spec, spec['sources_file']), rows)
    return rows


# ---------------------------------------------------------------- frames

def decode(path, start, n, W, H, fps, speed=1.0, zoom=None):
    """Exactly n RGB frames; slow motion repeats source frames (honest, no interpolation)."""
    crop = (f"crop=iw*{zoom[2]}:ih*{zoom[3]}:iw*{zoom[0]}:ih*{zoom[1]}," if zoom else '')
    vf = (f'{crop}scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,'
          f'setsar=1,setpts=PTS/{speed},fps={fps},format=rgb24')
    # -t BEFORE -i limits the source read; after -i it cut slow motion to half and froze the rest (render v1).
    proc = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-ss', f'{max(0, start):.4f}',
                             '-t', f'{n / fps * speed + .5:.4f}', '-i', str(path), '-an', '-vf', vf, '-frames:v', str(n),
                             '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    size, last, got = W * H * 3, None, 0
    try:
        while got < n:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            last = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            got += 1
            yield last
    finally:
        proc.stdout.close()
        proc.wait()
    if last is None:
        raise UltraError(f'No frame decoded from {path} at {start}')
    if n - got > 2:
        raise UltraError(f'{path}: {n - got} of {n} frames missing at {start:.2f}s; refusing to freeze the picture')
    for _ in range(n - got):  # container end inside the last frame interval
        yield last


def ken_burns(img, n, amount=.05):
    """Slow push-in so held images are not frozen pictures (freezedetect stays meaningful)."""
    import cv2
    H, W = img.shape[:2]
    for i in range(n):
        z = 1 + amount * i / max(1, n - 1)
        w, h = int(W / z), int(H / z)
        x, y = (W - w) // 2, (H - h) // 2
        yield cv2.resize(img[y:y + h, x:x + w], (W, H), interpolation=cv2.INTER_LINEAR)


def segment_frames(spec, seg, proxy=False):
    W, H, fps = spec['video']['width'], spec['video']['height'], spec['video']['fps']
    n, kind = seg['frames'], seg['type']
    if kind == 'clip':
        path, local = resolve(spec, seg['src'], *seg['t'], proxy=proxy)
        fade_in = round(seg.get('fade_in', 0) * fps)
        for i, f in enumerate(decode(path, local, n, W, H, fps, seg.get('speed', 1), seg.get('zoom'))):
            yield (f * ((i + 1) / (fade_in + 1))).astype(np.uint8) if i < fade_in else f
    elif kind == 'freeze':
        path, local = resolve(spec, seg['src'], seg['at'], seg['at'], proxy=proxy)
        yield from ken_burns(next(decode(path, local, 1, W, H, fps, 1, seg.get('zoom'))), n)
    elif kind == 'card':
        img = np.asarray(render_card(seg, W, H, spec['_out']))
        fade_out = round(seg.get('fade_out', 0) * fps)
        for i, f in enumerate(ken_burns(img, n, .03)):
            yield (f * min(1, (n - 1 - i) / fade_out)).astype(np.uint8) if fade_out and i >= n - fade_out else f
    elif kind == 'split':
        w2, h2 = W // 2 - 30, (W // 2 - 30) * 9 // 16
        gens = []
        for p in (seg['left'], seg['right']):
            path, local = resolve(spec, p['src'], *p['t'], proxy=proxy)
            m = round((p['t'][1] - p['t'][0]) / p.get('speed', 1) * fps)
            gens.append((decode(path, local, min(n, m), w2 // 2 * 2, h2 // 2 * 2, fps, p.get('speed', 1)), p))
        bg = np.asarray(_background(W, H, 3)).copy()
        heads = [text_patch([p['label'].split()], {}, W, size=40) for _, p in gens]
        last = [None, None]
        for _ in range(n):
            frame = bg.copy()
            for k, (g, p) in enumerate(gens):
                f = next(g, None)
                last[k] = f if f is not None else last[k]
                x = 20 + k * (W // 2 + 10)
                y = (H - last[k].shape[0]) // 2 + 30
                frame[y:y + last[k].shape[0], x:x + last[k].shape[1]] = last[k]
                blend(frame, heads[k], x + (last[k].shape[1] - heads[k].shape[1]) // 2, y - heads[k].shape[0] - 14)
            yield frame


# ---------------------------------------------------------------- audio

def _rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) + 1e-9


def _smooth(env, rate, attack, release):
    out, g = np.empty_like(env), env[0]
    a, r = math.exp(-1 / (attack * rate)), math.exp(-1 / (release * rate))
    for i, v in enumerate(env):
        g = a * g + (1 - a) * v if v > g else r * g + (1 - r) * v
        out[i] = g
    return out


def mix(spec, plan, vo_files, out, start=0.0, end=None, proxy=False, voice_out=None):
    """Voice first: music ducks under speech, ring ambience stays under both; one FLAC written."""
    sr = 48000
    end = plan['duration'] if end is None else end
    N = round((end - start) * sr)
    voice, amb = np.zeros((N, 2), np.float32), np.zeros((N, 2), np.float32)

    def place(dst, x, t):
        i = round((t - start) * sr)
        a, b = max(0, i), min(N, i + len(x))
        if b > a:
            dst[a:b] += x[a - i:b - i]

    for blk in plan['blocks']:
        if blk['end'] <= start or blk['start'] >= end:
            continue
        x = pcm(vo_files[blk['id']])
        speech = x[np.abs(x[:, 0]) > 10 ** (-40 / 20)]
        x *= 10 ** (-17 / 20) / _rms(speech if len(speech) else x)  # same loudness for every block
        place(voice, x, blk['vo_start'])
    fps = plan['fps']
    for seg in plan['segments']:
        t0, t1 = seg['start_frame'] / fps, (seg['start_frame'] + seg['frames']) / fps
        if seg['type'] != 'clip' or seg.get('speed', 1) != 1 or seg.get('audio') == 'mute' or t1 <= start or t0 >= end:
            continue
        path, local = resolve(spec, seg['src'], *seg['t'], proxy=proxy)
        x = pcm(path, local, t1 - t0)
        if len(x):
            x *= 10 ** ((-20 if seg.get('audio') == 'featured' else -26) / 20) / _rms(x)  # ducked 8 dB more under the voice
            ramp = np.linspace(0, 1, min(1440, len(x) // 2), dtype=np.float32)[:, None]
            x[:len(ramp)] *= ramp
            x[len(x) - len(ramp):] *= ramp[::-1]
            place(amb, x, t0)
    tracks = [out_path(spec, m['path']) for m in spec.get('music', [])]
    music = np.zeros((N, 2), np.float32)
    if tracks:
        def audible(x):  # stock tracks end on long near-silent tails; a mute picture over them reads as a gap
            idx = np.where(np.abs(x).max(axis=1) > 10 ** (-40 / 20))[0]
            return x[idx[0]:idx[-1] + 1] if len(idx) else x
        loop = audible(pcm(tracks[0]))
        xf = np.linspace(0, 1, 2 * sr, dtype=np.float32)[:, None]  # 2 s crossfade between tracks
        for t in tracks[1:]:
            nxt = audible(pcm(t))
            loop = np.concatenate([loop[:-len(xf)], loop[-len(xf):] * (1 - xf) + nxt[:len(xf)] * xf, nxt[len(xf):]])
        offset = round(start * sr) % len(loop)
        music = np.resize(np.roll(loop, -offset, axis=0), (N, 2))
        music *= 10 ** (-20 / 20) / _rms(music)
    hop = sr // 100
    active = np.abs(voice[:, 0]).reshape(-1, hop).max(axis=1) if N % hop == 0 else \
        np.abs(np.pad(voice[:, 0], (0, hop - N % hop))).reshape(-1, hop).max(axis=1)
    duck = _smooth((active > 10 ** (-45 / 20)).astype(np.float64), 100, .12, .9)
    gain = np.repeat(10 ** ((-6 - 8 * duck) / 20), hop)[:N].astype(np.float32)  # -6 dB bed, -14 dB under voice
    total = voice + amb * (gain / 10 ** (-6 / 20))[:, None] + music * gain[:, None]
    if voice_out:
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(sr), '-ac', '2',
                        '-i', 'pipe:0', '-ac', '1', '-c:a', 'pcm_s16le', str(voice_out)], input=voice.tobytes(), check=True)
    fade = round(.5 * sr)
    if end >= plan['duration'] - 1e-6:
        total[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    loud = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-f', 'f32le', '-ar', str(sr), '-ac', '2', '-i', 'pipe:0',
                           '-af', 'ebur128', '-f', 'null', '-'], input=total.tobytes(), capture_output=True).stderr
    lufs = float(re.findall(rb'I:\s+(-?[0-9.]+) LUFS', loud)[-1])
    total *= 10 ** ((-16 - lufs) / 20)
    enc = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(sr), '-ac', '2',
                          '-i', 'pipe:0', '-af', 'alimiter=limit=0.79:level=0:latency=1', '-c:a', 'flac',
                          '-sample_fmt', 's16', str(out)], input=total.tobytes())
    if enc.returncode:
        raise UltraError('Mix encode failed')
    speaking = np.repeat(duck > .5, hop)[:N]
    bed = (amb * (gain / 10 ** (-6 / 20))[:, None] + music * gain[:, None])[speaking]
    return dict(path=str(out), lufs_before_norm=lufs, target_lufs=-16,
                voice_to_bed_db=round(20 * math.log10(_rms(voice[speaking]) / _rms(bed)), 1) if speaking.any() else None)


# ---------------------------------------------------------------- render

def cue_layer(spec, cues, W, H):
    patches = [text_patch(c['lines'], spec, W) for c in cues]
    return [(c['start'], c['end'], p) for c, p in zip(cues, patches)]


def render(spec, plan, cues, audio, output, start=0.0, end=None, proxy=False, crf=19):
    W, H, fps = spec['video']['width'], spec['video']['height'], plan['fps']
    end = plan['duration'] if end is None else end
    f0, f1 = round(start * fps), round(end * fps)
    output = Path(output)
    if output.exists():
        raise UltraError(f'Preserve existing output: {output}')
    require_space(output.parent, int((end - start) * 9.5e6 / 8 * 1.1), 'documentary render')
    partial = output.with_name(f'.{output.stem}-{uuid.uuid4().hex[:8]}.partial.mp4')
    enc = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                            '-s', f'{W}x{H}', '-r', str(fps), '-i', 'pipe:0', '-i', str(audio),
                            '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf),
                            '-maxrate', '9M', '-bufsize', '18M', '-pix_fmt', 'yuv420p', '-g', str(2 * fps),
                            '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-t', f'{(f1 - f0) / fps:.4f}',
                            '-movflags', '+faststart', str(partial)], stdin=subprocess.PIPE)
    subs = cue_layer(spec, [c for c in cues if c['end'] > start and c['start'] < end], W, H)
    tag_font = font(int(30 * W / 1920), heavy=True)
    written = 0
    try:
        for seg in plan['segments']:
            s0, s1 = seg['start_frame'], seg['start_frame'] + seg['frames']
            if s1 <= f0 or s0 >= f1:
                continue
            static = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(static)
            parts = _parts(seg)
            if parts:
                srcs = [spec['sources'][q['src']] for q in parts]
                credit = 'Images : ' + ' | '.join(f"{s['credit']} · {s['fight']} ({s['fight_date'][:4]})" for s in srcs) + ' · extrait commenté'
                w = d.textlength(credit, font=font(int(22 * W / 1920)))
                d.rectangle((W - w - 40, 18, W - 14, 58), fill=(0, 0, 0, 150))
                d.text((W - w - 27, 24), credit, font=font(int(22 * W / 1920)), fill=(235, 235, 235, 255))
                lab = dict(dict(freeze='ARRÊT SUR IMAGE', slow='RALENTI ×{speed}', decimal=','), **spec.get('labels', {}))
                tag = seg.get('tag') or (lab['freeze'] if seg['type'] == 'freeze' else
                                         lab['slow'].format(speed=f"{seg.get('speed'):g}".replace('.', lab['decimal']))
                                         if seg.get('speed', 1) != 1 else None)
                if tag:
                    _box_label(d, tag, 44, 34, tag_font, RED)
            static_np = np.asarray(static)
            bbox = static.getbbox()
            static_patch = static_np[bbox[1]:bbox[3], bbox[0]:bbox[2]] if bbox else None
            for i, frame in enumerate(segment_frames(spec, seg, proxy)):
                k = s0 + i
                if k < f0:
                    continue
                if k >= f1:
                    break
                frame = np.array(frame, copy=True)
                t_local = i / fps
                live = [o for o in seg.get('overlays', []) if o.get('at', 0) <= t_local < o.get('until', 1e9)]
                if live:
                    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                    for o in live:
                        draw_overlay(layer, o, min(1, (t_local - o.get('at', 0)) / .35), W, H)
                    lb = layer.getbbox()
                    if lb:
                        blend(frame, np.asarray(layer)[lb[1]:lb[3], lb[0]:lb[2]], lb[0], lb[1])
                if static_patch is not None:
                    blend(frame, static_patch, bbox[0], bbox[1])
                t = k / fps
                for a, b, p in subs:
                    if a <= t < b:
                        top = seg.get('subs') == 'top'
                        blend(frame, p, (W - p.shape[1]) // 2, 70 if top else H - p.shape[0] - 46)
                enc.stdin.write(frame.tobytes())
                written += 1
        enc.stdin.close()
        if enc.wait():
            raise UltraError('Encoder failed')
    except BaseException:
        enc.kill()
        partial.unlink(missing_ok=True)
        raise
    if written != f1 - f0:
        raise UltraError(f'Rendered {written} frames, expected {f1 - f0}')
    os.link(partial, output)
    partial.unlink()
    return dict(output=str(output), frames=written, duration=written / fps)


# ---------------------------------------------------------------- reports

def build_cues(spec, plan, align):
    cues = []
    for blk, (_, block) in zip(plan['blocks'], iter_blocks(spec)):
        toks = timed_tokens(' '.join(block['text'].split()), align.get(blk['id'], []), blk['vo_duration'])
        cues += make_cues(toks, blk['vo_start'])
    return cues


def write_reports(spec, plan, cues):
    facts = load_facts(spec)
    fps, out = plan['fps'], Path(spec['_out'])
    by_block = {}
    for seg in plan['segments']:
        by_block.setdefault(seg['block'], []).append(seg)
    ledger, md = [], [f"# {spec['title']}\n", "Narration française exacte (texte affiché ; `say` = graphie envoyée à la voix).\n"]
    for blk, (chapter, block) in zip(plan['blocks'], iter_blocks(spec)):
        visuals = []
        for seg in by_block[blk['id']]:
            row = dict(type=seg['type'], timeline=[round(seg['start_frame'] / fps, 3),
                                                   round((seg['start_frame'] + seg['frames']) / fps, 3)])
            for p in _parts(seg):
                src = spec['sources'][p['src']]
                row.setdefault('evidence', []).append(dict(
                    source=p['src'], url=src['url'], channel=src['channel'], fight=src['fight'],
                    fight_date=src['fight_date'], source_start=(p.get('t') or [p.get('at')])[0],
                    source_end=(p.get('t') or [None, p.get('at')])[1], speed=p.get('speed', 1),
                    visible_action=p['action'], confidence=p['confidence'], provenance=p['provenance'],
                    review_sheet=p.get('sheet'), rights=src['rights']['status']))
            if seg['type'] == 'card':
                row['card'] = {k: seg[k] for k in ('kind', 'title', 'lines', 'value', 'caption', 'rows', 'source') if k in seg}
            visuals.append(row)
        claims = [dict(category=c['cat'], facts=[dict(id=f, claim=facts[f]['claim_fr'], value=facts[f]['value'],
                                                     sources=facts[f]['sources']) for f in c.get('facts', [])])
                  for c in block.get('claims', [])]
        ledger.append(dict(block=blk['id'], chapter=chapter['id'], narration=block['text'],
                           voice_start=round(blk['vo_start'], 3), voice_duration=round(blk['vo_duration'], 3),
                           claims=claims, visuals=visuals))
        md.append(f"**[{blk['vo_start'] // 60:02.0f}:{blk['vo_start'] % 60:04.1f}] {blk['id']}** "
                  f"({', '.join(c['cat'] for c in block.get('claims', []))}) — {block['text']}\n")
    save(out / 'evidence_ledger.json', dict(
        note='agent_frame_review = images échantillonnées vues par Claude (planche citée), pas une revue humaine.',
        categories_excluded_from_narration=['unverified_claim'], blocks=ledger))
    save(out / 'edit_plan.json', plan)
    (out / spec.get('names', {}).get('script', 'script_fr.md')).write_text('\n'.join(md))
    chapters = [(b['start'], b['chapter']) for i, b in enumerate(plan['blocks'])
                if i == 0 or b['chapter'] != plan['blocks'][i - 1]['chapter']]
    names = {c['id']: c.get('title', c['id']) for c in spec['chapters']}
    credits = '\n'.join(f"- {s['channel']} — « {s['title']} » — {s['url']}" for s in spec['sources'].values())
    music = '\n'.join(f"- {m['title']} — {m.get('author', '')} — {m.get('license_url', '')}" for m in spec.get('music', []))
    (out / 'youtube_metadata.md').write_text(f"""# Métadonnées YouTube (non publiées)

## Titre
{spec['title']}

## Description
{spec.get('description', '').strip()}

## Chapitres
""" + '\n'.join(f"{int(t // 60)}:{int(t % 60):02d} {names.get(c, c)}" for t, c in chapters) + f"""

## Crédits images (extraits courts commentés, aucune licence : citation / fair use revendiqué)
{credits}

## Musique
{music}

{spec['voice'].get('credit', 'Voix off : synthèse Qwen3-TTS (Apache-2.0).')}
""")


# ---------------------------------------------------------------- quality and CLI

def write_alignment(spec, plan, cues):
    """One row per shot: who is on screen, what is visible, what the voice says over it, does it match."""
    fps, rows = plan['fps'], []
    subjects = {b['id']: b.get('subject') or [] for _, b in iter_blocks(spec)}
    for seg in plan['segments']:
        a, b = seg['start_frame'] / fps, (seg['start_frame'] + seg['frames']) / fps
        said = ' '.join(' '.join(' '.join(line) for line in c['lines']) for c in cues if c['start'] < b and c['end'] > a)
        for p in _parts(seg) or [None]:
            row = dict(block=seg['block'], timeline=[round(a, 2), round(b, 2)], type=seg['type'],
                       narration_subject=subjects[seg['block']], narration_during_shot=said)
            if p:
                src = spec['sources'][p['src']]
                boxer = set((p.get('boxer') or '').split('+')) - {''}
                row.update(boxer_on_screen=p.get('boxer'), source=p['src'], url=src['url'], fight=src['fight'],
                           source_timecode=p.get('t') or [p.get('at')], visible_action=p['action'],
                           confidence=p['confidence'], provenance=p['provenance'], review_sheet=p.get('sheet'),
                           match=bool(boxer & set(subjects[seg['block']])),
                           uncertainty=None if p['confidence'] >= .7 else 'action vue sur images échantillonnées, confiance < 0,7')
            else:
                row.update(boxer_on_screen=None, match=True, uncertainty=None)
            rows.append(row)
    footage = [r for r in rows if r.get('source')]
    save(out_path(spec, spec.get('names', {}).get('alignment', 'shot_narration_alignment.json')), dict(
        shots=rows, footage_shots=len(footage), matching=sum(r['match'] for r in footage),
        verified_ge_0_7=sum(r['confidence'] >= .7 for r in footage)))
    return rows


def integrity(spec, plan, cues):
    """Checks that do not need eyes: windows kept whole, no reused footage, readable cues."""
    fps, issues, used = plan['fps'], [], {}
    for seg in plan['segments']:
        for p in _parts(seg):
            if 't' in p:
                a, b = p['t']
                if seg['type'] == 'clip' and abs(seg['frames'] / fps * p.get('speed', 1) - (b - a)) > 1.5 / fps * p.get('speed', 1):
                    issues.append(f"{seg['block']}: {p['src']} window shortened")
                for (a2, b2, blk) in used.get(p['src'], []):
                    if a < b2 - .05 and a2 < b - .05 and not (p.get('speed', 1) != 1 or blk == seg['block']):
                        issues.append(f"{seg['block']}: {p['src']} {a}-{b} reuses footage of {blk}")
                used.setdefault(p['src'], []).append((a, b, seg['block']))
    long_lines = [c for c in cues if len(c['lines']) > 2 or max(len(' '.join(line)) for line in c['lines']) > 44]
    return dict(window_issues=issues, cues=len(cues), cues_over_2_lines_or_44_chars=len(long_lines),
                min_cue_seconds=round(min(c['end'] - c['start'] for c in cues), 2) if cues else None)


def main(argv=None):
    p = argparse.ArgumentParser(prog='ueu documentary', description='Spec → voice, subtitles, plan, verified MP4')
    p.add_argument('--spec', required=True)
    p.add_argument('--stage', choices=['plan', 'render'], default='render')
    p.add_argument('--preview', nargs=2, type=float, metavar=('START', 'SECONDS'))
    p.add_argument('--proxy', action='store_true', help='render from 144p review proxies (layout tests only)')
    p.add_argument('--output', help='final MP4 name inside the output folder')
    args = p.parse_args(argv)
    try:
        return run(args)
    except (UltraError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


def run(args):
    from .jobs import Job
    from .quality import finalize_output, verify_output
    spec = load_spec(args.spec)
    errors = validate(spec)
    if errors:
        raise UltraError('Spec invalide :\n' + '\n'.join(errors))
    out = Path(spec['_out'])
    jobdir = out / 'job'
    job = Job(jobdir) if (jobdir / 'manifest.json').exists() else Job(jobdir, options=dict(spec=spec['_path']))
    vj = voice_jobs(spec)
    vkey = _key(vj)

    def voice():
        run_voice(spec, 'tts')
        return dict(artifacts=[i['out'] for i in vj['items']], files={i['id']: i['out'] for i in vj['items']})
    files = tempo_files(spec, job.stage(f'voice-{vkey}', voice)['files'])
    raw = {i['id']: i['out'] for i in vj['items']}
    v = spec['voice']
    tempo = _key(v.get('tempo', 1.0), v.get('target_wpm'), v.get('trim_pauses'), v.get('max_tempo'))
    # v2: no initial_prompt (it made Whisper repeat the script); timings measured on the audio actually heard
    align_file = out_path(spec, f'audio/align-v2-{vkey}-x{tempo}.json')

    def align():
        run_voice(spec, 'align', files if files != raw else None)
        out_path(spec, 'audio/align.json').rename(align_file)
        return dict(artifacts=[str(align_file)])
    job.stage(f'align-v2-{vkey}-x{tempo}', align)
    plan = build_plan(spec, {k: probe(Path(v))['duration'] for k, v in files.items()})
    lo, hi = spec['duration_range']
    print(f"plan: {len(plan['segments'])} segments, {plan['duration']:.1f}s", flush=True)
    if not lo <= plan['duration'] <= hi:
        raise UltraError(f"Durée planifiée {plan['duration']:.1f}s hors de [{lo}, {hi}]")
    cues = build_cues(spec, plan, json.loads(align_file.read_text()))
    names = spec.get('names', {})
    write_subtitles(spec, cues, out / names.get('ass', 'subtitles_fr.ass'), out / names.get('srt', 'subtitles_fr.srt'))
    write_reports(spec, plan, cues)
    write_alignment(spec, plan, cues)
    checks = integrity(spec, plan, cues)
    if checks['window_issues']:
        raise UltraError('\n'.join(checks['window_issues']))
    if args.stage == 'plan':
        print(json.dumps(checks, ensure_ascii=False))
        return 0
    W, H, fps = spec['video']['width'], spec['video']['height'], plan['fps']
    if args.preview:
        start, seconds = args.preview
        start = round(start * fps) / fps
        end = min(plan['duration'], start + round(seconds * fps) / fps)
        tag = f"preview_{start:06.1f}-{end:06.1f}{'_proxy' if args.proxy else ''}"
        audio = out / 'render' / f'{tag}.flac'
        audio.parent.mkdir(exist_ok=True)
        stats = mix(spec, plan, files, audio, start, end, args.proxy)
        video = out / 'render' / f'{tag}.mp4'
        video.unlink(missing_ok=True)  # previews are disposable test exports
        render(spec, plan, cues, audio, video, start, end, args.proxy)
        audio.unlink()
        report = verify_output(video, end - start, width=W, height=H, fps=fps, true_peak_limit=-1.0)
        save(video.with_suffix('.preview.json'), dict(mix=stats, verification=report, integrity=checks))
        print(json.dumps(dict(video=str(video), status=report['status'], flags=report['quality_flags'],
                              true_peak=report['true_peak_dbfs'], voice_to_bed_db=stats['voice_to_bed_db'])))
        return 0
    final = out / (args.output or spec.get('names', {}).get('final', 'documentary.mp4'))
    rkey = _key(plan, cues, spec.get('music'), args.proxy, 'renderer-5')  # 5: image cards, clip fade-in

    def do_render():
        audio = out / 'render' / f'mix-{rkey}.flac'
        audio.parent.mkdir(exist_ok=True)
        stats = mix(spec, plan, files, audio, proxy=args.proxy, voice_out=out / names.get('voiceover', 'voiceover.wav'))
        save(out / 'render' / f'mix-{rkey}.json', stats)
        render(spec, plan, cues, audio, final, proxy=args.proxy)
        audio.unlink()
        return dict(artifacts=[str(final), str(out / names.get('voiceover', 'voiceover.wav'))], mix=stats)
    rendered = job.stage(f'render-{rkey}', do_render)
    verification = finalize_output(final, plan['duration'], job_dir=out, width=W, height=H, fps=fps)
    hd = json.loads(src_path(spec, 'hd_index.json').read_text()) if not args.proxy else {}
    save(out / 'quality_report.json', dict(
        status=verification['status'], output=verification['output'], sha256=verification['sha256'],
        duration=verification['duration'], duration_range_ok=lo <= verification['duration'] <= hi,
        decoded_frames=verification['decoded_video_frames'], true_peak_dbfs=verification['true_peak_dbfs'],
        quality_flags=verification['quality_flags'], full_decode=verification['full_decode'],
        mix=rendered['mix'], integrity=checks,
        hd_windows=dict(count=sum(len(v) for v in hd.values()),
                        min_match_r=min((e['match_r'] for v in hd.values() for e in v), default=None),
                        heights=sorted({e['height'] for v in hd.values() for e in v})),
        not_verified=['visionnage et écoute humains continus', 'identité de chaque adversaire hors fiches citées',
                      'impact réel des coups (seule l’action visible est décrite)', 'droits : fair use revendiqué, aucune licence',
                      'qualité perçue de la voix (mesurée par ASR et hauteur, pas écoutée)']))
    print(json.dumps(dict(final=verification['output'], status=verification['status'],
                          duration=verification['duration']), ensure_ascii=False))
    return 0
