# C2PA Build-Fix Spike — Finding (not a verified fix)

**Date:** 2026-06-24 · **Branch:** `floorno8/remixa-impl-mocked-features`
**Mandate:** investigate the real blocker; propose a patch; do **NOT** claim valid signatures without
a test build. No code was changed for this task — finding only.

## Root cause (proven empirically)
`requirements.txt:30-32` disables `c2pa-python==0.3.1` with "Rust build issues on Fly.io." The chain:

- `c2pa-python` is a Rust/pyo3 extension. If pip can't find a matching **prebuilt wheel**, it builds
  from sdist, which needs `cargo`/`rustc`.
- The Dockerfile builder stage (`Dockerfile:4-19`, `python:3.11-slim`) installs `build-essential
  ffmpeg libsndfile1` — **no Rust toolchain**. So a source build fails.
- **Verified:** the pinned `0.3.1` has **no** linux/cp311 wheel:
  ```
  pip download --only-binary=:all: --platform manylinux_2_17_x86_64 --python-version 311 \
      --abi cp311 --implementation cp --no-deps c2pa-python==0.3.1
  → ERROR: No matching distribution found for c2pa-python==0.3.1
  ```
  That is exactly why the Fly build broke: no wheel → source build → no Rust → fail.

## The fix is a version bump, not adding Rust (Option A — recommended)
**Verified:** a current `c2pa-python` ships a prebuilt manylinux wheel — `pip download` for the latest
matching my constraints fetched:
```
c2pa_python-0.9.0-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
```
`py3-none-manylinux` = pure-binary wheel, **no Rust at install time**. So:

1. Pin `c2pa-python` to the newest version that publishes a `cp311`/`abi3` `manylinux_2_17_x86_64`
   wheel (≥ 0.9 confirmed; pick against the deploy Python/arch — Fly = linux/amd64).
2. `pip install` then uses the wheel; the Dockerfile needs **no** change.
3. **But the API changed massively** across `0.3.1 → 0.9 → 0.36`. `c2pa_embedder.py` today does
   **SHA-256 hashing only** (no real signing) — so it must be **rewritten** against the chosen
   version's signing API regardless. That rewrite + a `c2pa-tool verify` smoke test is the real work,
   and needs a build env. **Not done here.**

## Fallback (Option B — add Rust to the builder)
Only if a wheel can't be matched to the final Python/arch. Patch the **builder stage** (runtime image
unaffected — it copies only `/opt/venv`):

```dockerfile
# Dockerfile builder stage — add after the apt-get install (line 11)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.cargo/bin:${PATH}"
# (curl is already installed in the runtime stage; add it to the builder apt-get line too)
```
Cost: slower builds (Rust compile of c2pa + deps), larger builder layer. Unnecessary given Option A.

## Status / what's NOT done (gates)
- ❌ No working C2PA signatures produced or verified (per mandate — needs a real build + `c2pa-tool verify`).
- ❌ `c2pa_embedder.py` not rewritten (SHA-256 placeholder remains; new-API rewrite required).
- ✅ Root cause proven; ✅ wheel-availability proven; ✅ two patch options with the recommended path.

**Next step (needs build env):** choose the exact version against Fly's Python/arch, rewrite
`c2pa_embedder.py` to that version's signing API, build, and `c2pa-tool verify` a signed sample.
