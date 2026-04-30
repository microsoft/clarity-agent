---
name: codebase-scanner-thinker
display_name: Codebase Scanner
type: ai
modes: [quick, deep]
prerequisites:
  required: [goal/problem.md]
  recommended: [goal/stakeholders.md, solution/architecture.md]
tags: [architecture, codebase, scanning, reconnaissance]
description: "Repository scanning: API routes, configs, auth patterns, secrets, AI integrations, infrastructure"
---
# Codebase Scanner Thinker

This thinker scans a repository for architectural signals — API routes, configs, auth patterns, database references, AI/ML integrations, secrets management, and network config — to inform architecture design and threat modeling.

## Prerequisites

This thinker requires **direct access to the project's codebase** via file-reading and search tools (Grep, Glob, Read). When running via the brainstorm runner, the codebase must be accessible from the execution environment. When running from a web UI or remote context where the codebase isn't directly accessible, this thinker should be skipped — rely on the architecture document instead.

## Purpose

Before you can analyze a system's failure modes, you need to understand what the system actually is. This thinker systematically scans the codebase for structural signals that reveal components, data flows, trust boundaries, and potential attack surface. The output feeds directly into architecture design and failure brainstorming.

## Scope

This thinker focuses on:

- **API routes and endpoints** — the system's external interface
- **Configuration** — how the system is configured, what's configurable
- **LLM/AI integrations** — model usage, embedding pipelines, agent frameworks
- **Database and storage** — what data is stored, where, how
- **Authentication and identity** — how users prove who they are, what they can access
- **Network and infrastructure** — ports, hosts, CORS, proxies, firewalls
- **Secrets management** — how credentials and keys are stored and accessed
- **CI/CD and deployment** — build pipelines, containers, infrastructure as code

## Analysis Approach

Use Grep, Glob, and Read tools to systematically search the repository. Start by identifying the technology stack from package manifests and directory structure, then search for signals relevant to the detected stack.

If `solution/architecture.md` exists, use it as a starting point — the architecture document describes the intended design. The codebase scan validates what's actually implemented and surfaces things the architecture document may have missed or gotten wrong. Note any discrepancies between the documented architecture and what the code reveals.

## Patterns to Search

The table below lists common signal categories. **Adapt these to the actual technology stack** — don't search for Express patterns in a Python project, or Django patterns in a Java project. Start by reading the package manifest (package.json, requirements.txt, pom.xml, etc.) to identify the stack, then search for patterns relevant to it.

| Signal | What to look for |
|--------|-----------------|
| API routes | Route definitions, endpoint handlers, controller classes, API documentation |
| Config | Environment files, config modules, settings files, feature flags |
| LLM/AI | Model API calls, embedding pipelines, agent frameworks, prompt templates |
| Database | Connection strings, ORM models, migration files, query builders |
| Auth | Authentication middleware, session management, token handling, identity providers |
| Network | Port bindings, CORS config, proxy settings, load balancer config, firewall rules |
| Secrets | Key vault references, secret managers, credential stores, hardcoded secrets |
| CI/CD | Pipeline definitions, Dockerfiles, infrastructure-as-code, deployment scripts |

## Output Format

For each scan session, produce a structured architectural report and raw failure modes for any concerns discovered.

### Architectural Report

```
## Codebase Scan Report
**Scanned:** {date}

### Project Structure
- Language(s): {languages detected}
- Framework(s): {frameworks detected}
- Package manager: {npm/pip/etc.}

### Components Found

| Component | Type | Description | Trust Zone |
|-----------|------|-------------|------------|
| {name} | {Process/Data Store/External Entity/AI Model/Agent} | {description} | {Untrusted/Low Trust/Trusted/High Trust} |

### Data Flows
| From | To | Data | Protocol | Sensitivity |
|------|-----|------|----------|-------------|
| {source} | {dest} | {what flows} | {HTTP/gRPC/etc.} | {Public/Internal/Confidential/Restricted} |

### Discrepancies with Architecture Document
- {Anything the code reveals that differs from or is missing in architecture.md}

### Auth & Identity
- {Authentication mechanisms found}

### Secrets Management
- {How secrets are stored and accessed}

### AI/ML Integration
- {Models used, how they're called, what data they process}

### Open Questions
- {Things that couldn't be determined from code alone}
```

### Raw Failure Modes

For each architectural concern discovered during scanning, record a raw failure mode:

- **Title**: A short descriptive title of what could go wrong
- **Source**: `codebase-scanner-thinker`
- **Description**: 1-3 sentences describing the concern and potential harm
- **Additional context**: Reference to the specific code pattern or file that raised the concern

## Using This Thinker

This thinker is invoked by the failure brainstorming process or directly during architecture design. The AI reads this guide (via `read_thinker_guide`) and applies its methodology, scanning the codebase and recording failures via the `record_failure` tool.

In either mode, the thinker scans the codebase, builds a structural understanding, and produces both an architectural report and raw failure modes for any concerns.

## Cross-Domain Considerations

Codebase scanning findings inform multiple other thinkers:

- **Security thinker**: Exposed endpoints, auth patterns, and secrets management feed security analysis
- **Adversarial analysis thinker**: Attack surface revealed by the scan (exposed APIs, data stores, access patterns) informs what adversaries would target
- **Human factors thinker**: UI patterns and configuration complexity affect operator and user error
- **Latest threats fetcher**: Component types determine which threat categories to check