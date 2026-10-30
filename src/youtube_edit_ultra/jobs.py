"""Resumable one-prompt jobs composed from the existing acquisition and editing APIs."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
import signal
from pathlib import Path
import subprocess
import sys
import time

from . import catalogue as cat
from .media import UltraError, check_binaries, probe, slug
from .spec import parse_request
from .storage import guarded_command, cleanup_temporaries


def now():
    return datetime.now(timezone.utc).isoformat()


class Job:
    def __init__(self, path, options=None):
        self.path = Path(path).expanduser().resolve()
        self.file = self.path / 'manifest.json'
        if self.file.exists():
            self.state = cat.read(self.file)
            if self.state.get('schema') != 1 or self.state.get('job_dir') != str(self.path):
                raise UltraError('Invalid job manifest or moved job; original paths must remain valid')
        elif options is not None:
            self.path.mkdir(parents=True, exist_ok=False)
            (self.path / '.ultra-ignore').touch()
            self.state = dict(schema=1, job_id=self.path.name, job_dir=str(self.path),
                              created_at=now(), status='PENDING', options=options, stages={})
            self.save()
        else:
            raise UltraError(f'Job manifest missing: {self.file}')

    def save(self):
        self.state['updated_at'] = now()
        cat.save(self.file, self.state)

    def stage(self, name, callback):
        saved = self.state['stages'].get(name, {})
        if saved.get('status') == 'COMPLETE':
            for path, digest in saved['hashes'].items():
                if not Path(path).is_file() or cat.sha256(Path(path)) != digest:
                    raise UltraError(f'Changed or missing checkpoint artifact: {path}; start a new job')
            print(f'[{name}] cached', flush=True)
            return saved['result']
        for group in saved.get('process_groups', []):
            try:
                os.killpg(group, 0)
            except ProcessLookupError:
                continue
            except PermissionError:
                raise UltraError(f'Cannot establish that previous {name} process stopped') from None
            raise UltraError(f'Previous {name} process group {group} is still running; no duplicate started')
        record = dict(status='RUNNING', started_at=now(), attempts=saved.get('attempts', 0) + 1)
        self.state['stages'][name] = record
        self.state['status'] = 'RUNNING'
        self.state.pop('error', None)
        self.save()
        self.current_stage = name
        print(f'[{name}] running', flush=True)
        try:
            result = callback()
            hashes = {str(Path(p).resolve()): cat.sha256(Path(p)) for p in result.get('artifacts', [])}
            record.update(status='COMPLETE', finished_at=now(), result=result, hashes=hashes)
            self.save()
            return result
        except BaseException as exc:
            record.update(status='INTERRUPTED' if isinstance(exc, (KeyboardInterrupt, SystemExit))
                          else 'BLOCKED', finished_at=now(), error=str(exc), error_type=type(exc).__name__)
            self.state.update(status=record['status'], error=str(exc))
            self.save()
            raise


def _run(command, log, *, need=0, path=None, label='job', job=None):
    if need:
        command = guarded_command(command, need=need, path=path or log.parent, label=label)
    with log.open('a') as output:
        child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        if job:
            job.state['stages'][job.current_stage]['process_groups'] = [child.pid]
            job.save()
        try:
            code = child.wait()
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL);child.wait()
            raise
    if code:
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size - 2500))
            tail = stream.read().decode(errors='replace')
        raise UltraError(f'{label} failed ({code}); {log}\n{tail}')


def _lock(stack, path):
    handle = stack.enter_context(path.open('a'))
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise UltraError(f'Another job owns {path.name}; resume when it finishes') from None


def _resources(job, args, folder):
    from .produce import locked
    if locked(args, folder, output=job.path, prepare_only=True):
        report = cat.read(job.path / 'production_report.json')
        raise UltraError('; '.join(report['blockers']))
    candidates = cat.read(job.path / 'source_candidates.json')
    return dict(artifacts=[str(job.path / n) for n in ('project.json', 'source_candidates.json')],
                assets=[dict(path=r['path'], sha256=r['sha256'], kind=r['kind'])
                        for r in candidates['videos'] + candidates['music']])


def _check_assets(resources, state, mode, job_id=None):
    for asset in resources['assets']:
        p = Path(asset['path'])
        row = state['media'].get(str(p), {})
        if (not p.is_file() or cat.sha256(p) != asset['sha256']
                or row.get('sha256') != asset['sha256'] or not cat.permitted(state, row, mode=mode)):
            raise UltraError(f'Input missing, changed or no longer permitted: {p}; start a new job')
        if asset['kind'] == 'audio' and any(
                used.get('job_id') != job_id and (used.get('sha256') == asset['sha256']
                or used.get('family') == cat.family(row['title'])) for used in state['used']):
            raise UltraError(f'Music already used by another job since selection: {p}; start a new job')


def _review(job, args, resources):
    from .events import from_json
    from .vision import analyze
    from .duplicates import deduplicate_shots
    accepted = {'annotation', 'visual_review', 'visual_sample_review', 'human_review'}
    shots, unreviewed, evidence_files = [], [], []
    for asset in resources['assets']:
        if asset['kind'] != 'video':
            continue
        source = Path(asset['path'])
        annotation, shot_file = source.with_suffix('.actions.json'), source.with_suffix('.shots.json')
        if shot_file.is_file():
            values = cat.read(shot_file)
            if not isinstance(values, list):
                raise UltraError(f'Shot sidecar must contain a list: {shot_file}')
            for value in values:
                row = dict(value, source=str(source))
                if row.get('source_sha256', asset['sha256']) != asset['sha256']:
                    raise UltraError(f'Annotation source hash mismatch: {shot_file}')
                if row.get('provenance') not in accepted:
                    unreviewed.append(dict(source=str(source), reason='unverified shot provenance'))
                else:
                    shots.append(row)
            evidence_files.append(str(shot_file))
        elif annotation.is_file():
            raw = cat.read(annotation)
            rows = raw.get('events', []) if isinstance(raw, dict) else raw
            envelope_provenance = raw.get('provenance') if isinstance(raw, dict) else None
            if (not isinstance(rows, list) or not rows
                    or any(not isinstance(r, dict) or r.get('provenance', envelope_provenance) not in accepted
                           for r in rows)):
                unreviewed.append(dict(source=str(source), reason='Missing explicit annotation provenance'))
                continue
            actions = from_json(annotation, source, probe(source)['duration'], args.request['sport'])
            for raw_row, action in zip(rows, actions, strict=True):
                if action.provenance not in accepted:
                    unreviewed.append(dict(source=str(source), reason=action.provenance))
                    continue
                shots.append(dict(source=str(source), safe_start=action.start, core_start=action.start,
                                  core_end=action.end, safe_end=action.end, peak=action.peak,
                                  quality=action.confidence, label=action.label,
                                  provenance=action.provenance, source_sha256=asset['sha256'],
                                  **{k: raw_row[k] for k in ('kind', 'audio_intent') if k in raw_row}))
            evidence_files.append(str(annotation))
        else:
            actions, stats = analyze(source, job.path / 'cache/vision', args.request['sport'])
            candidate_file = job.path / 'review' / (asset['sha256'][:16] + '.candidates.json')
            cat.save(candidate_file, dict(source=str(source), source_sha256=asset['sha256'],
                                         candidates=[a.as_dict() for a in actions], analysis=stats,
                                         status='CANDIDATES_REQUIRE_REVIEW'))
            unreviewed.append(dict(source=str(source), reason='No documented action boundaries',
                                   candidates=str(candidate_file)))
    if not shots:
        cat.save(job.path / 'review_required.json', dict(status='ACTION_REVIEW_REQUIRED', sources=unreviewed))
        raise UltraError('ACTION_REVIEW_REQUIRED: source motion cannot certify complete combinations/KO; '
                         'candidates and missing annotations saved in review_required.json')
    retained, duplicate_report = deduplicate_shots(shots, job.path / 'cache/duplicates')
    cat.save(job.path / 'shot_duplicates.json', duplicate_report)
    if not duplicate_report.get('complete', True):
        raise UltraError('Duplicate candidate scan incomplete; inspect its report before delivery')
    cat.save(job.path / 'shots.json', retained)
    # This generated manifest is separate from the acquisition checkpoint.
    manifest = cat.read(job.path / 'project.json')
    manifest.update(editorial_shots=str(job.path / 'shots.json'), source_volume=.07, music_volume=1.)
    intro, outro = context_edits(retained, args.request['duration_seconds'], args.fps)
    for role, edits in [('intro', intro), ('outro', outro)]:
        if edits:
            path = job.path / f'{role}.json';cat.save(path, edits)
            manifest[f'{role}_edits'] = str(path)
            evidence_files.append(str(path))
    manifest['sources'] = [s for s in manifest['sources']
                           if s['path'] in {row['source'] for row in retained}]
    cat.save(job.path / 'edit_project.json', manifest)
    return dict(artifacts=[str(job.path / n) for n in ('shots.json', 'shot_duplicates.json', 'edit_project.json')]
                + evidence_files, ignored_unreviewed_sources=unreviewed, semantic_completeness_guaranteed=False)


def context_edits(shots, target, fps):
    """Use only explicitly tagged reviewed context; never invent walkouts or celebrations."""
    selected = []
    for role in ('intro', 'outro'):
        budget = min(12., target * .1)
        candidates = sorted((s for s in shots if s.get('kind') == role),
                            key=lambda s: s.get('quality', 0), reverse=True)
        edit = None
        for shot in candidates:
            start = math.ceil(shot['safe_start'] * fps - 1e-7) / fps
            end = min(math.floor(shot['safe_end'] * fps + 1e-7) / fps,
                      start + math.floor(budget * fps) / fps)
            if start > shot['core_start'] + 1e-6 or end < shot['core_end'] - 1e-6 or end <= start:
                continue
            at = 0 if role == 'intro' else target - (end - start)
            edit = dict(source=shot['source'], source_start=start, source_end=end,
                        timeline_start=at, timeline_end=at + end - start, source_peak=shot.get('peak'),
                        label=shot.get('label', role), provenance=shot['provenance'],
                        confidence=shot.get('quality', 1), audio_intent=shot.get('audio_intent', 'auto'))
            break
        selected.append([edit] if edit else [])
    return selected


def _validate_sources(job, resources):
    from .media import validate_media
    reports = [validate_media(Path(a['path']), a['kind'], cache_dir=job.path / 'cache/source-decode')
               for a in resources['assets']]
    path = job.path / 'source_integrity.json'
    cat.save(path, reports)
    return dict(artifacts=[str(path)], files=len(reports))


def _plan(job, args, rendered):
    command = [sys.executable, '-m', 'youtube_edit_ultra.cli', '--no-banner', 'create', args.prompt,
               '--spec', str(job.path / 'edit_project.json'), '--plan-only', '--publish', 'none',
               '--width', str(args.width), '--height', str(args.height), '--fps', str(args.fps)]
    need = int(args.request['duration_seconds'] * 48000 * 4 + 10_000_000)
    _run(command, job.path / 'plan.log', need=need, path=job.path, label='soundtrack and plan', job=job)
    recipe = cat.read(rendered / 'render_inputs.json')
    return dict(artifacts=[str(rendered / n) for n in ('edit_plan.json', 'action_integrity_report.json',
                                                      'render_inputs.json', 'source_report.json')]
                + [recipe['soundtrack']], soundtrack=recipe['soundtrack'])


def _render(job, args, rendered):
    from .render import estimate_streamed_bytes
    # The worker publishes only completed outputs. A pre-checkpoint file is never assumed valid.
    raw = rendered / 'rendered.mp4'
    if raw.exists():
        previous = cat.read(rendered / 'render_report.json', {})
        inputs = {n: cat.sha256(rendered / n) for n in ('edit_plan.json', 'render_inputs.json')}
        if previous.get('sha256') == cat.sha256(raw) and previous.get('inputs_sha256') == inputs:
            return dict(artifacts=[str(raw), str(rendered / 'render_report.json')], video=str(raw))
        raw.rename(raw.with_name(f'rendered.unverified-{time.time_ns()}.mp4'))
    _run([sys.executable, '-m', 'youtube_edit_ultra.jobs', '_render', str(rendered)],
         job.path / 'render.log', need=estimate_streamed_bytes(args.request['duration_seconds']),
         path=rendered, label='video render', job=job)
    return dict(artifacts=[str(raw), str(rendered / 'render_report.json')], video=str(raw))


def _quality(job, args, rendered, video):
    # Separate process gives the installed guard ownership of correction disk reservations.
    _run([sys.executable, '-m', 'youtube_edit_ultra.jobs', '_quality', str(job.path)],
         job.path / 'quality.log', path=rendered, label='quality', job=job)
    result = cat.read(rendered / 'verification_report.json')
    return dict(artifacts=[result['output'], str(rendered / 'verification_report.json')],
                video=result['output'], sha256=result['sha256'])


def _deliver(job, args, rendered, result):
    from .cli import _thumbnail_and_metadata
    from .planner import Edit
    from .spec import Settings
    from .thumbnail import create_storyboard
    src = Path(result['video'])
    dst = rendered / f"{slug(args.request['athlete'])}-{slug(args.request['style'])}-{round(args.request['duration_seconds'])}s.mp4"
    if dst.exists():
        if cat.sha256(dst) != result['sha256']:
            raise UltraError('Existing delivery differs; preserved: ' + str(dst))
    else:
        os.link(src, dst)
    if cat.sha256(dst) != result['sha256']:
        raise UltraError('Delivery checksum mismatch')
    edits = [Edit(**row) for row in cat.read(rendered / 'edit_plan.json')]
    music = [Path(p) for p in cat.read(rendered / 'source_report.json')['music']]
    settings = Settings(**args.request, output=rendered, library=job.path / 'library',
                        width=args.width, height=args.height, fps=args.fps)
    _thumbnail_and_metadata(settings, edits, music)
    create_storyboard(edits, rendered / 'storyboard.jpg')
    catalogue = cat.read(Path(args.state_dir).expanduser() / 'catalogue.json')
    used_paths = {e.source for e in edits} | {str(p) for p in music}
    rights = []
    for path in sorted(used_paths):
        row = catalogue['media'][path]
        if not cat.permitted(catalogue, row, mode=args.mode):
            raise UltraError('Permission no longer valid at delivery: ' + path)
        rights.append(dict(path=path, sha256=row['sha256'], url=row.get('url'),
                           permission=catalogue['permissions'][row['sha256']]))
    cat.save(rendered / 'rights_report.json', dict(mode=args.mode, sources=rights,
                                                 independent_ownership_verification=False))
    credits = list(dict.fromkeys(r['permission']['credit'] for r in rights if r['permission'].get('credit')))
    metadata_path = rendered / 'youtube_metadata.json'
    metadata = cat.read(metadata_path)
    metadata['source_credits'] = credits
    if credits:
        metadata['description'] += '\n\nSources et licences :\n' + '\n'.join(credits)
    cat.save(metadata_path, metadata)
    delivery = dict(video=str(dst), sha256=result['sha256'], bytes=dst.stat().st_size,
                    duration=args.request['duration_seconds'], publication_performed=False,
                    rights_mode=args.mode, monetizable=False,
                    rights_status='documented commercial permissions' if args.mode == 'commercial'
                    else 'personal use only; distribution may trigger claims',
                    continuous_human_viewing=False)
    if args.desktop:
        desktop = Path.home() / 'Desktop' / dst.name
        if desktop.exists():
            if cat.sha256(desktop) != result['sha256']:
                raise UltraError('Existing Desktop file differs; preserved: ' + str(desktop))
        elif sys.platform == 'darwin':
            subprocess.run(['cp', '-c', '-n', str(dst), str(desktop)], check=True)
        else:
            os.link(dst, desktop)
        if cat.sha256(desktop) != result['sha256']:
            raise UltraError('Desktop copy checksum mismatch')
        delivery['desktop'] = str(desktop)
    path = rendered / 'delivery.json';cat.save(path, delivery)
    return dict(artifacts=[str(dst), str(path), str(rendered / 'thumbnail.jpg'),
                           str(rendered / 'youtube_metadata.json'), str(rendered / 'storyboard.jpg'),
                           str(rendered / 'rights_report.json')],
                **delivery)


def _consume(job, folder, rendered):
    from .music import audio_profile
    state = cat.read(folder / 'catalogue.json')
    if any(p.get('job_id') == job.state['job_id'] for p in state['projects']):
        tracklist = rendered / 'music_tracklist.json'
        if (not tracklist.is_file() or job.state.get('tracklist_sha256', cat.sha256(tracklist)) != cat.sha256(tracklist)):
            raise UltraError('Delivered tracklist missing or changed; catalogue usage preserved')
        job.state['tracklist_sha256'] = cat.sha256(tracklist)
        return
    candidates = cat.read(job.path / 'source_candidates.json')
    actual = cat.read(rendered / 'source_report.json')['music']
    by_path = {r['path']: r for r in candidates['music']}
    _check_assets({'assets': [dict(path=p, sha256=by_path[p]['sha256'], kind='audio') for p in actual]},
                  state, job.state['options']['mode'], job.state['job_id'])
    tracks, offset = [], 0.
    for path in actual:
        row = by_path[path]
        profile = audio_profile(Path(row['path']), cache_dir=job.path / 'cache/audio-profiles')
        used = min(profile['usable_duration'], job.state['options']['request']['duration_seconds'] - offset)
        track = dict(row, timeline_start=offset, timeline_end=offset + used,
                     source_start=profile['source_start'], used_seconds=used,
                     permission=state['permissions'][row['sha256']])
        tracks.append(track);offset += used - .7
        state['used'].append(dict(title=row['title'], artist=row.get('artist', ''),
                                 family=cat.family(row['title']), sha256=row['sha256'],
                                 job_id=job.state['job_id'], evidence=job.state['delivery']['video']))
    cat.save(rendered / 'music_tracklist.json', dict(tracks=tracks, crossfade_seconds=.7))
    job.state['tracklist_sha256'] = cat.sha256(rendered / 'music_tracklist.json')
    state['projects'].append(dict(job_id=job.state['job_id'], path=str(rendered),
                                  sha256=job.state['delivery']['sha256'], status='COMPLETE_TECHNICAL'))
    cat.save(folder / 'catalogue.json', state)


def execute(args):
    options = vars(args).copy();options.pop('func', None)
    if args.command == 'resume':
        job = Job(args.job)
        options = job.state['options']
        args = argparse.Namespace(**options)
    else:
        args.request = parse_request(args.prompt)
        from .spec import Settings
        Settings(**args.request, output=Path(args.output_dir), library=Path(args.state_dir),
                 width=args.width, height=args.height, fps=args.fps)
        options['request'] = args.request
        key = {k: options[k] for k in ('request', 'mode', 'width', 'height', 'fps', 'roots', 'state_dir',
                                     'playlist', 'offline', 'desktop')}
        key['output_dir'] = str(Path(args.output_dir).expanduser().resolve())
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:12]
        name = f"{slug(args.request['athlete'])}-{digest}"
        if args.new_job:name += '-' + str(time.time_ns())
        job = Job(Path(args.output_dir).expanduser() / name, options)
    folder = Path(args.state_dir).expanduser().resolve();folder.mkdir(parents=True, exist_ok=True)
    rendered = job.path / f"{slug(args.request['athlete'])}-{round(args.request['duration_seconds'])}s"
    owns_lock = False
    stack = ExitStack()
    try:
        check_binaries()
        _lock(stack, folder / 'catalogue.lock');_lock(stack, job.path / 'job.lock')
        owns_lock = True
        job = Job(job.path)  # Reload after acquiring locks; another process may have advanced it.
        if job.state.get('delivery'):
            delivery = job.state['delivery']
            if not Path(delivery['video']).is_file() or cat.sha256(Path(delivery['video'])) != delivery['sha256']:
                raise UltraError('Verified delivery missing or changed; original checkpoint preserved')
            for stage in ('quality', 'delivery'):
                if job.state['stages'].get(stage, {}).get('status') != 'COMPLETE':
                    raise UltraError('Incomplete delivery checkpoint: ' + stage)
                job.stage(stage, lambda: None)
            _consume(job, folder, rendered)
            job.state.pop('error', None)
            job.state['status'] = 'COMPLETE_TECHNICAL';job.save()
            print('Existing verified delivery: ' + delivery['video'], flush=True)
            return 0
        resources = job.stage('resources', lambda: _resources(job, args, folder))
        _check_assets(resources, cat.read(folder / 'catalogue.json'), args.mode, job.state['job_id'])
        job.stage('source_validation', lambda: _validate_sources(job, resources))
        job.stage('action_review', lambda: _review(job, args, resources))
        job.stage('plan', lambda: _plan(job, args, rendered))
        raw = job.stage('render', lambda: _render(job, args, rendered))
        final = job.stage('quality', lambda: _quality(job, args, rendered, raw['video']))
        delivery = job.stage('delivery', lambda: _deliver(job, args, rendered, final))
        job.state['delivery'] = delivery;job.save()
        _consume(job, folder, rendered)
        # Only this job's raw render can be retired; external inputs and final delivery remain protected.
        temp = Path(raw['video'])
        removed = cleanup_temporaries(job.path, [temp], verified=True,
                                       protected=[delivery['video'], final['video']]) if temp != Path(final['video']) else []
        job.state.update(status='COMPLETE_TECHNICAL', cleaned_temporaries=removed);job.save()
        print('Verified delivery: ' + delivery['video'], flush=True)
        return 0
    except KeyboardInterrupt:
        if owns_lock:
            job.state.update(status='INTERRUPTED', error='Interrupted; resume this job');job.save()
        return 130
    except Exception as exc:
        if owns_lock:
            job.state.update(status='BLOCKED', error=str(exc), error_type=type(exc).__name__);job.save()
        print(f'Blocked: {exc}\nResume: ueu resume "{job.path}"', file=sys.stderr, flush=True)
        return 2
    finally:
        try:
            if owns_lock:
                delivery = job.state.get('delivery', {})
                (job.path / 'REPORT.txt').write_text(
                    f"Status: {job.state['status']}\nPrompt: {args.prompt}\n"
                    f"Video: {delivery.get('video', 'not delivered')}\n"
                    f"Blocker: {job.state.get('error', 'none')}\n"
                    'Automated checks are not continuous human viewing or proof of every sports action.\n'
                    f"Resume: ueu resume \"{job.path}\"\n")
        finally:
            stack.close()


def _worker(command, path):
    from .planner import Edit
    from .render import render_streamed
    from .quality import finalize_output
    if command == '_render':
        rendered = Path(path)
        recipe = cat.read(rendered / 'render_inputs.json')
        edits = [Edit(**row) for row in cat.read(rendered / 'edit_plan.json')]
        report = render_streamed(edits, recipe.pop('soundtrack'), rendered / 'rendered.mp4',
                                 **{k: v for k, v in recipe.items() if k != 'editorial'})
        report['sha256'] = cat.sha256(rendered / 'rendered.mp4')
        report['inputs_sha256'] = {n: cat.sha256(rendered / n) for n in ('edit_plan.json', 'render_inputs.json')}
        cat.save(rendered / 'render_report.json', report)
    else:
        job = Job(path);options = job.state['options'];request = options['request']
        rendered = job.path / f"{slug(request['athlete'])}-{round(request['duration_seconds'])}s"
        raw = rendered / 'rendered.mp4'
        # Normal QC writes only logs. Repair itself checks free space before allocating a new MP4.
        report = finalize_output(raw, request['duration_seconds'], job_dir=job.path,
                                 width=options['width'], height=options['height'], fps=options['fps'])
        from .duplicates import check_video_duplicates
        duplicates = check_video_duplicates(Path(report['output']), cat.read(rendered / 'edit_plan.json'),
                                             job.path / 'cache/final-duplicates')
        cat.save(rendered / 'duplicate_report.json', duplicates)
        if duplicates.get('candidates') or not duplicates.get('complete', True):
            raise UltraError('Repeated or incompletely checked action frames; see duplicate_report.json')
        report['visual_duplicates'] = duplicates
        integrity = cat.read(rendered / 'action_integrity_report.json')
        if integrity.get('violations') or not integrity['all_selected_event_windows_preserved']:
            raise UltraError('Protected action core violation')
        report['action_integrity'] = integrity
        cat.save(rendered / 'verification_report.json', report)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {'_render', '_quality'}:
        return _worker(argv[0], argv[1])
    if argv and argv[0] not in {'create', 'resume', 'status', '-h', '--help'}:
        from .cli import main as legacy
        return legacy(argv)
    parser = argparse.ArgumentParser(prog='ueu', description='Athlete + music style + duration → verified MP4 or explicit blocker')
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('prompt')
    create.add_argument('--mode', choices=['personal', 'commercial'], default='personal')
    create.add_argument('--state-dir', default=str(Path.home() / '.local/share/youtube-edit-ultra'))
    create.add_argument('--output-dir', default='output/jobs')
    create.add_argument('--root', dest='roots', action='append')
    create.add_argument('--playlist')
    create.add_argument('--offline', action='store_true')
    create.add_argument('--desktop', action='store_true')
    create.add_argument('--new-job', action='store_true')
    create.add_argument('--width', type=int, default=1920)
    create.add_argument('--height', type=int, default=1080)
    create.add_argument('--fps', type=int, default=30)
    create.set_defaults(strict_actions=True, semantic_model=None)
    resume = commands.add_parser('resume');resume.add_argument('job')
    status = commands.add_parser('status');status.add_argument('job')
    args = parser.parse_args(argv)
    try:
        if args.command == 'status':
            print(json.dumps(Job(args.job).state, indent=2, ensure_ascii=False));return 0
        return execute(args)
    except (UltraError, OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr);return 2


if __name__ == '__main__':
    sys.exit(main())
