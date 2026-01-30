# AI Model Scanner

[![CI](https://github.com/MichaelWeed/ai-model-scanner/workflows/CI/badge.svg)](https://github.com/MichaelWeed/ai-model-scanner/actions)
[![PyPI version](https://badge.fury.io/py/ai-model-scanner.svg)](https://badge.fury.io/py/ai-model-scanner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

A small CLI that finds AI model files on your machine—Ollama, LM Studio, ComfyUI, Hugging Face cache, stray `.gguf` and `.safetensors`—and shows you what you have, where it lives, and which files are duplicates. Everything runs locally; no servers, no accounts.

---

## Install

```bash
pip install ai-model-scanner
```

You need Python 3.9+. For faster scanning, install `fd` (macOS: `brew install fd`, Linux: `apt install fd-find` or `dnf install fd`, Windows: [releases](https://github.com/sharkdp/fd/releases)).

---

## Quick start

```bash
ai-model-scanner scan
```

That scans your home directory for model files over 500MB and prints a table. To scan somewhere else or change the size cutoff:

```bash
ai-model-scanner scan --root ~/Documents
ai-model-scanner scan --min-size 100MB
```

Export to a file:

```bash
ai-model-scanner scan --export json > my_models.json
ai-model-scanner scan --export csv > my_models.csv
```

To see what *would* be scanned without doing it: `ai-model-scanner scan --dry-run`.

---

## What it does

- **Scan** – Finds model files (`.gguf`, `.safetensors`, `.pth`, `.bin`, etc.) under given roots. Uses `fd` if present, otherwise `find`. Can stick to “known” tool paths (Ollama, LM Studio, ComfyUI, Hugging Face, MLX) or do a full tree.
- **Incremental scans** – After the first run it skips directories that haven’t changed, so later scans are faster. Use `--no-incremental` to force a full rescan.
- **Duplicates** – Hashes files (SHA256; for big files it samples the first 1MB) and groups duplicates so you can see wasted space.
- **Code references** – Can search your code (e.g. `~/Documents`, `~/Projects`) for references to model filenames. Handy before deleting duplicates.
- **Cleanup / keep** – `cleanup` finds unreferenced duplicate copies and can delete them (with confirmation). `keep /path/to/model.gguf` keeps that file and deletes the other copies with the same hash.
- **Reports** – Writes CSV/JSON reports of “referenced” vs “unreferenced” models (e.g. to Desktop).
- **Watch** – Watches paths and can notify when new large model files appear.

Results of a scan are cached so `duplicates`, `cleanup`, `export`, `report`, and `show` can reuse them without rescanning (see FAQ for cache details).

---

## Commands (overview)

| Command | What it does |
|--------|----------------|
| `scan` | Find model files, optionally export, run health/reference checks |
| `duplicates` | List duplicate groups and (if requested) where they’re referenced in code |
| `cleanup` | Find unreferenced duplicates and optionally delete them |
| `keep <path>` | Keep one copy, delete the rest of its duplicate set |
| `report` | Write referenced/unreferenced model reports (CSV/JSON) |
| `show` | Show last scan results from cache |
| `export` | Export cached results to JSON/CSV/TXT |
| `watch` | Watch paths for new model files |
| `health` | Compare scan with Ollama/LM Studio CLI |

Run `ai-model-scanner <command> --help` for options.

---

## Configuration

Config file (create if you want to customize):

- **macOS/Linux:** `~/.config/ai-model-scanner/config.toml`
- **Windows:** `%APPDATA%\ai-model-scanner\config.toml`

Example (see `examples/config.toml.example` for a full one):

```toml
[scanner]
min_size_mb = 500
known_paths_only = false
scan_roots = ["~/"]

[tools]
ollama_paths = ["~/ollama/models", "/usr/local/var/ollama/models"]
lm_studio_paths = [
    "~/Library/Application Support/LMStudio/models",
    "~/.lmstudio/models"
]

[output]
default_format = "table"
group_by_tool = true
show_duplicates = true
```

You can add your own paths under `[tools]` and set `scan_roots` for full scans.

---

## Where it looks (defaults)

It knows about common installs for:

- **Ollama** – e.g. `~/ollama/models`, `~/.ollama/models`, platform-specific paths
- **LM Studio** – Application Support paths and `~/.lmstudio/models`
- **ComfyUI** – `~/ComfyUI/models/checkpoints`, `loras`, `vae`, etc.
- **Hugging Face** – `~/.cache/huggingface/hub`
- **MLX** – macOS `~/mlx-community`, `~/Library/Application Support/mlx`

Exact paths are in the example config. If your models live elsewhere, add them to `config.toml` or run with `--full-scan` and optionally `--learn-paths` to have the scanner suggest new paths from what it finds.

---

## Scan options (short reference)

- `--root`, `-r` – Directory to scan (default: home).
- `--min-size`, `-s` – Minimum file size (default 500MB).
- `--full-scan` – Ignore “known paths” and scan from roots (and disable incremental for that run).
- `--no-incremental` – Don’t skip unchanged dirs; rescan everything.
- `--export`, `-e` – `json`, `csv`, or `txt`.
- `--dry-run` – Print what would be scanned, don’t scan.
- `--find-references` – Search code dirs for model references.
- `--health` – Cross-check with Ollama/LM Studio.
- `--learn-paths` – Suggest new tool paths from discovered models and save to config.

---

## Duplicates, cleanup, keep

- **`duplicates`** – Reads from last scan cache (or runs a scan). Shows groups of identical files and, if you asked for it, code references. Use `--no-cache` to force a fresh scan.
- **`cleanup`** – Same data, but finds unreferenced duplicate copies and asks before deleting. Use `--dry-run` to see what would be removed.
- **`keep /path/to/model.gguf`** – Keeps that file and deletes the other copies with the same hash (after confirmation). Use `--dry-run` to preview.

Cache: Commands that use the last scan (`duplicates`, `cleanup`, `export`, `report`, `show`, `keep`) use the cache by default. Run `scan` first if you haven’t, or pass `--no-cache` to force a new scan. There is no `--no-cache` on `scan` itself; use `--no-incremental` for a full rescan.

---

## If something goes wrong

- **“Command not found”** – Ensure the environment where you ran `pip install ai-model-scanner` is on your PATH, or run `python3 -m ai_model_scanner.cli scan`.
- **No models found** – Check size threshold (`--min-size 100MB`), that paths are readable, and try `--dry-run` to see what’s included. If models are in a custom location, add it in config or use `--full-scan`.
- **Permission errors** – The tool skips files it can’t read. On macOS you may need Full Disk Access for some locations.

---

## Development

```bash
git clone https://github.com/MichaelWeed/ai-model-scanner.git
cd ai-model-scanner
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e ".[dev]"
pytest tests/ -v
```

Lint: `ruff check ai_model_scanner/ tests/`

Package layout: `ai_model_scanner/` holds the CLI (`cli.py`), scanner, model/tool/duplicate logic, formatters, config, watcher, and reference finder. See `pyproject.toml` for deps and script entry point.

Contributions: open an issue or PR. Keep style consistent (PEP 8, ruff), add tests for new behavior, and update docs if you change behavior.

---

## License

MIT. See [LICENSE](LICENSE).
