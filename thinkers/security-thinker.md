---
name: security-thinker
display_name: Security
type: ai
modes: [quick, deep]
prerequisites:
  required: [goal/problem.md, goal/stakeholders.md]
  recommended: [solution/solution.md, solution/architecture.md]
tags: [security, adversarial]
execution: sync
description: "Security vulnerabilities: authentication, authorization, data protection, injection, cryptography, and supply chain"
---
# Security Thinker

This thinker identifies security-related failure modes in systems being designed or built.

## Purpose

Security failures can have severe consequences: data breaches, unauthorized access, financial loss, regulatory violations, and loss of user trust. This thinker systematically examines a system from a security perspective to identify potential vulnerabilities before they become real problems.

## Scope

This thinker focuses on:

- **Authentication failures**: How users prove who they are
- **Authorization failures**: What users are allowed to do
- **Data protection failures**: Keeping sensitive information secure
- **Injection and manipulation**: Malicious inputs and tampering
- **Session and state management**: Maintaining security across interactions
- **Cryptographic failures**: Weak or broken encryption
- **Dependency and supply chain**: Third-party vulnerabilities
- **Operational security**: Configuration, secrets management, logging

## Analysis Approach

Start by reading the stakeholder list (`.clarity-protocol/goal/stakeholders.md`). Adversarial stakeholders identified there — attackers, spammers, scrapers, abusive users — are your primary threat actors. Their documented objectives tell you what they're trying to achieve; your job is to figure out how they might succeed.

For each aspect of the system, think about:

- **Named adversarial stakeholders**: Work from their specific objectives. "The scraper wants to extract all listing data" is more productive than "what if an attacker..."
- **Dual-nature stakeholders**: Users who are aligned in normal use but adversarial in certain contexts (spamming, harassment, gaming the system). These are often the hardest to defend against because they have legitimate access.
- **Indirect stakeholders at risk**: People affected by the system who aren't users. Security failures may harm them in ways they can't anticipate or prevent.
- **Humans as system components**: Operators, administrators, and on-call engineers are part of the security system. They make decisions under pressure, fatigue, and incomplete information. A security incident at 3am handled by a groggy engineer is a different scenario than one at 2pm. Consider how human judgment, communication gaps, and organizational dynamics affect security outcomes.
- **Accidents**: Security protections failing unintentionally — including human error in configuration, deployment, or incident response
- **Insider threats**: Trusted parties misusing access — but also trusted parties making honest mistakes with powerful access
- **Cascading failures**: One security breach enabling others — including cases where a human's response to one incident creates vulnerability to another

If no adversarial stakeholders have been identified yet, flag this — the stakeholder analysis may be incomplete. Use the generic checklist below, but note that the analysis will be stronger once specific threat actors are documented.

### Component-to-Threat Heuristic

Use this table to map system components to relevant threat categories. Reference `catalogs/security-catalog.csv` for full descriptions of each threat ID.

| Component type | Threats to check |
|----------------|-----------------|
| LLM / AI model | LLM01–LLM10, STRIDE-I, STRIDE-T |
| AI agent | ASI01–ASI10, LLM01, LLM06 |
| Vector store / RAG | LLM08, LLM04, STRIDE-T, STRIDE-I |
| Database | STRIDE-T, STRIDE-I, STRIDE-R |
| API gateway | STRIDE-S, STRIDE-D, STRIDE-E, LLM10 |
| Key vault / identity | STRIDE-S, STRIDE-E, ASI03 |
| Human oversight | ASI09, ASI08 |
| Inter-agent | ASI07, ASI04, ASI08 |
| Code execution | ASI05, LLM05 |
| External entity | STRIDE-S, LLM01, ASI09 |

**Consider the prior state**: For each failure you identify, note whether it also exists before this solution is implemented. Many security issues (e.g., phishing, social engineering) are pre-existing and universal. If the solution doesn't make them worse, flag them as pre-existing — they'll be triaged efficiently during analysis.

## Failure Discovery Checklist

Work through these categories systematically:

### Authentication Failures

**What if credentials are compromised?**

