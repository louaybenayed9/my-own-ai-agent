---
name: security-review
description: >
  Security review checklist for code, configs, and infrastructure changes.
  Use when reviewing a diff, deploying a service, or answering "is this safe?".
  Adapted from mukul975/Anthropic-Cybersecurity-Skills.
---

# Security Review

Review in this priority order. Report findings as:
`[severity] location — issue — fix` with severity one of CRITICAL / HIGH /
MEDIUM / LOW.

## 1. Injection and execution
- SQL: any string-formatted query → parameterize. ORM raw() calls count.
- Shell: `shell=True`, `os.system`, `subprocess` with user input → reject or
  escape; prefer argv lists.
- Templates: `|safe`, `dangerouslySetInnerHTML`, `v-html` on user data → XSS.
- Deserialization: pickle/yaml.load on untrusted input → use safe loaders.

## 2. Auth and secrets
- Secrets in code, logs, or error messages → move to env/secret manager.
- Missing authz check on any endpoint or object access (IDOR): enumerate
  every route and confirm the guard.
- Token handling: no JWT `alg: none`, no long-lived refresh tokens without
  rotation.

## 3. Data handling
- User input reaching file paths (path traversal), redirects, or SSRF-prone
  fetches (internal IPs, metadata endpoints 169.254.169.254).
- CORS `*` with credentials; cookies without HttpOnly/Secure/SameSite.

## 4. Infrastructure
- Public S3/buckets/DB ports; default credentials; containers running as root
  with host mounts.
- Outdated deps with known CVEs in the direct dependency tree.

## Output format
End with a one-line verdict: `BLOCK` (any CRITICAL/HIGH), `FIX-THEN-MERGE`
(MEDIUM), or `PASS` (LOW only, with tracking note).
