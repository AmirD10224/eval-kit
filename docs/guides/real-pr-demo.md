# Producing a real PR auto-reject screenshot

10 minutes, four steps. The result is the screenshot at the top of the
README. but from a real PR on a real GitHub repo, not the mock renderer.

## 1. Create a fresh repo

```bash
gh repo create eval-kit-demo --public --clone
cd eval-kit-demo
cp -r ../eval-kit/examples/regression-demo/. .
git add . && git commit -m "init: regression-demo suite + golden + toy app"
git push -u origin main
```

This pulls in `suite.yaml`, `rubrics/faithfulness.yaml`, `golden.jsonl`,
`app.py`, and the pre-computed `baseline.json`, everything the action
needs to produce a PR comment.

## 2. Wire up the EvalKit action

Drop this into `.github/workflows/eval.yml`:

```yaml
name: eval
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: AmirD10224/eval-kit@v0.1.0
        with:
          suite: ./suite.yaml          # ← the suite from regression-demo
          baseline: ./baseline.json    # ← pre-computed baseline
          fail-on-regression: 5
```

Don't forget to add `ANTHROPIC_API_KEY` as a repo secret.

## 3. Open the regressing PR

```bash
git checkout -b drop-faithfulness
# Edit a prompt or the toy app to drop faithfulness intentionally.
git commit -am "Tweak retrieval prompt for better recall"
git push origin drop-faithfulness
gh pr create --title "Tweak retrieval prompt for better recall" \
             --body "Trying a new retriever to improve recall."
```

## 4. Wait for the action, then screenshot

Once the action runs, the PR will have:

1. A failing check: ❌ EvalKit / metrics
2. A bot comment with the metric diff table

Take a screenshot covering both. That's the marketing asset.

## Tips

- For a tighter screenshot, collapse the file tree and use a viewport ~960
  pixels wide.
- `https://github.com/<owner>/<repo>/pull/<n>?notification_referrer_id=`
  removes the side rail on dark mode for a cleaner shot.
- macOS: `Shift + Cmd + 4`, then space, then click the comment frame to
  capture exactly that element.
