# sphinx-jinja2 — modernization & minijinja migration: handoff

> Working/handoff doc for continuing this effort. **Not part of the package — do not commit
> into the PR.** Delete before merge (or keep in a scratch location).
> Companion file: `REVIEW_ROUND.md` (full Opus review-round findings + evidence).

Last updated: 2026-07-15.

---

## 1. Session rules (carry these forward)

These are standing preferences the user set during the session. Apply them for the rest of
this effort:

1. **No Claude/promotional footers in anything published to GitHub.** Do **not** put
   "🤖 Generated with Claude Code", session links, or the model identifier
   (`claude-fable-5`) in PR descriptions, PR/issue comments, or review comments. Keep those
   surfaces clean and about the change only.
   - Distinct from the above: **commit messages** still carry the `Co-Authored-By:` trailer
     required by this environment's git guidance (that's a git co-authorship trailer, not a
     promotional footer). Do not put the model identifier in commit messages either.
2. **Always do Opus agent review rounds *and* your own deep-thinking pass** before treating
   substantive work as done. Spawn independent Opus (`model: opus`) review agents with
   distinct lenses (correctness / integration / config-docs / adversarial), *and*
   personally reason through the diff — don't rely on either alone. Reconcile both before
   pushing. Test-suite/lint/typecheck green is necessary but **not** sufficient.

Other environment constraints already in force (from the task setup):
- Develop on branch **`claude/repo-modernize-triage-biyd2m`**; push with
  `git push -u origin claude/repo-modernize-triage-biyd2m`.
- Don't open new PRs unless asked. PR **#10** already exists for this branch.
- GitHub actions go through the `mcp__github__*` tools (load via ToolSearch); no `gh` CLI.

---

## 2. Where things stand

- **Branch:** `claude/repo-modernize-triage-biyd2m` (2 commits ahead of `main`), pushed.
  - `592d29d` ♻️ Migrate template rendering from Jinja2 to minijinja
  - `0cb12c9` 🔧 Modernize packaging, CI, and dev tooling
- **PR:** [#10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10) — open, footer
  removed. Base `main`. Body summarizes migration + triage.
- **Verification done:** 21/21 pytest on Sphinx 9.0.4 (py3.11) and Sphinx 7.2.6; `-nW` docs
  build clean; mypy `--strict` clean; all pre-commit hooks pass; wheel builds with
  `License-Expression: MIT`.
- **Review round:** 4 Opus agents complete (see `REVIEW_ROUND.md` for the full report). Net
  result: **1 high-severity regression must be fixed before merge** (template-loader path
  traversal), plus a handful of lower items. **No fixes applied yet** — the user asked to
  document first.

### Local environment (for whoever continues)
- Repo: `/home/user/sphinx-jinja2`
- venv (latest): `.venv` → Sphinx 9.0.4, minijinja 2.21.0, myst-parser 5.1.0, package `-e`,
  furo, ruff 0.15.21, mypy, build, pre-commit.
- venv (floor): `scratchpad/venv72` → Sphinx 7.2.6, myst-parser 4.0.1.
- Run tests: `PATH=$PWD/.venv/bin:$PATH .venv/bin/pytest -q`
- Update snapshots: `.venv/bin/pytest -q --snapshot-update`
- Docs: `.venv/bin/python -m sphinx -nW --keep-going -b html docs/ <out>`
- Lint/type: `.venv/bin/ruff check src/ tests/ docs/` · `.venv/bin/mypy --config-file=pyproject.toml src/`
- Scratch review projects from the agents live under `scratchpad/review{1..4}/`.

---

## 3. Outstanding work

### 3-URGENT. pre-commit.ci broke CI (discovered post-review, NOT yet fixed)

After the branch was pushed, **pre-commit.ci auto-committed `66138b6`** onto the branch, and its
`trailing-whitespace` hook **stripped a legitimate trailing space** from
`tests/__snapshots__/test_builds/test_myst.doctree.xml` (the paragraph text `Hello ` before the
`<emphasis>` node). That space is real doctree content, so **`test_myst` now fails** and CI on
PR #10 is red:
```
<paragraph>
-    Hello      (snapshot, corrupted by the hook)
+    Hello       (actual rendered doctree — trailing space)
```
Root cause is the `.pre-commit-config.yaml` this PR introduced: the `trailing-whitespace` and
`end-of-file-fixer` hooks must not touch syrupy single-file snapshots. **Fix:** add
`exclude: ^tests/__snapshots__/` (or `files:` scoping) to those two hooks, and restore the correct
snapshot (`git checkout 0cb12c9 -- tests/__snapshots__/test_builds/test_myst.doctree.xml`, or
re-run `pytest --snapshot-update`). Then re-push. Any other snapshot with meaningful leading/trailing
whitespace or missing final newline is vulnerable to the same corruption.

### 3a. Code fixes from the review round (NOT yet applied)

Full findings, evidence, and reproductions are in `REVIEW_ROUND.md`. Decisions:

| # | Sev | Fix? | What to do |
|---|-----|------|-----------|
| 1 | **HIGH** | **Yes — blocker** | `_load_template` in `src/sphinx_jinja2/__init__.py` (~L210) must reject absolute names and `..` traversal and confirm the resolved path stays under `template_base.resolve()`, returning `None` otherwise (restores the old `FileSystemLoader` sandbox). Add a regression test: `{% include "/etc/hostname" %}` and `{% include "../x" %}` must produce a "template not found" warning, not leak file contents. |
| 2 | MED | Yes | `:file:` read (~L264) catches only `OSError`; non-UTF-8 raises `UnicodeDecodeError` (a `ValueError`) and crashes the whole build, while the include path degrades to a warning. Make them consistent — catch `UnicodeDecodeError` (or read with `errors=`). Add a test. |
| 3 | LOW/MED | Yes | Bare `:raw:` (no format value) is falsy → silently parses instead of emitting raw, no warning. Warn that `raw` needs a format argument. Add a test. |
| — | LOW | Yes | Env-kwargs allowlist `_ENVIRONMENT_KWARGS` omits `path_join_callback` (relevant to include-path resolution) and `reload_before_render`. Add at least `path_join_callback`. |
| — | LOW | Docs | jinja2 `@pass_context`/`@pass_environment` filters don't work under minijinja (they fail at render → warning, not crash). Note this in the "Migration from Jinja2" docs section as a caveat. |
| — | LOW | Yes | `CONTRIBUTING.md` (~L17): dangling "To install them, run:" with no command. Fix the instruction. |
| M1 | MED | Fix/doc | MyST `:file:` warning attribution: the reporter monkeypatch (~L304-328) is **inert on myst-parser 5.x** (myst 5 logs against `env.docname`, not `document["source"]`), so template parse-warnings point at the including `.md`, not the template — the code comment overclaims and it diverges from the RST path + myst 4.x. Correct the comment at minimum; investigate whether attribution can be improved on myst 5.x, else document the limitation. |
| M2 | LOW | Docs | `docs/index.rst` (~L187): "problems … always refer to the first line number …" is true only for the RST path; the MyST path maps warnings to the actual offset line inside the rendered content. Reword to cover both. |
| M3 | LOW | Skip | `:debug:` node placement differs RST vs MyST (in MyST a template heading pushes the debug block inside the last section). Cosmetic; debug is a dev aid. Note only. |
| 4 | LOW | Skip | Non-dict `jinja2_env_kwargs` crashes on `.items()`. Pre-existing; Sphinx already emits a type-mismatch warning first. Marginal — optional guard only. |
| 5 | LOW | Skip | Self-referential `:file:` directive hangs (in the `insert_input` path, identical to `main`). Deliberate self-reference; out of scope. |
| 6 | LOW | Skip | `:file: ../…` escapes srcdir (author-controlled, uses `relfn2path`, identical to `main` and to docutils' own `include`). Consistent by design. |

After fixing: re-run pytest (both venvs), docs `-nW`, mypy, pre-commit; regenerate/inspect
any affected snapshots; then **run another Opus review round on the fix diff** before pushing
(per session rule 2). Update `CHANGELOG.md` if user-facing behavior changes (the path-traversal
fix is worth a "Security"/"Fixed" note; also fix the changelog date to the real release date).

### 3b. Triage follow-through (issues/PRs — not yet actioned)

The PR body already credits/links these; still to do on GitHub once #10 lands (keep comments
footer-free):
- **#3** (MyST `insert_input` error) — fixed by this PR; close on merge.
- **#4** (`raw` option, @eudoxos) — incorporated with co-author credit; close with thanks
  (don't merge — the file was rewritten).
- **#6** (document #3 workaround, @eudoxos) — obsoleted by the real fix + MyST docs; close
  with thanks.
- **#2** (pre-commit autoupdate) — superseded (adopted the same revs); close (pre-commit.ci
  will recycle otherwise).
- **#8 / #9** (dependabot action bumps) — superseded (checkout@v6 / setup-python@v6 in the
  workflow); will auto-close when `main` has the bumps.

