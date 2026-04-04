# /review — Code Review Skill

## Trigger
`/review [file_path | git diff]`

## Agents
- **momus** (primary): Code review and critique
- **sentinel** (security): Security-focused review

## Flow
1. Read the target code or diff.
2. Check for: bugs, logic errors, security issues, style violations, performance.
3. Produce a structured review with severity levels.

## Output Format
```
## Review: <file or PR>

### Critical
- [line:N] description — suggested fix

### Warning
- [line:N] description — suggestion

### Nit
- [line:N] description — optional improvement

### Security
- [finding] description — risk level — mitigation
```
