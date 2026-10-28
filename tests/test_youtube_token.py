"""OAuth persistence tests are local; no token or Google API request is used."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from youtube_edit_ultra.youtube import _write_private_token


def test_token_is_created_private_and_previous_contents_replaced(tmp_path):
    directory = tmp_path / "auth"
    token = directory / "token.json"
    directory.mkdir()
    token.write_text("old token", encoding="utf-8")
    if os.name == "posix":
        os.chmod(token, 0o644)
    _write_private_token(token, "synthetic new token")
    assert token.read_text(encoding="utf-8") == "synthetic new token"
    if os.name == "posix":
        assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert not list(directory.glob(".token-*.tmp"))


def test_failed_token_write_never_destroys_existing_credentials(tmp_path):
    token = tmp_path / "token.json"
    token.write_text("previous valid token", encoding="utf-8")
    with patch("youtube_edit_ultra.youtube.os.replace", side_effect=OSError("simulated failure")):
        with pytest.raises(OSError, match="simulated failure"):
            _write_private_token(token, "incomplete new token")
    assert token.read_text(encoding="utf-8") == "previous valid token"
    assert not list(tmp_path.glob(".token-*.tmp"))


@pytest.mark.skipif(os.name != "posix", reason="symlink behavior is POSIX-tested")
def test_token_symlink_is_replaced_without_following_it(tmp_path):
    original = tmp_path / "unrelated-private-file"
    original.write_text("do not overwrite", encoding="utf-8")
    token = tmp_path / "token.json"
    token.symlink_to(original)
    _write_private_token(token, "fresh synthetic token")
    assert original.read_text(encoding="utf-8") == "do not overwrite"
    assert not token.is_symlink()
    assert token.read_text(encoding="utf-8") == "fresh synthetic token"