### 3c. External / user actions
- **PyPI trusted publishing (blocks the next release):** the user must register a trusted
  publisher for `sphinx-jinja2` on PyPI — workflow `tests.yml`, environment `pypi`. Until
  then the publish job cannot upload on tag.
- **Upstream myst-parser issue (optional, nice-to-have):** file a bug — in
  `DocutilsRenderer.nested_render_text(temp_root_node=...)`, `_level_to_section` is snapshotted
  for restore but never re-rooted at `temp_root_node`, so sections created via
  `MockState.nested_parse(match_titles=True)` escape the container and render out of order.
  Minimal repro was found during this work (this is *why* the extension mimics myst's own
  `include` directive via `nested_render_text` instead of a contained nested parse). A public
  "render text at current position" API (or fixing the re-rooting) would let the extension drop
  its reach into `state._renderer`.

### 3d. PR #10 monitoring (offered, not started)
The user hasn't opted in yet. If asked, subscribe via `subscribe_pr_activity` for owner
`sphinx-extensions2`, repo `sphinx-jinja2`, PR 10, then respond to CI/review events per the
environment's PR-activity rules (footer-free replies).

---

## 4. Design notes worth keeping (context for the next agent)

- **Rendering parity was the design goal.** All 9 original doctree snapshots are byte-identical
  under minijinja — the engine swap was deliberately behavior-preserving. Don't "improve"
  rendering output without re-snapshotting and calling it out.
- **Dependency tracking** now happens via the loader callback (records templates *actually*
  loaded, incl. transitive includes) instead of `jinja2.meta.find_referenced_templates` static
  analysis. This is a net improvement (old code missed transitive includes → stale builds), but
  it's why the path-traversal fix must live *in the loader*.
- **Two rendering paths by design:** RST uses `state_machine.insert_input` (full docutils
  contract: real section levels, following content joins injected sections, per-line source
  attribution). MyST has no such state machine, so it renders at the current position like
  myst's own `include`. A generic contained-`nested_parse` fallback exists for unknown states.
  See `REVIEW_ROUND.md` §MyST for the nuance and the "best way possible" analysis.
- **Import-string filters/tests** were added because Sphinx can't cache function objects (full
  rebuilds + `config.cache` warnings on Sphinx ≥7.3). Import strings are the documented
  recommendation; function objects still work.
