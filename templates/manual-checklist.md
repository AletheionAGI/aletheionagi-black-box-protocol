# Manual evidence checklist

Complete this file with sanitized evidence before changing either manual result to PASS.

## BB-02 — Workspace identity

- [ ] Organization A opened in an isolated browser profile.
- [ ] Organization B opened in a different isolated browser profile.
- [ ] Organization names, projects, environments and namespaces compared.
- [ ] Key metadata and balances compared.
- [ ] No foreign resource appeared.
- Sanitized evidence references:
- Operator:
- UTC time:
- Outcome: PASS | FAIL | INCONCLUSIVE
- Notes:

## BB-10 — API-key revocation

- [ ] Temporary key created in one organization.
- [ ] One permitted operation succeeded before revocation.
- [ ] Key revoked in the dashboard.
- [ ] Same operation returned 401 or 403 after revocation.
- [ ] Other organization's key remained operational.
- [ ] Temporary key is absent or revoked at cleanup.
- Sanitized evidence references:
- Operator:
- UTC time:
- Outcome: PASS | FAIL | INCONCLUSIVE
- Notes:

