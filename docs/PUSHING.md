# Publishing this branch to GitHub (handoff)

> **Read me first if you're wondering why nothing is on GitHub yet.**

All of the v1 work is committed **locally** on the **`build/v1`** branch of the
repo at `…/LensTrace/LensTrace` (remote `origin` →
`https://github.com/Ranger222/LensTrace.git`). It could **not be pushed** during
the build because the only credential available was **read-only**. Pushing is a
one-liner once a write-capable credential exists.

## What blocked the push

| Credential found | Result |
|---|---|
| `GITHUB_PAT` env var (account **Ranger222**, the repo owner) | A **fine-grained** token **without `Contents: write`** → `git push` returns `403 denied to Ranger222`. |
| macOS keychain entry for `github.com` | A **different account** (`piyushtomar-ethara`) with **no write access** to this repo → `403`. |
| GitHub MCP server | **Not connected** in the session. |
| `gh` CLI | **Not installed.** |

No further credential stores were searched (by design). So the work was built,
tested, and committed locally, ready to push.

## Fix it (pick ONE), then push

The repo already has a credential helper configured that reads `$GITHUB_PAT`, so
**option A is the least effort.**

### A. Grant write to the existing fine-grained token  ✅ recommended
1. GitHub → Settings → Developer settings → **Fine-grained tokens** → your token.
2. Under **Repository permissions**, set **Contents: Read and write** (and ensure
   `Ranger222/LensTrace` is in the token's selected repositories). Save.
3. Make sure `$GITHUB_PAT` in your shell is that token, then:
   ```bash
   cd …/LensTrace/LensTrace
   git push -u origin build/v1
   ```

### B. Use the GitHub MCP
If you connect a write-capable GitHub MCP server, ask Claude to push `build/v1`
and open the PR through it.

### C. Classic token or SSH
- Classic PAT with `repo` scope: `git push https://<TOKEN>@github.com/Ranger222/LensTrace.git build/v1`
- Or add an SSH key to the **Ranger222** account and:
  `git remote set-url origin git@github.com:Ranger222/LensTrace.git && git push -u origin build/v1`

## Then: open the PR and land it

Direct pushes to `main` are intentionally avoided. Open a reviewed PR:

```bash
# with gh installed:
gh pr create --base main --head build/v1 \
  --title "LensTrace v1: SDK + dashboard + tests" \
  --body  "Local-first agent tracing. See docs/ for design; scripts/verify.sh is green."
```
…or open it from the GitHub web UI (`build/v1` → `main`). CI
(`.github/workflows/ci.yml`) will run the same gates as `scripts/verify.sh`.
Merge when green.

## Sanity check before pushing

```bash
cd …/LensTrace/LensTrace
git log --oneline            # the v1 commits on build/v1
git status                   # should be clean
source .venv/bin/activate && ./scripts/verify.sh   # expect: ALL GREEN ✅
```

## Note on PyPI (later, not required to push)

The brand and CLI stay **LensTrace** / `lenstrace`, but the **PyPI distribution
name `lenstrace` is taken** by an unrelated package — choose a different
distribution name (e.g. `lenstrace`) in `pyproject.toml` before `twine upload`.
The import name and `lenstrace` command can stay as-is. See
[ROADMAP.md](ROADMAP.md).
