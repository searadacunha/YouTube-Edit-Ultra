"""Voice helper for `ueu documentary`, run by the interpreter that owns MLX / faster-whisper.

  design --model M --instruct TEXT --text TEXT --out DIR --seeds 1,2,3   VoiceDesign candidates
  tts    --model M --jobs jobs.json                                      Base model, cloned synthetic ref
  align  --jobs jobs.json --model base                                   word timestamps per wav
  qc     --jobs jobs.json --ref FILE[:A-B] [--other FILE:A-B]           ASR match, negations, voice resemblance
  diarize --audio FILE --output diar.json                               two-speaker split (find a voice to clone)

jobs.json: {"lang": "French", "ref_audio": ..., "ref_text": ..., "items": [{"id", "text", "out"}]}
Optional: item "max_seconds" (slot to fit, e.g. a dubbed track on an existing edit) and jobs "trim_pauses"
(seconds, as in the spec): more seeds are tried and the shortest take is kept.
Existing outputs are kept (resumable); each file is written to a temporary name then renamed.
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

NEGATIONS = {  # a dropped negation inverts the claim: counted in the script and in what ASR heard
    'fr': r"\b(ne|n'|pas|jamais|aucun|aucune|personne|rien|non|zéro)\b",
    'en': r"\b(no|not|never|nobody|none|nothing|zero)\b|n't\b",
    'es': r"\b(no|nunca|nadie|ningún|ninguna|nada|cero)\b",
    'pt': r"\b(não|nunca|ninguém|nenhum|nenhuma|nada|zero)\b",
}


def asr_match(ref, hyp):
    """Share of script words found, in order, in the transcript (punctuation and case ignored)."""
    norm = lambda text: [w for w in (re.sub(r'\W', '', t.lower()) for t in text.split()) if w]  # noqa: E731
    r, h = norm(ref), norm(hyp)
    return sum(b.size for b in difflib.SequenceMatcher(None, r, h).get_matching_blocks()) / max(1, len(r))


def negations(text, lang):
    return len(re.findall(NEGATIONS.get(lang, NEGATIONS['en']), text, re.I))


def two_speakers(E):
    """2-means on unit embeddings, seeded by the first segment and the one least like it. Label 0 = first speaker."""
    import numpy as np
    c = [E[0], E[np.argmin(E @ E[0])]]
    for _ in range(20):
        lab = (E @ c[1] > E @ c[0]).astype(int)
        c = [E[lab == k].mean(0) if (lab == k).any() else c[k] for k in (0, 1)]
        c = [x / np.linalg.norm(x) for x in c]
    return lab, c


def _pcm(path, rate, window=None):
    """Mono float32 through FFmpeg; window = (start, end) seconds."""
    import numpy as np
    cut = ['-ss', str(window[0]), '-to', str(window[1])] if window else []
    raw = subprocess.run(['ffmpeg', '-v', 'error', *cut, '-i', str(path), '-ac', '1', '-ar', str(rate), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def _ref(arg):
    """FILE or FILE:START-END."""
    m = re.fullmatch(r'(.+):([\d.]+)-([\d.]+)', arg)
    return (m[1], (float(m[2]), float(m[3]))) if m else (arg, None)


def _trimmed_seconds(audio, rate, trim):
    """Duration once pauses longer than `trim` s are shortened, exactly as the engine's trim_pauses."""
    if not trim:
        return len(audio) / rate
    out = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(rate), '-ac', '1', '-i', 'pipe:0', '-af',
                          f'silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:'
                          f'stop_duration={trim}:stop_threshold=-45dB:stop_silence={trim * .7:.3f}', '-f', 'f32le', '-'],
                         input=audio.astype('float32').tobytes(), capture_output=True, check=True).stdout
    return len(out) / 4 / rate


