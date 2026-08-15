# Authorized Strix Scope for AletheionAGI

This scan is authorized only for infrastructure owned and controlled by AletheionAGI.

## Focus areas

- Authentication failures and authorization bypass.
- Tenant isolation, namespace isolation, IDOR and cross-tenant leakage.
- Unauthorized evidence access, grounding bypass and fail-closed bypass.
- Unsupported-claim delivery and unsafe fallback behavior.
- Evidence poisoning and prompt injection through evidence.
- API parameter manipulation, malformed requests and business-logic flaws.
- State confusion, replay-related authorization issues and inconsistent enforcement
  between endpoints.

## In scope

- The exact HTTPS hostname supplied by the wrapper, which must be one of:
  `aletheionagi.com`, `www.aletheionagi.com`, or `api.aletheionagi.com`.
- Publicly reachable HTTP/API behavior on that exact host.
- Non-destructive checks in Strix `quick` mode.
- Synthetic test inputs and test credentials explicitly provisioned for this assessment.

## Out of scope

- Every competitor, third-party provider, dependency, SaaS platform, shared hosting
  neighbor, cloud control plane, employee device, or customer environment.
- Subdomains not listed above, even if they end with `aletheionagi.com`.
- Destructive exploitation, persistence, denial of service, credential attacks,
  phishing, social engineering, data exfiltration, or modification of production data.
- Data deletion, credential stuffing and brute force.
- Bypassing rate limits, authentication boundaries, or provider terms.
- Payment providers, hosting providers, email providers and unrelated domains.
- Access to real user data or data belonging to real third parties.

Stop immediately if a redirect, discovered asset, DNS result, callback, integration or
linked service leaves the exact hostname allowlist. Do not follow it or test it. Treat
all findings as unconfirmed until a human reviewer reproduces them safely and records a
minimal proof of concept. If confirmation would require real third-party data, stop and
report the issue as unconfirmed. Do not exfiltrate secrets or include secrets, cookies
or authorization headers in reports. Do not modify production data outside the
dedicated test namespace.
