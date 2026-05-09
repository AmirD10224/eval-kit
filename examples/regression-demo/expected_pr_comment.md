<!-- evalkit:pr-comment -->
## EvalKit report

### ❌ 1 metric regressed beyond 5.0pp threshold

| Metric | Baseline | Current | Δ | Status |
|---|---:|---:|---:|:---:|
| `answer_relevancy` | 0.812 | 0.835 | +2.3pp | ✅ |
| `closed_book` | 0.733 | 0.733 | +0.0pp | ▪️ |
| `faithfulness` | 0.847 | 0.713 | -13.4pp | ❌ |
| `idk_when_no_ctx` | 0.967 | 0.967 | +0.0pp | ▪️ |

<details><summary>Run metadata</summary>

**baseline**
- `git_sha`: `be0bdb2c11f9d3a4b5e6c7d8e9f0a1b2c3d4e5f6`
- `judge_model`: `claude-haiku-4-5-20251001`
- `n_samples`: `30`
- `suite`: `qa-rag`
- `timestamp`: `2026-05-05T17:42:11+00:00`

**current**
- `git_sha`: `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0`
- `judge_model`: `claude-haiku-4-5-20251001`
- `n_samples`: `30`
- `suite`: `qa-rag`
- `timestamp`: `2026-05-06T09:14:02+00:00`

</details>


<sub>Posted by [EvalKit](https://github.com/AmirD10224/eval-kit) · threshold: 5.0pp</sub>