# CHANGELOG_DECISIONS
Whenever you change a magic number, safety constraint, or policy:
- add/modify a decision in DECISIONS.md
- reference it here with date + PR/commit

## Format
```
YYYY-MM-DD | D-XXX | Brief change | PR/Commit | Author
```

## Log

2024-01-01 | D-001 | Python 3.9 requirement | Initial commit | @polymarket
2024-01-01 | D-002 | Trade execution disabled by default | Initial commit | @polymarket
2024-01-01 | D-003 | Ephemeral local RAG databases | Initial commit | @polymarket
2024-01-01 | D-004 | LangChain + ChromaDB for RAG | Initial commit | @polymarket
2024-01-01 | D-005 | Token chunking strategy | PR #23 | @testpower4
2024-01-01 | D-006 | Typer for CLI framework | Initial commit | @polymarket
2024-01-01 | D-007 | Black for code formatting | Initial commit | @polymarket

---

## Usage Examples

**When to add an entry:**
- Changed token limit threshold (4 chars/token → different ratio)
- Modified database cleanup behavior
- Updated API endpoints or contract addresses
- Changed rate limiting logic
- Adjusted safety timeouts
- Modified wallet approval logic
- Changed embedding model
- Updated LLM model defaults

**What NOT to log here:**
- Regular bug fixes (unless they change a policy)
- New features that don't alter existing decisions
- Documentation updates
- Dependency version bumps (unless they force architectural change)
- Refactoring that preserves behavior

**Template for adding new decision:**

1. Create/update decision in DECISIONS.md
2. Add line here: `YYYY-MM-DD | D-XXX | Summary | PR#123 | @username`
3. Commit both files together

**Pro tip:** Review this file quarterly to spot decision churn. If D-XXX changes 3+ times in 6 months, it might be unstable and need deeper analysis.
