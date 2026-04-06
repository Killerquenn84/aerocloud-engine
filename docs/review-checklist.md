# Code Review Checklist — AeroCloud Engine

> MANDATORY for every code review. All 3 AIs must complete independently.

## Security (S-1 to S-8)
- [ ] S-1: SQL/NoSQL Injection — Are all queries parameterized?
- [ ] S-2: XSS — Is all user input sanitized before rendering?
- [ ] S-3: CSRF — Are state-changing endpoints protected?
- [ ] S-4: Authentication — Are all protected routes properly guarded?
- [ ] S-5: Secrets — Are credentials in env vars, never in code?
- [ ] S-6: SSRF — Are outbound requests validated?
- [ ] S-7: Path Traversal — Are file paths sanitized?
- [ ] S-8: DoS — Are rate limits and input size limits in place?

## Stability (L-1 to L-8)
- [ ] L-1: Error Handling — Are all errors caught and handled gracefully?
- [ ] L-2: Resource Leaks — Are connections/handles properly closed?
- [ ] L-3: Race Conditions — Are concurrent operations safe?
- [ ] L-4: Timeouts — Do all external calls have timeouts?
- [ ] L-5: Memory — Are there potential memory leaks or unbounded growth?
- [ ] L-6: Retry Logic — Is retry implemented with backoff for external calls?
- [ ] L-7: Graceful Degradation — Does the system handle partial failures?
- [ ] L-8: Logging — Are errors logged with sufficient context?

## Architecture (A-1 to A-5)
- [ ] A-1: SRP — Does each module have a single responsibility?
- [ ] A-2: DRY — Is there unnecessary duplication?
- [ ] A-3: Coupling — Are modules loosely coupled?
- [ ] A-4: API Contract — Are interfaces well-defined and stable?
- [ ] A-5: Backwards Compatibility — Are breaking changes documented?

## Anti-Sycophancy Self-Check
- [ ] "Did I actively search for weaknesses?"
- [ ] "Am I agreeing because I'm convinced — or because it's easier?"
- [ ] "Did I search for a counter-case before approving?"
