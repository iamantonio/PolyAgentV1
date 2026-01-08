# SESSION PRE-FLIGHT CHECKLIST
Run this:
- Start of any serious session
- Before risky changes (security, money, data, prod)
- When resuming after a break
- When answers feel too confident

## Copy/Paste Prompt
```
You are working on an existing system.

Before doing ANY implementation or suggestions, perform a pre-flight check:

1. Restate the core purpose of this project in 1–2 sentences.
2. List the non-negotiable constraints from SYSTEM_INVARIANTS.md that apply.
3. List known failure modes we must avoid.
4. Explicitly state what you are NOT allowed to optimize for (anti-goals).
5. List all assumptions you are making right now.
6. Label each assumption as:
   - Verified (from files)
   - Plausible but uncertain
   - Unknown

Rules:
- If information is missing, say so explicitly.
- Do NOT fill gaps optimistically.
- Do NOT proceed to solutions yet.

End with:
"Pre-flight complete. Safe to proceed: YES / NO / PARTIAL"
```

## When to Run This

### Always Required
- Before uncommenting trade execution code
- Before modifying wallet/private key handling
- Before changing API authentication logic
- Before altering order signing/submission
- Before modifying rate limiting or timeout logic

### Strongly Recommended
- After a break of several hours/days
- When working on unfamiliar parts of codebase
- Before refactoring core trading logic
- When adding new external API integrations
- Before making changes to Pydantic models (data contracts)

### Optional But Helpful
- When starting to implement a new feature
- After reviewing someone else's PR
- When debugging unexpected behavior
- When answers from AI feel generic or uncertain

## Red Flags That Should Trigger Preflight

- AI suggests "just temporarily disable" a safety check
- Proposed changes touch multiple system boundaries
- Solution involves "we can just assume..."
- Changes to magic numbers without explanation
- Modifications to blockchain contract addresses
- Alterations to token limits or chunking logic

## Example Session Start

**User:** "I want to add a new trading strategy that uses Twitter sentiment"

**Before proceeding, run preflight:**
1. What is this project and what constraints apply?
2. What failure modes exist around external APIs?
3. What anti-goals must I respect (e.g., no black-box trading)?
4. What assumptions am I making about Twitter API, rate limits, sentiment accuracy?

**Then:** If preflight = YES, proceed. If PARTIAL, clarify gaps. If NO, stop and reset.