def _write(audio, rate, out):
    import wave
    import numpy as np
    out = Path(out)
    tmp = out.with_name(f'.{out.stem}.partial.wav')
    pcm = (np.clip(np.asarray(audio, dtype='float32'), -1, 1) * 32767).astype('<i2')
    with wave.open(str(tmp), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    os.replace(tmp, out)


def _concat(results):
    import numpy as np
    return np.concatenate([np.array(r.audio, dtype='float32').reshape(-1) for r in results])


def design(a):
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
    model = load_model(a.model)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for seed in map(int, a.seeds.split(',')):
        target = out / f'design_seed{seed}.wav'
        if target.exists():
            continue
        mx.random.seed(seed)
        res = list(model.generate_voice_design(text=a.text, language=a.lang, instruct=a.instruct))
        _write(_concat(res), model.sample_rate, target)
        print(f'{target} {len(_concat(res)) / model.sample_rate:.2f}s', flush=True)


def tts(a):
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
    jobs = json.loads(Path(a.jobs).read_text())
    if all(Path(i['out']).exists() for i in jobs['items']):
        return  # nothing to synthesize: do not load (or download) the model
    model = load_model(a.model)
    for item in jobs['items']:
        target = Path(item['out'])
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        kw = dict(text=item['text'], lang_code=jobs.get('lang', 'french'), ref_audio=jobs['ref_audio'],
                  temperature=jobs.get('temperature', 0.7))
        if jobs.get('ref_text'):  # without it Qwen3 clones the timbre only (x-vector), safer across languages
            kw['ref_text'] = jobs['ref_text']
        limit = max(8.0, len(item['text'].split()) / 1.3)  # slower than ~80 wpm = runaway generation
        slot, best = item.get('max_seconds'), None
        for attempt in range(6 if slot else 4):
            mx.random.seed(int(jobs.get('seed', 7)) + 101 * attempt)
            audio = _concat(list(model.generate(**kw)))
            if len(audio) / model.sample_rate > limit:
                print(f"{item['id']} runaway {len(audio) / model.sample_rate:.0f}s, retry", flush=True)
                continue
            heard = _trimmed_seconds(audio, model.sample_rate, jobs.get('trim_pauses'))
            if best is None or heard < best[0]:
                best = (heard, audio)
            if not slot or heard <= slot:
                break
        if best is None:
            raise SystemExit(f"{item['id']}: generation keeps running away; not written")
        _write(best[1], model.sample_rate, target)
        over = f' OVER slot {slot:.2f}s' if slot and best[0] > slot else ''  # left to atempo or a shorter text
        print(f"{item['id']} {len(best[1]) / model.sample_rate:.2f}s{over}", flush=True)


def align(a):
    from faster_whisper import WhisperModel
    jobs = json.loads(Path(a.jobs).read_text())
    model = WhisperModel(a.model, device='cpu', compute_type='int8')
    result = {}
    for item in jobs['items']:
        # faster-whisper 1.2.1's own decoder breaks on PyAV 17+; ffmpeg gives the same 16 kHz mono floats.
        segments, _ = model.transcribe(_pcm(item['out'], 16000), language=jobs.get('asr_lang', 'fr'), word_timestamps=True,
                                       condition_on_previous_text=False, vad_filter=False)
        result[item['id']] = [dict(w=w.word.strip(), start=w.start, end=w.end)
                              for s in segments for w in (s.words or [])]
        print(item['id'], len(result[item['id']]), 'words', flush=True)
    Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=1))


def _embedder(model_id):
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    model = load_model(model_id)

    def emb(x):  # Qwen3-TTS speaker embedding, unit length, on 24 kHz audio
        e = np.array(model.extract_speaker_embedding(mx.array(x))).reshape(-1)
        return e / np.linalg.norm(e)
    return emb


