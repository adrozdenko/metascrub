# Contributing to MetaScrub

Thanks for your interest in improving MetaScrub! 🧼

## Ways to help

- 🐛 **Report bugs** — open an issue with the OS, file format, and steps to reproduce
- 💡 **Suggest features** — Windows/Linux launchers, a native build, video support, etc.
- 🔧 **Send a pull request** — see below

## Development setup

```bash
git clone https://github.com/adrozdenko/metascrub.git
cd metascrub
brew install exiftool imagemagick      # the only external dependencies
python3 server.py                       # run the app locally
```

The codebase is intentionally tiny and dependency‑free:

- `server.py` — Python **standard library only** (no pip installs). Keep it that way unless there's a strong reason not to.
- `index.html` — vanilla HTML/CSS/JS, no build step, no frameworks.
- `clean.sh` — POSIX‑ish bash; the canonical reference for the cleaning logic.

## Guidelines

- **Keep it lossless.** Never re‑encode JPEG/HEIC pixels. PNG/WebP re‑encode is fine because it's lossless.
- **Stay offline.** No network calls, no analytics, no external services. Privacy is the point.
- **Match the existing style.** Small, readable, comment the non‑obvious bits.
- **Test your change** on at least one real C2PA‑tagged image (e.g. a ChatGPT export) and confirm the output is clean:
  ```bash
  exiftool -a -G1 out/yourfile.png | grep -Ei 'C2PA|JUMBF|trainedAlgorithmic'   # should print nothing
  ```

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Windows launcher
fix: preserve EXIF orientation on rotated JPEGs
docs: clarify the watermark limitation
```

## Code of Conduct

Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
