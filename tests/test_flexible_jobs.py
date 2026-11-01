"""Opt-in flexibility must not mislabel heuristic footage or silently grant online rights."""
from argparse import Namespace
from pathlib import Path

import pytest

from youtube_edit_ultra import catalogue, duplicates, jobs, vision
from youtube_edit_ultra.events import Action
from youtube_edit_ultra.media import UltraError


def test_auto_actions_keep_heuristic_provenance(tmp_path, monkeypatch):
    source = tmp_path / "Canelo Alvarez clip.mp4"
    source.write_bytes(b"synthetic marker; analyze is stubbed")
    asset = {"path": str(source), "sha256": "a" * 64, "kind": "video"}
    candidate = Action(str(source), 1., 2., 4., "boxing",
                       "motion_candidate", .25, "heuristic")
    monkeypatch.setattr(vision, "analyze", lambda *a, **kw: ([candidate], {"sampled_frames": 12}))
    monkeypatch.setattr(duplicates, "deduplicate_shots",
                        lambda shots, cache: (shots, {"complete": True}))
    args = Namespace(request={"sport": "boxing", "duration_seconds": 6}, fps=30,
                     auto_actions=True)
    job = jobs.Job(tmp_path / "job-auto", {"prompt": "test"})
    catalogue.save(job.path / "project.json", {"sources": [{"path": str(source)}]})
    result = jobs._review(job, args, {"assets": [asset]})
    assert result["automatic_candidates_used"] == 1
    assert result["action_review_status"] == "UNVERIFIED_AUTOMATIC"
    [shot] = catalogue.read(job.path / "shots.json")
    assert shot["provenance"] == "heuristic"
    assert shot["label"] == "motion_candidate"
    assert shot["core_start"] == shot["safe_start"] == 1
    assert shot["core_end"] == shot["safe_end"] == 4
    assert not result["semantic_completeness_guaranteed"]
    assert catalogue.read(job.path / "review" / ("a" * 16 + ".candidates.json"))["status"] == "AUTOMATIC_UNVERIFIED"

    strict_job = jobs.Job(tmp_path / "job-strict", {"prompt": "test"})
    catalogue.save(strict_job.path / "project.json", {"sources": [{"path": str(source)}]})
    args.auto_actions = False
    with pytest.raises(UltraError, match="ACTION_REVIEW_REQUIRED"):
        jobs._review(strict_job, args, {"assets": [asset]})


def test_automatic_action_flags_are_not_implicit(tmp_path):
    job = jobs.Job(tmp_path / "checkpoint", {"prompt": "test", "auto_actions": False})
    assert not job.state["options"]["auto_actions"]
