# sphinx-jinja2 — PR #10 review round

> Full record of the Opus agent review round + maintainer deep-analysis for
> [PR #10](https://github.com/sphinx-extensions2/sphinx-jinja2/pull/10)
> (branch `claude/repo-modernize-triage-biyd2m`, diff vs `main`).
> **Working doc — not part of the package, do not commit into the PR.**
> Companion: `HANDOFF.md` (session rules + continuation plan).

Date: 2026-07-15. No code fixes have been applied yet — this is findings-only.

---

## How the review was run

Four independent Opus (`model: opus`) review agents, each a different lens, plus a maintainer
deep-analysis pass over the diff. All agents worked against the real editable install and built
actual Sphinx projects to verify claims empirically (no armchair findings). Two environments:

- `.venv` — Sphinx 9.0.4, minijinja 2.21.0, myst-parser 5.1.0 (primary)
- `scratchpad/venv72` — Sphinx 7.2.6, myst-parser 4.0.1 (floor)

| Agent | Lens | Result |
|-------|------|--------|
| 1 | Core migration correctness (parity vs jinja2) | 1 high, 2 low |
| 2 | MyST integration / output-node paths | 1 medium, 2 low; no build-breakers |
| 3 | Config / packaging / docs | essentially clean; 1 low (pre-existing) |
| 4 | Adversarial (break it) | reproduced the high; 5 more (mostly pre-existing/low) |

**Headline:** exactly one issue must block merge — a **high-severity template-loader
path-traversal regression**, independently found by Agents 1 and 4 with working exploits.
Everything else is medium/low or out-of-scope-by-design.

---

## Consolidated findings & decisions

Severity: HIGH = crash / wrong content / security · MED = confusing failure or wrong attribution
· LOW = cosmetic / robustness. "New" = introduced by this PR; "Pre" = pre-existing on `main`.

| ID | Sev | New? | Summary | Decision |
|----|-----|------|---------|----------|
| **F1** | **HIGH** | **New** | Template loader reads absolute/`..` paths → arbitrary file read into rendered docs, silently | **FIX — blocker** |
| F2 | MED | Pre (now inconsistent) | `:file:` non-UTF-8 crashes the build (`UnicodeDecodeError` not caught) | **FIX** |
| M1 | MED | New | MyST `:file:` warning misattributed on myst 5.x (monkeypatch inert) | **FIX comment / document** |
| F3 | LOW/MED | New | bare `:raw:` (no format) silently parses instead of warning | **FIX** |
| A1 | LOW | New | env-kwargs allowlist omits `path_join_callback`, `reload_before_render` | **FIX (add path_join_callback)** |
| A2 | LOW | — | jinja2 `@pass_context`/`@pass_environment` filters don't work under minijinja | **DOCUMENT** |
| M2 | LOW | New | docs "warnings always refer to first line" wrong for MyST path | **FIX docs** |
| C1 | LOW | Pre | `CONTRIBUTING.md` dangling "To install them, run:" | **FIX** |
| M3 | LOW | New | `:debug:` node placement differs RST vs MyST (cosmetic) | Skip (note) |
| F4 | LOW | Pre | non-dict `jinja2_env_kwargs` crashes on `.items()` (Sphinx warns first) | Skip |
| F5 | LOW | Pre | self-referential `:file:` directive hangs (in `insert_input`, = main) | Skip |
| F6 | LOW | — | `:file: ../…` escapes srcdir (author-controlled, = main & docutils `include`) | Skip |

---

## F1 — HIGH — Template-loader path traversal (BLOCKER)

**Where:** `src/sphinx_jinja2/__init__.py`, `_load_template` (~L210-218).

**Defect.** The loader does `path = template_base / name` with no sanitization, and minijinja
passes the raw `{% include %}` / `{% extends %}` / `{% import %}` target string through verbatim.
`pathlib` join semantics defeat the intended sandbox:
- `template_base / "/etc/hostname"` → `/etc/hostname` (an absolute segment discards the base).
- `template_base / "../../x"` → resolves outside the source directory.

On `main`, `jinja2.FileSystemLoader(template_base)` ran every name through `split_template_path`,
which raises `TemplateNotFound` for any `..` segment and remaps a leading `/` to a *srcdir-relative*
path — so both were blocked.

**Independently reproduced (Agent 4), real Sphinx build, zero warnings:**
```rst
.. jinja::

   {% include "/etc/hostname" %}

.. jinja::

   {% include "../../secret_outside.txt" %}
```
→ `build succeeded`, and `index.html` contained the real `/etc/hostname` contents and a file
placed *outside* the srcdir (`TOP_SECRET_abc123`). `{% extends "../parent.jinja" %}` leaks the
same way. On `main` both raise `TemplateNotFound` → caught → warning, no leak. Repro project:
`scratchpad/review4/A/`.

**Impact.** A template author (e.g. a docs-PR contributor, or any template whose include path
derives from context/external data) can exfiltrate arbitrary files readable by the build process
— CI secrets, SSH keys, `/etc/passwd` — into the published HTML, with no warning. Genuine sandbox
regression from swapping hardened `FileSystemLoader` for `template_base / name`.

**Fix direction.** In `_load_template`, reject absolute names and any with `..` segments, and
confirm `path.resolve()` is under `template_base.resolve()` (`is_relative_to`) before reading;
return `None` otherwise so minijinja emits its normal "template not found". Add a regression test
asserting `{% include "/etc/hostname" %}` and `{% include "../x" %}` warn rather than leak.

**Not a regression (checked):** include *resolution* is unchanged — a plain `partial.html`
referenced from a template named `sub/index` still maps to `template_base/partial.html`, matching
jinja2. Only the traversal guard was lost.

---

## F2 — MED — `:file:` with non-UTF-8 content crashes the build

**Where:** `src/sphinx_jinja2/__init__.py` (~L264-269).

```python
try:
    with open(source, encoding="utf8") as f:
        content = f.read()
except OSError as exc:            # UnicodeDecodeError is a ValueError, NOT OSError
    _warn(...); return []
```

A `:file:` target with non-UTF-8 bytes raises `UnicodeDecodeError`, which isn't an `OSError`, so it
propagates and Sphinx aborts (exit 2, full traceback). Repro `scratchpad/review4/B/`
(`bad.jinja` = `caf\xe9 {{ 1+1 }}`).

This block is unchanged from `main`, so the crash is **pre-existing** — but the PR made behavior
**inconsistent**: a bad-UTF-8 file pulled in via `{% include %}` hits the same `read_text("utf8")`
inside the loader, which is wrapped by the `render_str` catch-all, so it degrades to a graceful
warning (`scratchpad/review4/BU/`). Only the `:file:` option crashes. **Fix:** catch
`UnicodeDecodeError` (or read with `errors=`) so both paths warn. Add a test.

---

## M1 — MED — MyST `:file:` warning attribution is inert on myst-parser 5.x

**Where:** `src/sphinx_jinja2/__init__.py:304-328` (the reporter monkeypatch; code comment at L312
claims "so that any warnings/errors are correctly attributed").

**Defect.** The MyST branch temporarily overrides `document["source"]`, `reporter.source`, and
`reporter.get_source_and_line` to point at the template file. On **myst 4.0.1** that works
(`create_warning` logs `location=(document["source"], line)`). On **myst 5.1.0** it has *no effect*
on the logged location, because myst 5.x logs with `location=(document.settings.env.docname, line)`
— the docname, which the override never touches (`myst_parser/warnings_.py:129-131`).

**Failure scenario.** A MyST doc `index.md` with `` ```{jinja}\n:file: tmpl.jinja\n``` `` where
`tmpl.jinja` renders content with a parse problem (unknown role). On sphinx 9 / myst 5 the warning
is `index.md:3` (the directive line), not the template file. The RST path *is* tested to attribute
such warnings to `template.jinja:1` (`test_warning_from_file`), so the MyST path silently loses the
attribution the code comment promises — on the repo's own primary environment.

Evidence (`scratchpad/review2/warn_file`): myst5 → `index.md:3`; myst4 → `tmpl.jinja.rst:3`.

**Decision.** At minimum correct the overclaiming comment and document the limitation. Improving
attribution on myst 5.x would require reaching the docname-based location API and is likely not
worth deep integration; investigate briefly, else state the caveat. Not build-breaking.

---

## F3 — LOW/MED — bare `:raw:` silently parses instead of emitting raw

**Where:** `src/sphinx_jinja2/__init__.py:291` — `if raw_format := self.options.get("raw"):`.

`:raw:` is `directives.unchanged`, so a bare `:raw:` with no value yields `""` (falsy) → the raw
branch is skipped and content is parsed as normal source, no warning. The user asked for raw output
and silently got parsed/escaped output. Repro `scratchpad/review4/H1/`: bare `:raw:` with
`<b>raw {{ 1+1 }}</b>` → `<p>&lt;b&gt;raw 2&lt;/b&gt;</p>`. `:raw: html` works
(`review4/H2`). New code in this PR. **Fix:** warn when `:raw:` is given without a format.

---

## A1 / A2 — LOW — env-kwargs allowlist gaps; pass_context filters

- **A1.** Introspecting `minijinja.Environment.__init__`, every name in `_ENVIRONMENT_KWARGS` is
  valid (nothing wrongly included), but two legitimate constructor kwargs aren't exposable via
  `jinja2_env_kwargs`: **`path_join_callback`** (customizes include-path resolution — worth adding)
  and `reload_before_render` (irrelevant here — fresh env per directive). `loader`/`templates`/
  `filters`/`tests`/`globals` are correctly excluded (extension-managed). **Fix:** add
  `path_join_callback`.
- **A2.** Filters/tests are registered via `env.add_filter`/`add_test`, which accept any callable,
  but minijinja doesn't honor jinja2's `@pass_context` / `@pass_environment` / `@pass_eval_context`
  conventions. A jinja2 `@pass_context` filter used as `{{ 'x'|f }}` raises `TypeError` at render →
  caught → "Error rendering jinja template" warning (no crash, but a broken build with a confusing
  message for users migrating such filters). Inherent to the engine swap. **Document** as a
  migration caveat. Plain value-in/value-out filters/tests work correctly.

---

## M2 / M3 / C1 — LOW

- **M2.** `docs/index.rst` (~L187): "problems with the parsing of the rendered content always refer
  to the first line number either of the `jinja` directive, or the template file." True only for the
  RST `insert_input` branch (which stamps every line with `line - 1`). The MyST branch calls
  `nested_render_text(new_content, line)`, which maps token line numbers, so warnings point at the
  actual offset line inside the rendered content. Evidence `scratchpad/review2/warn_inline`: warning
  at `index.md:6`, neither the directive line (3) nor line 1. **Fix docs** to cover both paths.
- **M3.** `:debug:` node placement differs: RST emits the `jinja-rendered` `literal_block` before the
  parsed content; in MyST, a template heading moves `renderer.current_node` into the new section, so
  the debug block lands *inside* the template's last section rather than at directive level. Cosmetic
  (debug is a dev aid). Evidence `review2/rst_debug` vs `myst_debug` / `myst_debug_noh`. **Skip / note.**
- **C1.** `CONTRIBUTING.md` (~L17, pre-existing, not in the diff but in scope since the PR touched
  pre-commit config): "To install them, run:" is followed by a blank line and then the next heading —
  the install command is missing. **Fix** the instruction.

---

## F4 / F5 / F6 — LOW — deliberately not fixed

- **F4.** `jinja2_env_kwargs = "notdict"` → `AttributeError` on `.items()` → crash. Pre-existing
  (`main` crashes analogously on `**conf.env_kwargs`); Sphinx emits a config type-mismatch WARNING
  first. Marginal; optional guard only. **Skip.**
- **F5.** A `:file:` template that renders to a `.. jinja:: :file: <same file>` directive loops
  forever via `insert_input` re-processing (hung 90 s, killed). In the `insert_input` path, identical
  to `main`; requires a deliberately self-referential template; finite nesting terminates fine.
  **Skip** (out of scope).
- **F6.** `:file: ../../x` reads a file outside srcdir via `self.env.relfn2path` (which doesn't clamp
  `..`). Identical to `main`, author-controlled (path typed literally in the doc), and consistent with
  docutils' own `include` directive. Materially less severe than F1 (which is *loader*-side, not
  author-typed). Note the asymmetry: absolute `:file: /etc/hostname` *is* safely remapped to
  `srcdir/etc/hostname` by `relfn2path`. **Skip** (consistent by design).

