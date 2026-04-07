---
name: web-clone
description: URL-driven website cloning with visual + functional verification
---

# Web Clone Skill

Clone a target website from its URL, replicating visual appearance and core interactive functionality.

## When to Use

This skill activates when:
- User provides a target URL and wants the site replicated
- User says "clone site", "clone website", "copy webpage", "web-clone"
- Task requires both visual fidelity AND functional parity

## Scope (v1)

**Included:**
- Layout structure (header, nav, content areas, sidebar, footer)
- Typography (font families, sizes, weights)
- Colors, spacing, borders, border-radius
- Core interactions: navigation, buttons, forms, dropdowns, modals

**Excluded:**
- Backend API integration
- Authentication flows
- Dynamic/personalized content
- Multi-page crawling
- Third-party widgets

**Legal notice**: Only clone sites you own or have permission to replicate.

## Prerequisites

Browser automation required (Playwright MCP):
```
codex mcp add playwright npx "@playwright/mcp@latest"
```

## Passes

### Pass 1 - Extract
1. Navigate to target URL
2. Take accessibility snapshot (structural reference)
3. Take full-page screenshot (visual baseline)
4. Extract DOM + computed styles
5. Catalog interactive elements

### Pass 2 - Build Plan
1. Identify page regions (nav, main, footer, sidebar)
2. Map components with style properties
3. Create interaction map
4. Extract design tokens (colors, fonts, spacing)

### Pass 3 - Generate Clone
1. Scaffold directory structure
2. Implement design tokens
3. Build layout shell
4. Implement components
5. Wire up interactions
6. Add responsive rules

### Pass 4 - Verify
1. Serve clone locally
2. Visual verification (score >= 85)
3. Structural verification (landmark counts)
4. Functional spot-check (2-3 interactions)

### Pass 5 - Iterate
1. Prioritize fixes by impact
2. Apply targeted edits
3. Re-verify until pass or max 5 iterations

## Output Contract

```json
{
  "visual": {
    "score": 0,
    "verdict": "revise",
    "category_match": false,
    "differences": ["..."],
    "suggestions": ["..."]
  },
  "functional": {
    "tested": 0,
    "passed": 0,
    "failures": ["..."]
  },
  "structure": {
    "landmark_match": false,
    "missing": ["..."]
  },
  "overall_verdict": "revise",
  "priority_fixes": ["..."]
}
```

## Keywords

- clone site, clone website, web-clone
- copy webpage, replicate site
