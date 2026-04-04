# /security — Security Audit Skill

## Trigger
`/security [scope]`

## Agents
- **sentinel** (primary): Security audit
- **explorer** (support): Codebase search for patterns

## Checklist
1. **Secrets**: Scan for hardcoded API keys, tokens, passwords.
2. **Injection**: Check for SQL injection, XSS, command injection.
3. **Auth**: Verify authentication and authorization logic.
4. **Dependencies**: Check for known vulnerable packages.
5. **Input Validation**: Ensure all user input is validated at boundaries.

## Output Format
```
## Security Audit: <scope>

### Findings
| Severity | Location | Issue | Recommendation |
|----------|----------|-------|----------------|
| HIGH | file:line | desc | fix |
| MEDIUM | file:line | desc | fix |

### Summary
- X critical, Y warnings, Z informational
```
