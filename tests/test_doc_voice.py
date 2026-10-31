import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('doc_voice', Path(__file__).parents[1] / 'scripts/doc_voice.py')
dv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dv)  # pure helpers only: MLX and faster-whisper are imported inside the commands


def test_asr_match_ignores_case_and_punctuation_and_counts_missing_words():
    assert dv.asr_match('Canelo, 51 por ciento.', 'canelo 51 por ciento') == 1
    assert dv.asr_match('doce rounds y nada más', 'dos rounds y nada más') == 0.8


def test_negation_dropped_by_the_voice_is_visible():
    script = "Il n'a jamais perdu, ce n'est pas un hasard."
    assert dv.negations(script, 'fr') == 4
    assert dv.negations('Il a perdu, ce est un hasard.', 'fr') == 0
    assert dv.negations('Mbili não perdeu nunca', 'pt') == 2
    assert dv.negations("He didn't lose. Not once.", 'en') == 2


def test_two_speakers_labels_the_first_voice_zero():
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=8), rng.normal(size=8)
    E = np.stack([a + rng.normal(scale=.05, size=8) for _ in range(3)] + [b + rng.normal(scale=.05, size=8) for _ in range(4)])
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    lab, c = dv.two_speakers(E)
    assert lab.tolist() == [0, 0, 0, 1, 1, 1, 1]
    assert np.allclose([np.linalg.norm(x) for x in c], 1)


def test_reference_window_syntax():
    assert dv._ref('voice_ref/ref.m4a:133.9-151') == ('voice_ref/ref.m4a', (133.9, 151.0))
    assert dv._ref('voice_ref/ref.wav') == ('voice_ref/ref.wav', None)
