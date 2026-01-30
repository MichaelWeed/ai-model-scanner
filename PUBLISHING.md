# Publishing to PyPI

Steps to publish `ai-model-scanner` to PyPI (and optionally TestPyPI first).

## Prerequisites

- PyPI account: https://pypi.org/account/register/
- API token: https://pypi.org/manage/account/token/
- Optional: TestPyPI account for dry runs: https://test.pypi.org/account/register/

## Steps

**1. Bump version**  
Set the same version in `pyproject.toml` (`[project] version = "X.Y.Z"`) and `ai_model_scanner/__init__.py` (`__version__ = "X.Y.Z"`). Use semver: major for breaking changes, minor for new features, patch for fixes.

**2. Run tests**  
```bash
pytest tests/ -v
```

**3. Build**  
```bash
pip install build twine
python -m build
```
This creates `dist/` with a source tarball and a wheel.

**4. Test install locally**  
```bash
pip install dist/ai_model_scanner-*.whl
ai-model-scanner scan --help
```

**5. (Optional) Upload to TestPyPI**  
```bash
twine upload --repository testpypi dist/*
```
Username: `__token__`, password: your TestPyPI token. Then try:
```bash
pip install --index-url https://test.pypi.org/simple/ ai-model-scanner
```

**6. Upload to PyPI**  
```bash
twine upload dist/*
```
Username: `__token__`, password: your PyPI API token.

**7. Verify**  
Check https://pypi.org/project/ai-model-scanner/ and run `pip install ai-model-scanner` in a clean environment.

## GitHub Actions

The repo has a workflow in `.github/workflows/publish.yml` that builds and publishes when you create a release (or trigger it manually). Add a secret named `PYPI_API_TOKEN` with your PyPI token. The workflow uses `twine upload` with that token.

## Common issues

- **“File already exists”** – That version is already on PyPI. Bump the version.
- **“Invalid credentials”** – Use username `__token__` and the token as password. Check the token scope (project or account).
- **“Package name already taken”** – `ai-model-scanner` is taken; pick another name or contact the current owner.

After publishing, you can create a GitHub release, update the repo description, and point people at `pip install ai-model-scanner`.
