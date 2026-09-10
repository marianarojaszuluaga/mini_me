# qa/evidence/

Output of `app/services/qa_e2e_runner.py` (QA-E2E agent, Tarea 3,
PLAN-qa-automation.md). Each run writes a folder `qa/evidence/<run_id>/`
with `plan.json` (the input), `report.json` (findings in the
`app/schemas/qa.py` `Finding` schema), and `final.png` (screenshot) when a
real browser run executed.

**Requires Playwright's Chromium browser to be installed to actually run**:

```
pip install -e ".[test]"
playwright install chromium
```

This was intentionally NOT done as part of this pass — only the dependency
and the runner code are in place. Without the browser installed, `run_plan()`
still runs end-to-end and returns a single S1 `Finding` explaining the
missing browser, instead of crashing.

Run folders are generated artifacts — safe to delete; not meant to be
committed to git as a rule (add a `.gitignore` entry here if this starts
generating noise in PRs).
