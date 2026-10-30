"""Exercise the publisher's gates with simulated GitHub/git transport, no remote writes."""
from pathlib import Path
import os
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('dirty,history,expected', [
    (' M private.txt', '', 2),
    ('', 'JOURNAL_AGENTS.md', 2),
    ('', 'output/old.mp4', 2),
    ('', 'src/youtube_edit_ultra/jobs.py', 0),
])
def test_publisher_never_stages_or_pushes_private_history(tmp_path, dirty, history, expected):
    scripts = tmp_path / 'scripts';scripts.mkdir()
    shutil.copyfile(Path(__file__).parents[1] / 'scripts/publish_github.sh', scripts / 'publish.sh')
    bins = tmp_path / 'bin';bins.mkdir()
    gh = bins / 'gh';gh.write_text('#!/bin/sh\nexit 0\n');gh.chmod(0o755)
    git = bins / 'git'
    git.write_text('''#!/bin/sh
case "$1" in
  rev-parse) echo .git ;;
  remote) echo https://github.com/searadacunha/YouTube-Edit-Ultra.git ;;
  status) printf '%s' "$TEST_DIRTY" ;;
  fetch|merge-base|diff) exit 0 ;;
  log) printf '%s\\n' "$TEST_HISTORY" ;;
  push) touch "$TEST_PUSHED" ;;
  *) echo "Unexpected git operation: $1" >&2; exit 99 ;;
esac
''');git.chmod(0o755)
    pushed = tmp_path / 'pushed'
    env = dict(os.environ, PATH=str(bins) + os.pathsep + os.environ['PATH'],
               TEST_DIRTY=dirty, TEST_HISTORY=history, TEST_PUSHED=str(pushed))
    cp = subprocess.run(['bash', str(scripts / 'publish.sh')], env=env, capture_output=True, text=True)
    assert cp.returncode == expected, cp.stderr
    assert pushed.exists() == (expected == 0)
