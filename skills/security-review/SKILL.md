---
name: security-review
description: Security audit for vulnerabilities
trigger: security-review
---

# Security Review

## Check Areas
- **Authentication**: Auth mechanisms secure?
- **Authorization**: Proper access controls?
- **Input Validation**: Sanitize all inputs?
- **Output Encoding**: XSS protection?
- **Cryptography**: Secure storage/transmission?
- **Dependencies**: Known vulnerabilities?

## Common Issues
- SQL Injection
- XSS / CSRF
- Broken Authentication
- Sensitive Data Exposure
- Security Misconfiguration
- Insecure Dependencies

## Output Format
### Vulnerabilities Found
| Severity | Type | Location | Description | Fix |
### Security Score
### Recommendations

Task: {{ARGUMENTS}}
