# Publish YouTube-Edit-Ultra to GitHub

Default repository destination: `searadacunha/YouTube-Edit-Ultra`.

On macOS:

```bash
cd ~/Downloads/YouTube-Edit-Ultra   # adjust to where you unzipped it
brew install gh
gh auth login
./scripts/publish_github.sh
```

The script creates a clean `main` branch, commits the original source files, creates a **public** GitHub repository if it does not already exist, and pushes `main`. If the repo exists, it pushes your current branch to `main` instead. Neither raw video/music files nor OAuth tokens are committed (`.gitignore`).

To use a different owner/name:

```bash
GITHUB_OWNER=your-handle GITHUB_REPO=YouTube-Edit-Ultra ./scripts/publish_github.sh
```

The repository is not considered published until GitHub CLI returns its actual `https://github.com/...` URL. A local ZIP is not itself a remote GitHub repository.