def qc(a):
    import statistics
    from faster_whisper import WhisperModel
    jobs = json.loads(Path(a.jobs).read_text())
    lang = jobs.get('asr_lang', 'fr')
    emb = _embedder(a.tts_model)
    ref = emb(_pcm(_ref(a.ref)[0], 24000, _ref(a.ref)[1]))
    other = emb(_pcm(_ref(a.other)[0], 24000, _ref(a.other)[1])) if a.other else None
    asr = WhisperModel(a.model, device='cpu', compute_type='int8')
    report = {}
    for item in jobs['items']:
        x = _pcm(item['out'], 24000)
        segments, _ = asr.transcribe(_pcm(item['out'], 16000), language=lang, beam_size=5, condition_on_previous_text=False)
        hyp = ' '.join(s.text.strip() for s in segments)
        e = emb(x)
        row = dict(seconds=round(len(x) / 24000, 2), wpm=round(len(item['text'].split()) / (len(x) / 24000) * 60),
                   asr=hyp, asr_match=round(asr_match(item['text'], hyp), 2),
                   negations_script=negations(item['text'], lang), negations_heard=negations(hyp, lang),
                   sim_ref=round(float(e @ ref), 3), sim_other=None if other is None else round(float(e @ other), 3))
        report[item['id']] = row
        flag = row['asr_match'] < .8 or row['negations_script'] != row['negations_heard']
        print(item['id'], row['seconds'], 's match', row['asr_match'], 'ref', row['sim_ref'], 'CHECK' if flag else '', flush=True)
    Path(a.output).write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print('median resemblance ref', statistics.median(r['sim_ref'] for r in report.values()),
          'other', None if other is None else statistics.median(r['sim_other'] for r in report.values()))


def diarize(a):
    import numpy as np
    from faster_whisper import WhisperModel
    asr = WhisperModel(a.model, device='cpu', compute_type='int8')
    segments, _ = asr.transcribe(_pcm(a.audio, 16000), language=a.lang, condition_on_previous_text=False)
    segs = [dict(start=s.start, end=s.end, text=s.text.strip()) for s in segments if s.end - s.start >= a.min_seconds]
    if len(segs) < 2:
        raise SystemExit('fewer than two usable segments')
    audio, emb = _pcm(a.audio, 24000), _embedder(a.tts_model)
    E = np.stack([emb(audio[int(s['start'] * 24000):int(s['end'] * 24000)]) for s in segs])
    lab, c = two_speakers(E)
    rows = [dict(s, speaker='AB'[k], sim_A=round(float(e @ c[0]), 3), sim_B=round(float(e @ c[1]), 3))
            for s, e, k in zip(segs, E, lab)]
    Path(a.output).write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    for k in (0, 1):  # listen to a few segments before choosing a reference: clusters are not identities
        print('speaker', 'AB'[k], round(sum(r['end'] - r['start'] for r in rows if r['speaker'] == 'AB'[k])), 's')
    print('centroid cosine A/B', round(float(c[0] @ c[1]), 3))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('design')
    d.add_argument('--model', required=True)
    d.add_argument('--instruct', required=True)
    d.add_argument('--text', required=True)
    d.add_argument('--lang', default='french')
    d.add_argument('--out', required=True)
    d.add_argument('--seeds', default='1,2,3,4')
    t = sub.add_parser('tts')
    t.add_argument('--model', required=True)
    t.add_argument('--jobs', required=True)
    al = sub.add_parser('align')
    al.add_argument('--jobs', required=True)
    al.add_argument('--model', default='base')
    al.add_argument('--output', required=True)
    q = sub.add_parser('qc')
    q.add_argument('--jobs', required=True)
    q.add_argument('--ref', required=True, help='voice to match: FILE or FILE:START-END')
    q.add_argument('--other', help='a different voice for contrast: FILE or FILE:START-END')
    q.add_argument('--model', default='small', help='faster-whisper model')
    q.add_argument('--tts-model', default='mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit')
    q.add_argument('--output', required=True)
    dz = sub.add_parser('diarize')
    dz.add_argument('--audio', required=True)
    dz.add_argument('--lang', default='fr')
    dz.add_argument('--model', default='base', help='faster-whisper model')
    dz.add_argument('--tts-model', default='mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit')
    dz.add_argument('--min-seconds', type=float, default=2.0)
    dz.add_argument('--output', required=True)
    a = p.parse_args()
    dict(design=design, tts=tts, align=align, qc=qc, diarize=diarize)[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
