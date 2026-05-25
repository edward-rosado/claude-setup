---
name: parallel-ada-security-audit
description: "Run ADA/WCAG and security audits in parallel using specialized agents, then merge into prioritized remediation plan"
user-invocable: false
origin: auto-extracted
---

# Parallel ADA + Security Audit Workflow

**Extracted:** 2026-03-18
**Context:** Frontend component audit covering both WCAG 2.1 AA compliance and OWASP security

## Problem
Running accessibility and security audits sequentially doubles wall-clock time and loses the opportunity to cross-reference findings (e.g., contrast failures on legally-required disclaimers are both ADA and compliance risks).

## Solution
1. Launch two specialized agents in parallel:
   - **ADA agent** (code-reviewer type): WCAG 2.1 AA focus — semantic HTML, ARIA, contrast, keyboard nav, focus management, screen reader
   - **Security agent** (security-reviewer type): OWASP focus — XSS, injection, CSP, headers, reflected input, href validation
2. Feed both agents the same explicit file list (not "scan everything")
3. Each agent reports findings as: Severity | File:line | Issue | Standard | Fix
4. Merge results into a single prioritized remediation plan with phases ordered by severity

## When to Use
- Before shipping a new feature branch with UI components
- When a template system or component library has grown (10+ components)
- During compliance reviews (ADA lawsuits, SOC 2, etc.)

## Key Details
- ADA agent should check: heading hierarchy, landmarks, ARIA attributes, color contrast ratios (calculate actual ratios against backgrounds), keyboard focus traps, form labels, image alt text, screen reader content ordering
- Security agent should check: React unsafe HTML injection patterns, href construction from config/user data, CSP header construction, reflected query params, missing security headers, inline style/script nonce coverage
- Merge findings that overlap (e.g., legally-required disclaimer text failing contrast is both ADA H-priority and compliance risk)
- Remediation plan should group by: Critical ADA > High Security > High ADA > Medium Security > Medium ADA
