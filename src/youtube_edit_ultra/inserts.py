"""Prepare short still-image inserts for the existing video/editorial pipeline."""

import json
import math
import os
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .catalogue import sha256
from .media import UltraError, require_space, run, validate_media
from .render import estimate_streamed_bytes
from .storage import guarded_command


def prepare_image_insert(source, output, *, duration, width=1920, height=1080, fps=30):
    source, output = Path(source).expanduser(), Path(output).expanduser()
    if not math.isfinite(duration) or not 0 < duration < 2:
        raise UltraError('Short still inserts require 0 < duration < 2 seconds')
    if any(type(v) is not int or v <= 0 for v in (width, height, fps)) or width % 2 or height % 2:
        raise UltraError('Positive FPS and positive even dimensions required')
    frames = round(duration * fps)
    if not frames or abs(duration * fps - frames) > 1e-6:
        raise UltraError('Still duration must be on the output frame grid')
    if source.is_symlink() or not source.is_file():
        raise UltraError('A regular local still image is required')
    source, output = source.resolve(), output.absolute()
    report_path = output.with_suffix('.insert.json')
    if output.suffix.lower() != '.mp4':
        raise UltraError('Insert output must be MP4')
    if any(p.exists() or p.is_symlink() for p in (output, report_path)):
        raise UltraError(f'Preserve existing insert or provenance: {output}')
    try:
        with Image.open(source) as im:
            if im.format not in ('PNG', 'JPEG', 'WEBP') or getattr(im, 'is_animated', False):
                raise UltraError('Single PNG, JPEG or WebP image required; use video for animation')
            im.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise UltraError(f'Invalid still image: {source}') from exc
    digest = sha256(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    estimate = estimate_streamed_bytes(duration)
    require_space(output.parent, estimate, 'still insert preparation')
    temporary = output.with_name(f'.{output.stem}-{uuid.uuid4().hex[:12]}.partial.mp4')
    vf = (f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
          f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p')
    run(guarded_command([
        'ffmpeg', '-nostdin', '-hide_banner', '-v', 'error', '-n',
        '-loop', '1', '-framerate', str(fps), '-i', str(source),
        '-vf', vf, '-frames:v', str(frames), '-an', '-c:v', 'libx264',
        '-preset', 'fast', '-b:v', '4000k', '-maxrate', '5000k', '-bufsize', '8000k',
        '-movflags', '+faststart', str(temporary)],
        need=estimate, path=output.parent, label='still insert preparation'))
    validation = validate_media(temporary, 'video', cache_dir=output.parent / '.ultra-validation')
    if abs(validation['duration'] - duration) > 1e-6 or sha256(source) != digest:
        raise UltraError(f'Insert duration or source changed; partial preserved: {temporary}')
    report = dict(source=str(source), source_sha256=digest, output=str(output),
                  output_sha256=validation['sha256'], duration=duration, frames=frames,
                  rights_verified=False, visual_review_completed=False, full_decode=True,
                  candidate_shot=dict(source=str(output), source_sha256=validation['sha256'],
                      safe_start=0, core_start=0, core_end=duration, safe_end=duration,
                      peak=None, label='insert still', kind='insert', quality=0,
                      provenance='candidate_still_insert', audio_intent='mute'))
    # Neither a prepared clip nor its candidate annotation grants rights or visual review.
    try:
        with report_path.open('x') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.link(temporary, output)
    except FileExistsError as exc:
        raise UltraError(f'Concurrent insert output; partial preserved: {temporary}') from exc
    temporary.unlink()
    return report


def insert_image_command(args):
    report = prepare_image_insert(args.image, args.output, duration=args.duration,
                                  width=args.width, height=args.height, fps=args.fps)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
