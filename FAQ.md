# FAQ

## Setup & environment

**Do I need a virtual environment?**  
Yes, if you’re developing or installing from source. It keeps dependencies isolated. Use `./setup.sh` or `make setup` to create and use a venv. Don’t install into system Python.

**“Command not found” after pip install**  
Your PATH might not include the Scripts (Windows) or bin (macOS/Linux) directory where the CLI was installed. Try `python3 -m ai_model_scanner.cli scan` from the same environment you used for `pip install`.

**IDE wants to create a venv**  
Go ahead. Point it at the project and use the interpreter in `venv/`.

---

## Scanning

**Why isn’t it finding my models?**  
Check: (1) File size—default minimum is 500MB; use `--min-size 100MB` if needed. (2) Paths—run `--dry-run` to see what’s included. (3) LM Studio in `~/.lmstudio/models` is supported; if you use a custom config, add that path to `lm_studio_paths`. For a full rescan with no skipping, use `ai-model-scanner scan --no-incremental`.

**Scan is slow**  
Install `fd` (e.g. `brew install fd`). Use a higher `--min-size` to scan fewer files. Scanning only known tool paths is faster than a full tree.

**Can I change which paths are scanned?**  
Yes. Copy `examples/config.toml.example` to `~/.config/ai-model-scanner/config.toml` (or the Windows equivalent) and edit `scan_roots` and the `[tools]` paths.

---

## Caching and incremental scanning

**How does the cache work?**  
After you run `scan`, results are stored under `~/.cache/ai-model-scanner/` (or the Windows equivalent). Commands like `duplicates`, `cleanup`, `export`, `report`, `show`, and `keep` use that cache so they don’t rescan every time. Use `--no-cache` on those commands to force a fresh scan. Cache is reused for up to 24 hours.

**There’s no `--no-cache` on `scan`.**  
Right. To do a full rescan without reusing directory skip logic, use `scan --no-incremental`.

**Why is the second scan faster?**  
Incremental scanning: it only rescans directories whose modification time changed. The rest is loaded from cache. You’ll see something like “Skipped N unchanged directories, scanned M changed.”

**Where is the cache?**  
- macOS/Linux: `~/.cache/ai-model-scanner/`  
- Windows: `%LOCALAPPDATA%\ai-model-scanner\cache\`  

Files: `last_scan.json` (scan results), `directory_index.json` (mtimes for incremental). You can delete these to clear the cache.

---

## Duplicates and cleanup

**How are duplicates detected?**  
SHA256 hash. For files over 10MB it hashes the first 1MB to keep things fast; for smaller files it hashes the whole file.

**What’s the difference between `duplicates` and `cleanup`?**  
`duplicates` only lists duplicate groups and (optionally) code references. `cleanup` uses the same data but finds copies that aren’t referenced anywhere and can delete them (with confirmation). Use `duplicates` to review, then `cleanup` to remove.

**How do I read the cleanup output?**  
- “Groups with code references”: at least one copy is referenced in code. You need to decide which copy to keep and point code at it; then you can use `keep <path>` to remove the others.  
- “Safe to delete”: no references; the tool can remove these after you confirm.  
If you see the same path more than once in a group, that’s a display bug (paths are deduplicated now). References in lock files (e.g. pnpm-lock.yaml) might be metadata only—check if the model is actually used.

**How does `keep` work?**  
You pass the path of the copy you want to keep. It finds all other copies with the same hash and, after you confirm, deletes only those. Use `--dry-run` to see what would be deleted.

**What if I delete a model that’s referenced in code?**  
`keep` doesn’t check references; it just deletes duplicates of the given file. If you’re unsure, run `report` first, update your code to point at the copy you want to keep, then run `keep` with that path. `cleanup` only offers to delete unreferenced copies.

---

## Code reference search

**How does reference search work?**  
It searches your configured code folders (e.g. `~/Documents`, `~/Projects`) for the model filename in text files. It skips things like `.git`, `node_modules`, `venv`, and caps the number of files per folder so it doesn’t hang.

**Which dirs are searched?**  
Defined in config under `[scanner]` → `code_folders`. Defaults often include `~/Documents`, `~/Projects`, `~/Desktop`, and the current working directory.

**Why is it slow or stuck?**  
Large trees or many code folders. Reduce `code_folders` in config or interrupt with Ctrl+C.

---

## Reports and workflows

**What does `report` do?**  
Writes two files (by default to Desktop): one with models that are referenced in code, one with models that aren’t. Format is CSV or JSON. Useful before cleaning up duplicates.

**How do I view last scan without rescanning?**  
`ai-model-scanner show` shows the cached results. `duplicates`, `export`, `report`, `cleanup`, and `keep` also use the cache.

**Suggested workflow for duplicates**  
1. `scan` once.  
2. `duplicates` to see groups and references.  
3. `report` if you want files on disk.  
4. Update code to point at the copy you want to keep.  
5. `keep /path/to/kept/model.gguf` for each group, or `cleanup` to bulk-remove unreferenced copies.

---

## Troubleshooting

**“No cached scan results found”**  
Run `scan` first. If you cleared the cache or it’s older than 24 hours, run `scan` again.

**Scanner says a directory is unchanged but I added files**  
Rarely the directory mtime doesn’t update. Use `scan --no-incremental` to force a full rescan.

**`keep` says “Model not found in scan results”**  
The file might be under the size threshold, or the path doesn’t match. Check size with `ls -lh`, try `scan --min-size 100MB`, and use the exact path shown in `show` or `duplicates`.

**References aren’t being found**  
Filenames are case-sensitive on Linux/macOS. Check that the path is in `code_folders` and the file is plain text. You can try `grep -r "model-filename.gguf" ~/Projects` to confirm.
