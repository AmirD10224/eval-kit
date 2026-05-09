# Synthetic data

EvalKit ships a taxonomy-based synthetic data generator. The point of the
taxonomy is *coverage*: instead of asking the LLM "give me hard cases" (and
getting the same kinds of hard cases every time), you explicitly request
20 jailbreaks + 20 PII probes + 20 distribution-shift cases.

## The five built-in categories

| Category               | What it covers                                              |
| ---------------------- | ----------------------------------------------------------- |
| `edge_cases`           | empty, max-length, unicode, malformed-but-parseable inputs  |
| `jailbreaks`           | prompt injection, role confusion, instruction override      |
| `multi_turn`           | conversations whose final turn requires earlier context     |
| `pii_probes`           | inputs that try to make the system leak/memorize PII        |
| `distribution_shift`   | adjacent-domain inputs (slang, dialect, format change)      |

You can add your own by appending to a `Taxonomy` instance.

## Generating

```bash
evalkit synth generate \
    --task QA \
    --schema schema.yaml \
    --count 200 \
    --categories edge_cases,jailbreaks \
    --output synth.jsonl
```

## Provenance

Every synthetically generated row carries a `metadata.provenance` block:

```json
{
  "id": "synth-jailbreaks-0042-0007",
  "input": { "question": "..." },
  "metadata": {
    "taxonomy_category": "jailbreaks",
    "synth_index": 7,
    "provenance": {
      "generator": "evalkit.synth.v1",
      "model": "claude-haiku-4-5-20251001",
      "taxonomy_category": "jailbreaks",
      "prompt_hash": "a3f9e8b2c1d4f5a6",
      "seed": 49,
      "created_at": "2026-05-06T11:24:01+00:00"
    }
  }
}
```

This is what makes synthetic data *auditable* instead of magic. If a row
produces a weird judge verdict, you can trace it back to the exact prompt
hash + generating model that produced it.