- Passwords leaked, stolen, or guessed
- API keys exposed in code or logs
- Session tokens intercepted
- Biometric data spoofed
- Multi-factor authentication bypassed

**What if authentication is bypassed entirely?**

- Direct access to protected resources
- Default credentials not changed
- Authentication checks missing on some endpoints
- Time-of-check vs time-of-use vulnerabilities

**What if authentication state is confused?**

- Session fixation attacks
- Cross-site request forgery (CSRF)
- Authentication tokens reused or not expired

### Authorization Failures

**What if users access resources they shouldn't?**

- Horizontal privilege escalation (accessing other users' data)
- Vertical privilege escalation (gaining admin privileges)
- Insecure direct object references (changing IDs in URLs)
- Missing authorization checks

**What if permissions are incorrectly assigned?**

- Too-broad permissions granted by default
- Permissions not revoked when they should be
- Role confusion or inheritance issues
- Permissions checked client-side only

### Data Protection Failures

**What if sensitive data is exposed?**

- Data transmitted without encryption (HTTP instead of HTTPS)
- Data stored in plaintext when it should be encrypted
- Sensitive data in logs, error messages, or debug output
- Data leaked through side channels (timing, error differences)

**What if data is accessed inappropriately?**

- Database credentials compromised
- Backup files exposed
- Data visible in URLs or browser history
- Clipboard or cache containing sensitive information

**What if data retention is mishandled?**

- Data not deleted when it should be
- Soft deletes that don't actually remove data
- Backups retained longer than policy allows
- Data replicated to insecure locations

### Injection and Manipulation

**What if inputs are malicious?**

- SQL injection through user inputs
- Script injection (XSS) in web applications
- Command injection in system calls
- LDAP, XML, or template injection
- Path traversal attacks

**What if requests are manipulated?**

- Parameter tampering in HTTP requests
- Cookie manipulation
- Headers modified to bypass checks
- Replay attacks resending valid requests

**What if data integrity is compromised?**

- Man-in-the-middle attacks altering data in transit
- Data modified in storage
- Checksums or signatures not verified
- Race conditions allowing inconsistent state

### Session and State Management

**What if sessions are hijacked?**

- Session tokens stolen (XSS, network sniffing)
- Session tokens predictable
- Sessions not properly terminated
- Concurrent sessions not managed

**What if session state is manipulated?**

- Client-side state trusted without verification
- State machines bypassed (skipping steps)
- Time-based attacks (expiration not enforced)
- Session data leaking between users

### Cryptographic Failures

**What if encryption is weak or broken?**

- Using deprecated algorithms (MD5, SHA-1 for security)
- Weak key generation (predictable, too short)
- Hard-coded cryptographic keys
- Improper use of encryption modes
- Missing or weak initialization vectors

**What if secrets are exposed?**

- Private keys in version control
- Secrets in environment variables logged
- Key material in memory dumps
- Secrets transmitted insecurely

### Dependency and Supply Chain

**What if third-party components have vulnerabilities?**

- Known CVEs in dependencies
- Dependencies not updated
- Transitive dependencies with vulnerabilities
- Malicious packages installed

**What if the supply chain is compromised?**

- Dependency confusion attacks
- Typosquatting in package names
- Compromised package repositories
- Build process manipulation

### Operational Security

**What if systems are misconfigured?**

- Default settings left in place
- Debug mode enabled in production
- Overly permissive firewall rules
- CORS policies too broad
- Security headers missing

**What if monitoring fails?**

- Security events not logged
- Logs accessible to attackers
- Alerts not triggered on suspicious activity
- Audit trail incomplete or tampered with

### Human and Organizational Failures

**What if operators make mistakes?**

- Misconfiguration during deployment (wrong environment, wrong credentials)
- Granting excessive permissions because it's faster than figuring out the right ones
- Disabling security controls to debug a problem and forgetting to re-enable them
- Copy-pasting credentials or secrets into the wrong place

**What if incident response fails?**

- On-call engineer lacks context to assess the situation correctly
- Response procedures are too complex for someone who's tired or stressed
- Escalation paths don't work (wrong contacts, unavailable people)
- Responding to one incident creates vulnerability to another (tunnel vision)

**What if organizational dynamics create security gaps?**

- Security knowledge concentrated in one person who leaves
- Pressure to ship overriding security concerns
- Teams with different security assumptions sharing infrastructure
- Security policies that exist on paper but aren't followed in practice

## Failure Chain Development

For each identified failure, develop the chain:

1. **Initial condition**: What state makes this possible? (e.g., "User credentials stored in plaintext")
2. **Triggering event**: What causes it to happen? (e.g., "Database backup exposed")
3. **HARM BEGINS**: First harmful consequence (e.g., "Attacker downloads backup with all passwords")
4. **Propagation**: How does it get worse? (e.g., "Attacker tries passwords on production system")
5. **MITIGATION STARTS**: When/how is it detected? (e.g., "Unusual login pattern triggers alert")
6. **Recovery steps**: What must happen to stop the harm? (e.g., "Force password reset for all users")
7. **HARM ENDS**: Return to safe state (e.g., "All users have new credentials, attacker locked out")

Mark the intervention points—where could this be prevented, detected, or mitigated?

## Common Intervention Points

Security failures often have intervention points at:

- **Input validation**: Reject malicious data before processing
- **Principle of least privilege**: Limit what can be accessed even if security fails
- **Defense in depth**: Multiple layers so single failure doesn't cascade
- **Monitoring and alerting**: Detect attacks in progress
- **Encryption in transit and at rest**: Limit exposure if access control fails
- **Regular updates**: Patch known vulnerabilities
- **Security testing**: Find weaknesses before attackers do
- **Incident response plans**: Minimize damage when breaches occur

## Output Format

For each security failure identified, record a raw failure mode. Each failure record contains:

- **Title**: A short descriptive title of what could go wrong
- **Source**: `security-thinker`
- **Description**: 1-3 sentences describing what goes wrong, how it happens, and who is harmed. This must end in actual harm — a violated principle that doesn't lead to harm is not a failure mode.
- **Additional context** (optional): More detail about the scenario, potential severity, related concerns. Include any initial thoughts about the failure chain, but don't develop full chains here — that happens during failure analysis.

Keep raw failures lightweight. The goal is to capture the idea, not to fully analyze it. Full failure chains, intervention points, and management strategies are developed in later stages (failure analysis and failure management).

## Cross-Domain Considerations

Security failures often interact with other domains:

- **Adversarial analysis**: The `adversarial-analysis-thinker` identifies *who* would exploit vulnerabilities and *why*. This thinker identifies the vulnerabilities themselves. Together they produce the full threat picture: adversary + attack vector + harm.
- **Security catalog thinker**: The `security-catalog-thinker` maps cataloged threats from `catalogs/security-catalog.csv` to the system's components. Its findings feed directly into this thinker's analysis. (The catalog itself is maintained separately via `dev-tools/refresh-catalog.py`.)
- **Privacy**: Security failures often lead to privacy violations (data exposure)
- **User Experience**: Security measures can conflict with usability (complex passwords, frequent re-auth)
- **Scalability**: Rate limiting and security checks can impact performance
- **Data Integrity**: Security failures can enable data corruption
- **Accessibility**: Security measures must not exclude users with disabilities (e.g., CAPTCHA alternatives)

When identifying security failures, note these cross-domain interactions in the additional context — they help during failure analysis and grouping.

## Using This Thinker

This thinker is invoked by the failure brainstorming process. The AI reads this guide (via `read_thinker_guide`) and applies its methodology, recording failures via the `record_failure` tool and suggestions via the `record_suggestion` tool.

In either mode, the thinker examines the problem statement, stakeholder list, solution description, and architecture (if available) to identify security-specific failures.

Work systematically through the checklist, but use judgment — not every category applies to every system. A static website has different security concerns than a financial API.

For each potential failure:

1. Assess if it's relevant to this system
2. Record it as a raw failure mode
3. Include enough context for someone else to understand the scenario

The output is a set of raw failure modes. These will later be grouped, analyzed, and developed into full failure mode documents with chains and management plans.
