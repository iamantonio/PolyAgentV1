# SESSION RESET PROTOCOL
Use when:
- You suspect compaction or drift
- Pre-flight fails
- Resuming after hours/days
- The assistant contradicts prior decisions
- Responses feel "off" or too confident

## Copy/Paste Prompt
```
Context may be lost or corrupted. Perform a full session reset.

Step 1: Read Sources of Truth
Read these files in order:
1) SYSTEM_INVARIANTS.md
2) DECISIONS.md
3) CLAUDE.md
4) README.md

Step 2: State What You Now Know
After reading, explicitly state:
- Project purpose (1–2 sentences)
- Top 5 invariants that constrain changes
- The most recent 3 ACTIVE decisions
- Current environment assumptions (DEV/STAGING/PROD) if known

Step 3: State What You Do NOT Know
List gaps without guessing.

Step 4: Declare Assumptions
List assumptions and label each:
- Verified
- Inferred (reasonable but not explicit)
- Unknown

Step 5: Continuation Decision
Answer: "Safe to continue: YES / NO / PARTIAL"
If PARTIAL, list what must be clarified before touching risky code.
```

## When to Use This

### Mandatory Reset Triggers
- AI contradicts SYSTEM_INVARIANTS.md
- AI suggests changing a decision without updating DECISIONS.md
- AI doesn't know about trade execution being commented out
- AI suggests committing private keys or `.env` file
- AI proposes bypassing TOS restrictions

### Strong Indicators of Drift
- Responses are generic (not project-specific)
- AI doesn't mention Polymarket, Polygon, or CLOB
- Suggested code doesn't match existing patterns
- AI unaware of Python 3.9 requirement
- AI doesn't know about LangChain/ChromaDB RAG setup
- Answers about token limits don't mention chunking strategy

### Subtle Signs Worth Checking
- Long conversation thread (>20 exchanges)
- Multiple unrelated topics discussed
- Switching between different subsystems rapidly
- AI seems unsure about architecture
- File paths or function names are wrong

## Reset Checklist After Running Protocol

After running the reset prompt, verify AI knows:

**Core Architecture:**
- [ ] Trading pipeline: events → filter → markets → trade
- [ ] Polymarket class handles blockchain interactions
- [ ] Executor manages LLM calls and token chunking
- [ ] ChromaDB for local RAG, cleared each run
- [ ] Gamma API for read-only market data

**Critical Safety:**
- [ ] Trade execution commented out by default
- [ ] Private keys only via .env
- [ ] TOS restrictions on jurisdictions
- [ ] No testnet/sandbox available

**Key Decisions:**
- [ ] Python 3.9 requirement (D-001)
- [ ] Disabled trade execution (D-002)
- [ ] Ephemeral RAG databases (D-003)
- [ ] Token chunking at 80% limit (D-005)

**Known Failure Modes:**
- [ ] LLM token limit exceeded
- [ ] API rate limiting
- [ ] Wallet insufficient funds
- [ ] Stale market data

If any checkbox fails, AI context is incomplete. Re-run reset or clarify gaps.

## Emergency Reset (Nuclear Option)

If standard reset doesn't work:

1. Start completely fresh conversation
2. First message: "Read SYSTEM_INVARIANTS.md, DECISIONS.md, and CLAUDE.md. Summarize what you learned."
3. Verify AI absorbed the key points
4. Only then state the actual task

This costs tokens but guarantees clean slate.
