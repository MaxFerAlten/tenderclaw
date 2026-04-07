---
name: git-master
description: Git expert for atomic commits, rebasing, and history management
---

# Git Master Skill

Git expert for atomic commits, rebasing, and history management.

## When to Use

This skill activates when:
- User wants help with complex git operations
- User says "git master", "git expert"
- Need atomic commits, interactive rebase, or history cleanup
- Branch management tasks

## Capabilities

### Atomic Commits
- Conventional commit format
- Logical grouping of changes
- Clear commit messages with scope

### Interactive Rebasing
- Squash related commits
- Reorder for logical history
- Fixup/autosquash for WIP commits

### Branch Management
- Feature branch creation
- Branch cleanup and merging
- Protection policy enforcement

### History Management
- Selective history rewriting
- Commit archaeology
- Blame analysis

### Style Detection
- Analyze existing commit style
- Match project conventions

## Common Operations

### Create Feature Branch
```bash
git checkout -b feature/my-feature
git add .
git commit -m "feat(scope): add my feature"
```

### Interactive Rebase
```bash
git rebase -i HEAD~5
```

### Squash Commits
```
pick abc123 First commit
squash def456 Second commit
squash ghi789 Third commit
```

### Amend Last Commit
```bash
git commit --amend
```

### View History
```bash
git log --oneline --graph
git log --stat
```

## Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: feat, fix, docs, style, refactor, test, chore

## Best Practices

1. **Atomic commits** - One logical change per commit
2. **Descriptive messages** - Explain WHY, not just WHAT
3. **Small commits** - Easier to review and revert
4. **Test before commit** - Ensure changes work
5. **Never force push main** - Use merge or rebase

## Keywords

- git master, git expert
- atomic commit, interactive rebase
- squash commits, branch management
- git history, commit style

## Example Workflows

### Feature Development
```
1. Create feature branch
2. Make small, focused commits
3. Rebase to clean up
4. Merge with squash
```

### Bug Fix
```
1. Create fix branch from main
2. Make atomic commits
3. Test thoroughly
4. Fast-forward merge to main
```

### Release Preparation
```
1. Update version
2. Create release branch
3. Tag and merge
4. Clean up old branches
```
