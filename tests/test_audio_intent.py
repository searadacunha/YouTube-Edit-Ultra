import subprocess

import numpy as np
import pytest

from youtube_edit_ultra.editorial import plan_editorial
from youtube_edit_ultra.media import UltraError
from youtube_edit_ultra.planner import Edit
from youtube_edit_ultra.render import render_edits, render_streamed


def edit(source, start, end, label, intent='auto'):
    return Edit(str(source), start, end, start, end, label, None, 'visual_review', 1,
                audio_intent=intent)


def test_audio_intent_is_additive_validated_and_propagated():
    old = dict(source='source', source_start=0, source_end=2, timeline_start=0,
               timeline_end=2, label='action', source_peak=None, provenance='annotation', confidence=1)
    assert Edit(**old).audio_intent == 'auto'
    with pytest.raises(UltraError, match='audio_intent'):
        Edit(**old, audio_intent='guessed_speech')
    shot = dict(source='source', safe_start=0, core_start=0, core_end=2, safe_end=2,
                label='announcer', audio_intent='featured')
    structure = [dict(start=0, end=2, beats=[0, 1], features={'wave': [.5, .5]})]
    assert plan_editorial([shot], structure, 2)[0].audio_intent == 'featured'


def test_legacy_renderer_cannot_silently_ignore_explicit_intent(tmp_path):
    with pytest.raises(UltraError, match='streaming renderer'):
        render_edits([edit('unused', 0, 2, 'action', 'mute')], tmp_path/'music',
                     tmp_path/'output.mp4', tmp_path/'cache')


def amplitude(pcm, at, frequency, duration=.4):
    values = pcm[round(at*48000):round((at+duration)*48000)]
    phase = np.arange(len(values)) * (2*np.pi*frequency/48000)
    return 2*abs(np.sum(values*np.exp(-1j*phase)))/len(values)


def test_featured_intro_preserves_audio_and_ducks_music_smoothly(tmp_path):
    source, music, out = (tmp_path/name for name in ('source.mp4', 'music.wav', 'final.mp4'))
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=160x90:rate=30:duration=10', '-f', 'lavfi', '-i',
                    'sine=frequency=1000:sample_rate=48000:duration=10', '-c:v', 'libx264',
                    '-c:a', 'aac', str(source)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=48000:duration=10', str(music)], check=True)
    edits = [edit(source, 0, 2, 'intro'), edit(source, 2, 4, 'intro announcer', 'featured'),
             edit(source, 4, 6, 'action'), edit(source, 6, 8, 'intro', 'ambience'),
             edit(source, 8, 10, 'action', 'mute')]
    render_streamed(edits, music, out, width=160, height=90, video_kbps=200)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(out), '-vn', '-ac', '1',
                              '-ar', '48000', '-f', 'f32le', '-'], check=True, capture_output=True)
    pcm = np.frombuffer(decoded.stdout, np.float32)
    plain = amplitude(pcm, .5, 440)
    ducked = amplitude(pcm, 2.5, 440)
    assert -7.5 < 20*np.log10(ducked/plain) < -6.5
    assert amplitude(pcm, .5, 1000) < .001  # legacy intro stays muted
    assert amplitude(pcm, 8.5, 1000) < .001  # explicit mute wins over action label
    assert amplitude(pcm, 2.5, 1000) > 4*amplitude(pcm, 4.5, 1000)
    assert .85 < amplitude(pcm, 6.5, 1000)/amplitude(pcm, 4.5, 1000) < 1.15
    assert abs(amplitude(pcm, 4.5, 440)/plain - 1) < .03
    assert np.max(np.abs(pcm)) < .9
    # A 10ms source ramp and smooth music envelope do not produce a boundary impulse.
    for boundary in (2, 4, 6):
        cut = pcm[round((boundary-.02)*48000):round((boundary+.02)*48000)]
        assert np.max(np.abs(np.diff(cut))) < .06