---

## Surface verified sound (no defect)

Captured so the next agent doesn't re-litigate settled ground:

- **minijinja-py API usage correct.** `render_str(content, name, **ctx)` matches
  `(source, name=None, /, **ctx)`; positional-only `name`/`source` don't collide with ctx keys of
  those names (verified with `{'name': …}`, `{'source': …}`). `TemplateError.kind`/`.message` are
  real and well-formed for `UndefinedError` and `SyntaxError` kinds → the warning string is correct.
- **Strict undefined parity**, now overridable via `jinja2_env_kwargs = {"undefined_behavior": …}`
  (additive improvement; default set before the merge loop).
- **env_kwargs translation** correct: `finalize→finalizer` rename works; unsupported keys filtered
  with a helpful warning; env construction wrapped in try/except (old code raised uncaught `TypeError`
  on an unknown env kwarg). Invalid-but-well-typed values (`undefined_behavior="bogus"`, `fuel=-1`,
  `pycompat="x"`, conflicting delimiters) all degrade to warnings.
- **Dependency tracking** via the loader is a net improvement — records transitively-loaded templates
  (old `jinja2.meta.find_referenced_templates` static pass missed transitive includes → stale builds).
  `try/except/finally` notes deps on both success and error paths.
- **`_resolve_callable`** handles `mod:qual`, dotted `mod.func`, and non-string passthrough; bad
  inputs raise `ImportError`/`AttributeError` caught by the filter/test loops.
