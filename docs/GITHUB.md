# Publish reviewed code to the configured GitHub repository

The repository is public. Keep footage, music, OAuth credentials, local production
manifests, private journals and licence documents out of **every outgoing commit**,
not just the final working tree. `.gitignore` does not remove tracked history.

Review the diff, run `python -m pytest` and `ruff check src tests --select E9,F`,
then stage explicit public paths and commit them. The helper requires an existing,
authenticated `gh`, a clean checkout and the intended `origin`:

```bash
./scripts/publish_github.sh
```

It fetches the remote and pushes reviewed commits to `main` only when that is a
fast-forward. It does not stage files, initialize a repository, create a public
repository, rewrite history or override a failed check. `GITHUB_OWNER` and
`GITHUB_REPO` can select another already configured repository.

The path denylist is a safeguard, not a complete secret scanner. Review the actual
patch and outgoing history. If local-only commits contain private production
notes, retain that local branch and prepare a separate branch from `origin/main`
containing only the reviewed public changes.

Verify the remote commit SHA and GitHub Actions after pushing. A successful local
commit or a repository URL alone is not evidence of a successful remote update.
