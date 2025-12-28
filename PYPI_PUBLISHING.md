# PyPI Publishing Guide

This document outlines all the changes needed and steps to publish `repo-scout` to PyPI.

## ✅ Changes Already Made

1. **Updated `pyproject.toml`** with required PyPI metadata:
   - Added `description`
   - Added `readme` reference
   - Added `license` information
   - Added `authors`
   - Added `keywords` for discoverability
   - Added `classifiers` for PyPI categorization
   - Added `project.urls` section (needs your actual URLs)

## 🔧 Required Manual Updates

### 1. Update Project URLs in `pyproject.toml`

Replace the placeholder URLs in `[project.urls]` with your actual repository URLs:
- `Homepage`: Your project homepage
- `Documentation`: Link to your documentation (if using mkdocs, this might be GitHub Pages)
- `Repository`: Your GitHub/GitLab repository URL
- `Issues`: Your issues tracker URL

### 2. Package Name Consistency ✅

**Resolved**: 
- Package name: `repo-scout` (for `pip install repo-scout`)
- CLI command: `scout` (after installation)
- Config directory: `.repo-scout/`
- All documentation has been updated to reflect this consistently

### 3. Add Version to `__init__.py`

Add a `__version__` attribute to `src/scout/__init__.py`:

```python
__version__ = "0.1.0"
```

This allows the version to be imported programmatically.

### 4. Create/Update CHANGELOG.md

Your `CHANGELOG.md` is currently empty. Consider adding:
- Version history
- Release notes
- Breaking changes
- New features

## 📦 Pre-Publishing Checklist

- [x] Update URLs in `pyproject.toml` (user has updated)
- [x] Resolve package name consistency (repo-scout vs secret-scout) ✅
- [x] Add `__version__` to `src/scout/__init__.py` ✅
- [ ] Update CHANGELOG.md with release notes
- [ ] Test the build locally
- [ ] Verify all dependencies are correct
- [x] Ensure `.gitignore` excludes build artifacts ✅

## 🚀 Publishing Steps

### 1. Install Build Tools

```bash
pip install build twine
```

### 2. Build the Package

```bash
# Clean any previous builds
rm -rf dist/ build/ *.egg-info

# Build source distribution and wheel
python -m build
```

This creates:
- `dist/repo_scout-0.1.0.tar.gz` (source distribution)
- `dist/repo_scout-0.1.0-py3-none-any.whl` (wheel)

**Note**: Package names with hyphens (like `repo-scout`) are normalized to underscores in wheel filenames (e.g., `repo_scout`). This is normal Python packaging behavior.

### 3. Test the Build Locally

```bash
# Install in a virtual environment to test
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate
pip install dist/repo_scout-0.1.0-py3-none-any.whl

# Test the command
scout --help

# Verify it works
deactivate
rm -rf test_env
```

### 4. Check the Package

```bash
# Check the built package for common issues
twine check dist/*
```

### 5. Upload to TestPyPI (Recommended First Step)

```bash
# Create account at https://test.pypi.org/account/register/
# Get API token from https://test.pypi.org/manage/account/token/

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ repo-scout
```

### 6. Upload to PyPI

```bash
# Create account at https://pypi.org/account/register/ (if not already)
# Get API token from https://pypi.org/manage/account/token/

# Upload to PyPI
twine upload dist/*
```

**Note**: You can also use `--repository-url https://upload.pypi.org/legacy/` if needed.

## 🔄 For Future Releases

1. Update version in `pyproject.toml` (e.g., `0.1.0` → `0.1.1`)
2. Update `__version__` in `src/scout/__init__.py`
3. Update `CHANGELOG.md`
4. Build: `python -m build`
5. Upload: `twine upload dist/*`

## 📝 Additional Recommendations

### Optional: Add GitHub Actions for Automated Publishing

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install build tools
        run: pip install build twine
      - name: Build package
        run: python -m build
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

### Optional: Add Version Management

Consider using tools like:
- `bump2version` for automated version bumping
- `setuptools-scm` for version from git tags

## ⚠️ Important Notes

1. **Package names on PyPI are permanent** - Choose carefully!
2. **Test thoroughly** before first release
3. **TestPyPI first** - Always test on TestPyPI before real PyPI
4. **Version numbers** - Follow semantic versioning (MAJOR.MINOR.PATCH)
5. **API tokens** - Store securely, never commit to git
6. **Build artifacts** - Already in `.gitignore`, good!

## 🐛 Troubleshooting

### "Package already exists"
- Check if the version already exists on PyPI
- Increment version number

### "Invalid metadata"
- Run `twine check dist/*` to see specific errors
- Verify all required fields in `pyproject.toml`

### "Command not found after install"
- Verify `[project.scripts]` entry point is correct
- Check that the module path exists

