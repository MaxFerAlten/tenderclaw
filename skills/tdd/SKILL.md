# /tdd — Test-Driven Development Skill

## Trigger
`/tdd <feature description>`

## Agents
- **sisyphus** (primary): Write tests then implementation
- **momus** (verify): Ensure tests are meaningful

## Flow
1. Write failing tests first based on the feature description.
2. Run tests to confirm they fail.
3. Implement the minimum code to make tests pass.
4. Run tests to confirm they pass.
5. Refactor if needed (tests must still pass).

## Rules
- Tests must be written BEFORE implementation code.
- Each test must fail before the corresponding code is written.
- No skipping the red-green-refactor cycle.
