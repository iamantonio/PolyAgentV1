# AI WORKFLOW
**Purpose:** One-page guide for collaborators working with AI assistants on this codebase.

## Core Principle
**Files are law; chat is suggestion.**

If an AI response contradicts SYSTEM_INVARIANTS.md or DECISIONS.md, the files win. Always.

## Session Management

### Starting a Session
1. **First serious session of the day:** Run SESSION_PREFLIGHT.md
2. **Quick fixes/small changes:** Can skip preflight, but read relevant DECISIONS first
3. **Risky changes (security, money, blockchain):** ALWAYS run preflight, no exceptions

### During a Session
- **Two-session rule:** If a decision survives two work sessions, log it in DECISIONS.md
- **Magic numbers:** If you add a threshold/timeout/limit, create a decision entry
- **Violated invariant:** Update SYSTEM_INVARIANTS.md first, OR don't make the change

### After Long Breaks
- **Hours/days gap:** Run SESSION_RESET.md before continuing
- **Context feels off:** Reset immediately, don't push through

### When AI Drifts
Signs of drift:
- Contradicts prior decisions
- Suggests disabling safety checks
- Unaware of project-specific constraints
- Generic advice that doesn't fit architecture

**Action:** Stop. Run SESSION_RESET.md. Verify AI reloaded context correctly.

## Decision Protocol

### When to create a decision (DECISIONS.md)
1. **Threshold met:**
   - Survives 2+ sessions, OR
   - Touches safety/security/cost/data, OR
   - Introduces magic number, OR
   - Rejects tempting alternative

2. **Format:** Use template from DECISIONS.md

3. **Update changelog:** Add entry to CHANGELOG_DECISIONS.md

### When to update an invariant (SYSTEM_INVARIANTS.md)
1. **Hard rule changes:**
   - New security policy
   - Data boundary modification
   - Operational limit adjustment
   - New failure mode discovered

2. **Devil's advocate rule:**
   - If change violates invariant → update invariant FIRST
   - No "just this once" exceptions
   - If you can't justify invariant update → don't make the change

## Code Review Checklist

### Before submitting PR
- [ ] Does this change any decisions? Update DECISIONS.md
- [ ] Does this violate any invariants? Update SYSTEM_INVARIANTS.md or reject change
- [ ] New magic numbers? Document in DECISIONS.md
- [ ] Touches safety-critical code? Run preflight and include rationale in PR
- [ ] Changes to trading logic? Verify trade execution still commented out
- [ ] New API integration? Document rate limits, auth, failure modes

### Reviewing someone's PR
- [ ] Check if DECISIONS.md updated for policy changes
- [ ] Verify SYSTEM_INVARIANTS.md still holds
- [ ] Look for undocumented magic numbers
- [ ] Confirm safety checks not weakened
- [ ] Verify no secrets committed

## Quick Reference: File Roles

| File | Purpose | When to Update |
|------|---------|----------------|
| SYSTEM_INVARIANTS.md | Hard rules that never bend | New policies, boundaries, limits |
| DECISIONS.md | Why we chose X over Y | Any non-trivial choice that will recur |
| CHANGELOG_DECISIONS.md | Audit trail of changes | Every DECISIONS.md update |
| SESSION_PREFLIGHT.md | Safety check template | Never (it's a template) |
| SESSION_RESET.md | Context reload template | Never (it's a template) |
| CLAUDE.md | Architecture guide | Structural changes, new commands |
| AI_WORKFLOW.md | This file | Workflow improvements |

## Anti-Patterns to Avoid

**❌ "AI said it's fine"**
- Files > AI opinion, always

**❌ "I'll document it later"**
- Document decisions when made, not after

**❌ "Just this once bypass"**
- Bypasses become habits, update invariants properly or don't bypass

**❌ "Too small to document"**
- If you're debating whether to document, document it

**❌ "AI knows the context"**
- After compaction/drift, AI knows nothing. Files are memory.

## Workflow Examples

### Example 1: Adding New Feature (Twitter Sentiment)

1. **Start:** Run SESSION_PREFLIGHT.md
2. **Preflight output:** "Need to understand rate limits, API cost, failure modes"
3. **Research:** Check Twitter API limits, cost
4. **Decision:** Create D-008 documenting Twitter API choice, rate limits, timeout
5. **Implement:** Add TwitterConnector class
6. **Update:** Add Twitter to SYSTEM_INVARIANTS.md source-of-truth data section
7. **Commit:** Include D-008 and invariant updates in same commit

### Example 2: Fixing Token Overflow Bug

1. **Bug found:** Token estimation fails on very large market lists
2. **Fix:** Adjust chunking threshold from 80% to 70%
3. **Decision:** Update D-005 to reflect new threshold and rationale
4. **Changelog:** Add entry to CHANGELOG_DECISIONS.md
5. **Commit:** Reference D-005 in commit message

### Example 3: AI Suggests Disabling Trade Safety

**AI:** "To test faster, we could uncomment the trade execution line"

**Correct response:**
1. **Stop.** This violates D-002.
2. **Check:** Is there a valid reason to change D-002?
3. **If yes:** Update D-002 first, document why, then proceed
4. **If no:** Reject suggestion, explain D-002 to AI

## Integration with Development Tools

### Pre-commit Hooks
- Black formatter (enforced)
- Consider adding: DECISIONS.md linter (check for D-XXX references in changed files)

### Git Commit Messages
- Reference decision numbers: `feat: Add Twitter sentiment (D-008)`
- Flag invariant updates: `fix: Update token threshold (D-005, INVARIANTS updated)`

### Code Comments
- Link to decisions: `// See D-005 for token chunking strategy`
- Don't duplicate decision content in code (DRY - decisions are source of truth)

## Tips for Effective AI Collaboration

1. **Be explicit about constraints:** Tell AI to read SYSTEM_INVARIANTS.md before suggesting changes
2. **Reference decisions:** "How would D-005 apply here?" instead of re-explaining
3. **Catch drift early:** First generic response = time to reset
4. **Trust the files:** If AI and files disagree, files are always right
5. **Update as you go:** Don't accumulate "I should document this" debt

## Quarterly Maintenance

Every 3 months, review:
- [ ] Are all ACTIVE decisions still relevant?
- [ ] Any DEPRECATED decisions to remove?
- [ ] SYSTEM_INVARIANTS.md still accurate?
- [ ] CHANGELOG_DECISIONS.md showing concerning churn?
- [ ] New failure modes to document?

---

**Remember:** This system works because files persist and AI context doesn't. Invest in files, reap benefits across all sessions.
