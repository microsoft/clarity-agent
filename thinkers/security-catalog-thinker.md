---
name: security-catalog-thinker
display_name: Security Catalog
type: ai
modes: [quick, deep]
prerequisites:
  required: [goal/problem.md, goal/stakeholders.md]
  recommended: [solution/solution.md, solution/architecture.md]
tags: [security, threat-intelligence, owasp, cve]
description: "Maps threats from the security catalog to system components and records applicable failure modes"
---
# Security Catalog Thinker

This thinker maps threats from the curated security catalog to the system being designed, producing raw failure modes for applicable threats.

## Purpose

The clarity agent ships with a curated threat catalog at `catalogs/security-catalog.csv` containing known threat patterns from OWASP Top 10 for LLM Applications, OWASP Agentic AI Top 10, and STRIDE. Each entry has the columns: `category,id,title,summary,key_impacts,key_mitigations,source`.

This thinker's job is to read that catalog and systematically determine which threats are relevant to the specific system being analyzed — then record raw failure modes for each applicable threat.

The catalog itself is maintained separately (via `dev-tools/refresh-catalog.py`) and is assumed to be current when this thinker runs.

## Scope

This thinker focuses on:

- **OWASP LLM Top 10** (LLM01–LLM10) — threats to LLM-based applications
- **OWASP Agentic AI Top 10** (ASI01–ASI10) — threats specific to agentic AI systems
- **STRIDE** (STRIDE-S/T/R/I/D/E) — general threat categories for any system
- **Matching threats to components** — which cataloged threats apply to this specific system's architecture

## Analysis Approach

### Step 1: Identify system components

Read the system design documents (problem statement, solution, architecture) to identify the component types present in this system. Common component types include:

- LLM / AI model
- AI agent
- Vector store / RAG
- Database
- API gateway
- Key vault / identity provider
- Human oversight interface
- Inter-agent communication
- Code execution environment
- External entities / third-party services

### Step 2: Map threats to components

Read `catalogs/security-catalog.csv` and use this component-to-threat heuristic:

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

### Step 3: Assess applicability

For each threat identified by the heuristic, assess whether it actually applies to this system's specific design:

- Does the system have the component type this threat targets?
- Does the system's design make it susceptible to this specific attack vector?
- Are there design choices that already mitigate this threat?
- Would this threat cause real harm in the context of this system?

### Step 4: Record failure modes

For each threat that could cause real harm, record a raw failure mode via `record_failure`.

## Output Format

### Threat Relevance Assessment

```
## Security Catalog Analysis
**Analyzed:** {date}

### System Components Mapped
| Component | Type | Relevant Threat Categories |
|-----------|------|---------------------------|
| {name} | {type} | {threat IDs from catalog} |

### Applicable Threats
- {Threat ID}: {title} — relevant because {why it applies to this system}

### Not Applicable
- {Threat ID}: {title} — not relevant because {why}
```

### Raw Failure Modes

For each applicable threat, record a raw failure mode:

- **Title**: A short descriptive title of what could go wrong
- **Source**: `security-catalog-thinker`
- **Description**: 1-3 sentences describing what goes wrong, how it happens, and who is harmed
- **Additional context**: Reference to the security catalog entry ID, affected component types, and any system-specific considerations

## Using This Thinker

This thinker is invoked by the failure brainstorming process. The AI reads this guide (via `read_thinker_guide`) and applies its methodology, mapping catalog threats to project components and recording failures via the `record_failure` tool.

In either mode, the thinker reads `catalogs/security-catalog.csv` and system context, maps threats to components, and produces raw failure modes for applicable threats.

## Cross-Domain Considerations

Threat catalog findings often interact with other thinkers:

- **Security thinker**: Cataloged threats feed directly into security analysis via the component-to-threat heuristic. The security thinker does deep vulnerability analysis; this thinker ensures known threat patterns from the catalog are systematically covered.
- **Adversarial analysis thinker**: Threats mapped here inform what adversary types are relevant (e.g., LLM threats imply prompt injection adversaries, agentic threats imply tool exploitation adversaries).
- **Human factors thinker**: Some catalog entries (e.g., ASI09 human-agent trust exploitation) involve human factors.
- **Supply chain**: Many catalog entries (LLM03, ASI04) relate to dependency and supply chain vulnerabilities.

Note cross-domain relevance in the additional context of raw failure modes.
