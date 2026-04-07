---
name: visual-verdict
description: Structured visual QA verdict for screenshot-to-reference comparisons
---

# Visual Verdict Skill

Compare generated UI screenshots against reference images and return a JSON verdict.

## When to Use

This skill activates when:
- Task includes visual fidelity requirements (layout, spacing, typography)
- You have a generated screenshot and at least one reference image
- You need deterministic pass/fail guidance before continuing

## Inputs

- `reference_images[]` - One or more image paths
- `generated_screenshot` - Current output image
- `category_hint` - Optional category (e.g., dashboard, sns-feed)

## Output Contract

Return JSON only:

```json
{
  "score": 0,
  "verdict": "revise",
  "category_match": false,
  "differences": ["..."],
  "suggestions": ["..."],
  "reasoning": "short explanation"
}
```

Rules:
- `score`: integer 0-100
- `verdict`: `pass`, `revise`, or `fail`
- `differences[]`: concrete visual mismatches
- `suggestions[]`: actionable next edits
- `reasoning`: 1-2 sentence summary

## Threshold

- Target pass threshold: **90+**
- If `score < 90`, continue editing and rerun visual-verdict

## Debug Visualization

When mismatch diagnosis is hard:
1. Use `$visual-verdict` as the authoritative decision
2. Use pixel-level diff tooling as secondary debug aid
3. Convert diff hotspots into concrete suggestions

## Example

```json
{
  "score": 87,
  "verdict": "revise",
  "category_match": true,
  "differences": [
    "Top nav spacing is tighter than reference",
    "Primary button uses smaller font weight"
  ],
  "suggestions": [
    "Increase nav item horizontal padding by 4px",
    "Set primary button font-weight to 600"
  ],
  "reasoning": "Core layout matches, but style details still diverge."
}
```

## Keywords

- visual verdict, visual check, screenshot comparison
- compare screenshots, visual diff
