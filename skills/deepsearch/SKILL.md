---
name: deepsearch
description: Thorough codebase search
---

# Deep Search Skill

[DEEPSEARCH MODE ACTIVATED]

Perform thorough search of the codebase for the specified query, pattern, or concept.

## When to Use

This skill activates when:
- User wants comprehensive search results
- User says "deepsearch", "search deeply", "thorough search"
- Simple grep/find isn't finding all occurrences
- Need to understand usage patterns

## Search Strategy

### 1. Broad Search
- Search for exact matches
- Search for related terms and variations
- Check common locations (components, utils, services, hooks)

### 2. Deep Dive
- Read files with matches
- Check imports/exports to find connections
- Follow the trail (what imports this? what does this import?)

### 3. Synthesize
- Map out where the concept is used
- Identify the main implementation
- Note related functionality

## Output Format

- **Primary Locations** - Main implementations
- **Related Files** - Dependencies, consumers
- **Usage Patterns** - How it's used across codebase
- **Key Insights** - Patterns, conventions, gotchas

Focus on being comprehensive but concise. Cite file paths and line numbers.

## Example Output

```
PRIMARY LOCATIONS
- src/services/AuthService.ts (lines 42-89) - Main implementation
- src/hooks/useAuth.ts (lines 12-34) - React hook wrapper

RELATED FILES  
- src/types/auth.ts - Type definitions
- src/__tests__/auth.test.ts - Test coverage

USAGE PATTERNS
- Most services instantiate AuthService in constructor
- Hook pattern preferred in React components

KEY INSIGHTS
- Uses singleton pattern for service instance
- Token refresh handled automatically
```

## Keywords

- deepsearch, deep search, thorough search
- find all, search everywhere
- investigate, explore codebase