- **Exception safety of the MyST monkeypatch** is sound (originals captured before `try`; lambda
  always assigned before any raise; `finally` `del` can't `AttributeError` since `Reporter` has no
  such class attribute). Reentrancy verified (jinja-in-jinja in MyST builds cleanly).
- **RST `insert_input` path — no regression vs main.** Branch only entered when `state_machine` is a
  real `StateMachine` (MockStateMachine isn't a subclass); body identical to `main`; the
  admonition+heading `Unexpected section title` error reproduces identically on `main` (pre-existing
  `insert_input` limitation).
- **`get_source_info`/`set_source_info` under MockStateMachine** work on both myst versions;
  `:raw:` in MyST builds cleanly.
- **Config/packaging (Agent 3):** matrix+include yields exactly the intended 7 CI jobs (include
  entries overwrite the base `sphinx: ""` → become *new* standalone jobs, they don't modify the base
  4); flit-core `>=3.11` is the precise PEP 639 floor (3.11.0 builds `License-Expression: MIT`,
  3.10.1 fails); `myst-parser` unpinned resolves cleanly against the `sphinx~=7.2` job (backtracks to
  4.0.1); all version floors agree across pyproject/tox/CI/RTD/pre-commit; trusted-publishing setup
  correct (`id-token: write`, `environment: pypi`, no password); every migration claim in the docs
  verified true against minijinja 2.21.0 (`None`→`none`, missing filters list, pycompat method calls,
  lenient undefined); `.readthedocs.yml` schema valid with the added `sphinx.configuration`.
- **Adversarial surface that behaved correctly:** ctx abuse (`null`/`[]`/non-dict → warning; `env`/
  `self` collision handled), non-dict/object context values, invalid filters/tests (non-callable →
  warning), recursion guards (minijinja recursion guard on self-include), option combos
  (`:raw: html`+`:debug:`, `:file:` at a directory → `IsADirectoryError` caught, empty directive),
  MyST nesting/empty/heading-levels/directive-emit, **parallel build `-j 4`** across 12 docs sharing a
  template+context (no pickle/serialization issues — `parallel_read_safe=True` holds), and output edge
  cases (CRLF, 100k-char line, heading-only).

---

## Maintainer deep-analysis (independent of the agents)

My own pass reached the same three top issues before the agents reported (F1 path traversal, F3 empty
`:raw:`, changelog date), and I'd pre-cleared the items the agents also cleared: duplicate
`note_dependency` (Sphinx dedups), invalid `undefined_behavior` (caught), the `finally` `del`
(attribute always set first), CI `include` semantics (new jobs, not overwrites), and empty output
(same path as old code). The agents added what a solo pass missed: the *absolute-path* half of F1
(I'd focused on `..`), the F2 `:file:`/include inconsistency, and the myst-5.x attribution gap (M1) —
each of which needed building a real project on both myst versions to see. This is the case for the
"agents **and** deep-thinking" rule: the deep pass set the priorities and caught the blocker's shape;
the agents supplied breadth and the cross-version empiricism.

### On "is the nested parsing done the best way possible?"

- **RST (`insert_input`):** yes, and defensibly so — it's what docutils' own `include` uses and the
  only path giving the full contract (true section levels, following content joining injected sections,
  per-line source attribution → `template.jinja:1` errors). Sphinx 7.4+'s public
  `parse_text_to_nodes(allow_section_headings=True)` is the "clean" alternative but has *contained*
  semantics (sections force-closed at the boundary, per-line attribution lost) — right for a component
  directive, a regression for template inclusion.
- **MyST (`nested_render_text`):** best *available*, not best *possible*. It copies myst's own
  `MockIncludeDirective` and gives correct section order/nesting — but reaches a private
  `state._renderer` and monkeypatches the reporter (and per M1 the monkeypatch doesn't even achieve its
  goal on myst 5.x). The genuinely clean route — `MockState.nested_parse(match_titles=True)` into a
  container — is blocked by an upstream myst bug: `nested_render_text(temp_root_node=...)` snapshots
  `_level_to_section` for restore but never re-roots it, so contained sections escape and reorder
  (verified). Filing that upstream (see `HANDOFF.md` §3c) is the path to a better implementation.

---

## Repro artifacts

Scratch projects the agents built (under `scratchpad/`):
`review1/` (core probes), `review2/` (MyST: `warn_file`, `warn_inline`, `rst_debug`, `myst_debug*`,
`rst_in_admonition`, `myst_*`), `review3/` (packaging/docs build tests),
`review4/` (adversarial: `A` path-traversal, `B`/`BU` utf8, `H1`/`H2` raw, `D2` hang, `FT` file-opt,
`CX`, `E_nondict`, …).
