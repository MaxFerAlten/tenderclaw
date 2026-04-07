---
name: build-fix
description: Fix build and TypeScript errors with minimal changes
---

# Build Fix Skill

Fix build and compilation errors quickly with minimal code changes. Get the build green without refactoring.

## When to Use

This skill activates when:
- User says "fix the build", "build is broken"
- TypeScript compilation fails
- Build command or type checker reports errors
- User requests "minimal fixes" for errors

## What It Does

### 1. Collect Errors
- Run project's type check command (tsc --noEmit, mypy, cargo check, etc.)
- Or run build command to get failures
- Categorize errors by type and severity

### 2. Fix Strategically
- Add type annotations where missing
- Add null checks where needed
- Fix import/export statements
- Resolve module resolution issues
- Fix linter errors blocking build

### 3. Minimal Diff Strategy
- NO refactoring of unrelated code
- NO architectural changes
- NO performance optimizations
- ONLY what's needed to make build pass

### 4. Verify
- Run type check command after each fix
- Ensure no new errors introduced
- Stop when build passes

## Agent Delegation

```
Role: build-fixer (STANDARD tier)

Requirements:
- Run tsc/build to collect errors
- Fix errors one at a time
- Verify each fix doesn't introduce new errors
- NO refactoring, NO architectural changes
- Stop when build passes
```

## Output Format

```
BUILD FIX REPORT
===============

Errors Fixed: 12
Files Modified: 8
Lines Changed: 47

Fixes Applied:
1. src/utils/validation.ts:15 - Added return type annotation
2. src/components/Header.tsx:42 - Added null check for props.user
3. src/api/client.ts:89 - Fixed import path

Final Build Status: PASSING
Verification: tsc --noEmit (exit code 0)
```

## Keywords

- fix the build, build is broken
- fix type errors, type errors
- build failing, compilation error

## Stop Conditions

- Type check command exits with code 0
- Build command completes successfully
- No new errors introduced

## Combine with Other Skills

**With $ralph:**
```
$ralph fix the build
```
Keeps trying until build passes.

**With $ultraqa:**
```
$ultraqa fix build errors
```
QA cycling for build fixes.

**With $team:**
```
$team fix all build errors
```
Explore → build-fixer → verifier workflow.
