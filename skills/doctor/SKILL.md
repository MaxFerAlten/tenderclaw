---
name: doctor
description: Diagnose and fix TenderClaw installation issues
---

# Doctor Skill

Diagnose and fix TenderClaw installation issues.

## When to Use

This skill activates when:
- User says "doctor", "diagnose", "fix installation"
- Installation issues suspected
- Plugin not loading correctly

## Diagnostic Checks

### 1. Check Plugin Status

```bash
# Check if superpowers plugin is loaded
ls backend/plugins/

# Check if skills are loaded
ls skills/
```

**Diagnosis**:
- If plugins missing: CRITICAL - plugins not installed
- If skills missing: WARN - some skills not ported

### 2. Check Configuration

```bash
# Check config files
ls -la backend/*.json
ls -la frontend/src/config/
```

**Diagnosis**:
- Missing config: WARN - may need setup
- Invalid JSON: CRITICAL - configuration error

### 3. Check Dependencies

```bash
# Python dependencies
pip list | grep -E "(fastapi|uvicorn|pydantic)"

# Node dependencies
cd frontend && npm list
```

**Diagnosis**:
- Missing packages: WARN - need to install
- Outdated packages: WARN - consider updating

### 4. Check Import Paths

```bash
# Test Python imports
python -c "from backend.plugins.superpowers import SuperpowersPlugin"
python -c "from backend.core.keyword_detection import KeywordDetector"
```

**Diagnosis**:
- Import errors: CRITICAL - code needs fixing

### 5. Check Frontend Build

```bash
cd frontend && npm run build
```

**Diagnosis**:
- Build errors: WARN - TypeScript issues
- Build success: OK

### 6. Check Backend Startup

```bash
# Test backend loads
python -c "from backend.main import app"
```

**Diagnosis**:
- Startup errors: CRITICAL - needs investigation

## Report Format

```
TENDERCLAW DOCTOR REPORT
=======================

### Summary
[HEALTHY / ISSUES FOUND]

### Checks

| Check | Status | Details |
|-------|--------|---------|
| Plugins | OK/CRITICAL | ... |
| Configuration | OK/WARN/CRITICAL | ... |
| Dependencies | OK/WARN | ... |
| Import Paths | OK/CRITICAL | ... |
| Frontend Build | OK/WARN | ... |
| Backend Startup | OK/CRITICAL | ... |

### Issues Found
1. [Issue description]
2. [Issue description]

### Recommended Fixes
[List fixes based on issues]
```

## Auto-Fix

If issues found, ask user: "Would you like me to fix these issues?"

Apply fixes:
- Missing dependencies: Run pip install / npm install
- Import errors: Fix Python path issues
- Build errors: Run typecheck and fix errors

## Post-Fix

After applying fixes, run verification:
```
Doctor: Running verification...
Doctor: All checks passed.
```

## Keywords

- doctor, diagnose, fix installation
- check health, health check
- troubleshooting, debug setup
