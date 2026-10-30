import pytest

from youtube_edit_ultra.jobs import Job
from youtube_edit_ultra.media import UltraError


def test_completed_stage_reused_after_interrupt(tmp_path):
    job = Job(tmp_path / 'job', {'prompt': 'Crawford rnb 6s'})
    artifact = job.path / 'source.json'
    calls = []
    def first():
        calls.append('first');artifact.write_text('evidence')
        return {'artifacts': [str(artifact)], 'result': 42}
    assert job.stage('sources', first)['result'] == 42
    def interruption():
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):job.stage('render', interruption)
    resumed = Job(job.path)
    assert resumed.state['stages']['render']['status'] == 'INTERRUPTED'
    assert resumed.stage('sources', first)['result'] == 42
    assert calls == ['first']
    assert resumed.stage('render', lambda: {'artifacts': [], 'result': 'done'})['result'] == 'done'


def test_mutated_checkpoint_is_not_silently_accepted(tmp_path):
    job = Job(tmp_path / 'job', {'prompt': 'Crawford rnb 6s'})
    p = job.path / 'data.json';p.write_text('first')
    job.stage('prepare', lambda: {'artifacts': [str(p)]})
    p.write_text('tampered')
    with pytest.raises(UltraError, match='checkpoint'):
        Job(job.path).stage('prepare', lambda: pytest.fail('must not blindly reuse/rewrite'))


def test_failure_persists_before_delivery(tmp_path):
    job = Job(tmp_path / 'job', {'prompt': 'Crawford rnb 6s'})
    def fail():raise UltraError('No licensed audio')
    with pytest.raises(UltraError):job.stage('sources', fail)
    state = Job(job.path).state
    assert state['status'] == 'BLOCKED'
    assert state['stages']['sources']['error'] == 'No licensed audio'
    assert not state.get('delivery')


def test_context_preserves_complete_core_and_audio_intent():
    from youtube_edit_ultra.jobs import context_edits
    shots = [dict(source='fixture', safe_start=0, core_start=.2, core_end=1.8,
                  safe_end=2, peak=1, quality=1, kind='intro', provenance='visual_review',
                  audio_intent='featured'),
             dict(source='fixture', safe_start=5, core_start=5.2, core_end=6.8,
                  safe_end=7, peak=6, quality=1, kind='outro', provenance='visual_review')]
    intro, outro = context_edits(shots, 30, 30)
    assert intro[0]['audio_intent'] == 'featured' and intro[0]['source_end'] == 2
    assert outro[0]['timeline_end'] == 30
    assert context_edits(shots, 10, 30) == [[], []]  # Cannot fit whole cores in context budget.
