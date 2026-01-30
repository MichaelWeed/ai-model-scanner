# Publishing to PyPI

Automated publishing uses **Trusted Publishers** (OIDC)—no API tokens in GitHub. One-time setup on PyPI and GitHub, then releases are automatic.

## One-time setup

### 1. Trusted Publisher on PyPI

- Go to https://pypi.org/manage/project/ai-model-scanner/settings/publishing/
- “Add a new publisher” → **GitHub** tab.
- Enter:
  - **Owner:** `MichaelWeed`
  - **Repository name:** `ai-model-scanner`
  - **Workflow name:** `publish-to-pypi.yml` (exact filename)
  - **Environment name (optional):** `pypi` (recommended for approval gates)
- Click “Add”.

Repeat on **TestPyPI** (https://test.pypi.org/manage/project/ai-model-scanner/settings/publishing/) with the same values; environment can be `testpypi`.

### 2. GitHub Environments (optional but recommended)

- Repo → **Settings** → **Environments**.
- Create:
  - **`pypi`** – add required reviewers or approval for production.
  - **`testpypi`** – no approval for frequent test uploads.

No secrets needed; OIDC handles auth.

### 3. Workflow

`.github/workflows/publish-to-pypi.yml` is already in the repo. It:

- **Builds** on every push.
- **Publishes to PyPI** only when you push a **tag** (e.g. `v0.1.0`).
- **Publishes to TestPyPI** on every push that is **not** a tag (e.g. pushes to `master`).

## Releasing a new version

1. Bump version in `pyproject.toml` and `ai_model_scanner/__init__.py` (e.g. `0.1.1`).
2. Run tests: `pytest tests/ -v`.
3. Commit and push.
4. Create and push a tag:
   ```bash
   git tag v0.1.1
   git push origin v0.1.1
   ```
5. The workflow runs; the `pypi` job publishes to PyPI. If you use environment approval, approve the run in **Actions** → workflow run → **Review deployments**.

## Manual upload (no GitHub Actions)

If you need to upload from your machine:

- PyPI token: https://pypi.org/manage/account/token/
- `pip install build twine && python -m build && twine upload dist/*`
- Username: `__token__`, password: your token.

## Common issues

- **“File already exists”** – That version is already on PyPI. Bump the version and push a new tag.
- **Trusted Publisher “Workflow not found”** – Workflow filename on PyPI must be exactly `publish-to-pypi.yml` and live in `.github/workflows/`.
- **Environment approval** – If the `pypi` environment has required reviewers, approve the deployment in the Actions run.

After publishing, check https://pypi.org/project/ai-model-scanner/ and `pip install ai-model-scanner`.
