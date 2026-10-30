"""Use the installed reservation manager and delete only explicitly owned job files."""
from pathlib import Path
import sys

from .media import UltraError, require_space

GUARD_SCRIPT = Path.home() / 'Documents/Systeme/disk-guard/diskguard.py'


def guarded_command(command, *, need, path, label):
    path = Path(path).resolve()
    require_space(path, int(need), label)
    if GUARD_SCRIPT is not None and GUARD_SCRIPT.is_file():
        return [sys.executable, str(GUARD_SCRIPT), 'run', '--need', str(int(need)),
                '--label', label, '--path', str(path), '--', *map(str, command)]
    return list(map(str, command))


def cleanup_temporaries(job_dir, paths, *, verified, protected=()):
    if not verified:
        raise UltraError('Temporary cleanup requires a verified delivery')
    root = Path(job_dir).resolve()
    protected = {Path(p).resolve() for p in protected}
    checked = []
    for name in paths:
        path = Path(name)
        resolved = path.resolve()
        if (path.is_symlink() or resolved == root or not resolved.is_relative_to(root)
                or resolved in protected or not path.is_file()):
            raise UltraError(f'Not an owned temporary file: {path}')
        checked.append(path)
    for path in checked:
        path.unlink()
    return [str(p) for p in checked]
