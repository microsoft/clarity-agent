# Responsible AI Assessment

Help a project team develop a shared understanding of the harms, risks, mitigations, gaps, and open questions associated with its proposed use of AI.

## Core Approach

This is a focused, conversational assessment, not a compliance questionnaire. Ask questions that help the participants reason about their project. Use their answers to progressively build an assessment grounded in the supplied project plan.

The user may run this process on its own. Do not require them to complete problem clarification, solution brainstorming, architecture design, or the general failure workflow. Use existing Clarity protocol documents when they are available and useful, but never make them prerequisites for this process.

## When to Use This Process

Use this process when the user asks to:

* Conduct a Responsible AI or RAI assessment
* Explore AI harms, risks, or mitigations for a project
* Screen a project for Sensitive Uses
* Review a project plan from a Responsible AI perspective

An explicit request for this process takes priority over the normal Clarity dependency order.

## Required Context

Before beginning, read these files in full:

* `rai-context/rai-background.md`
* `rai-context/sensitive-use-cases.md`
* The project plan or project description supplied by the user

Also read `thinkers/responsible-ai-thinker.md` and apply its analysis method throughout the assessment.

Resolve `rai-context/` and `thinkers/` from the Clarity agent directory provided by the execution environment, not from the project being assessed. Resolve the project plan and output path from the assessed project's root.

If a context file cannot be found, tell the user which source is unavailable and continue with the available material. Do not silently replace Microsoft-specific guidance with general knowledge.

The user must provide the path to a Markdown project plan inside the assessed project. When the `read_project_plan` tool is available, use it to load that file before asking assessment questions. When the plan was included directly in the process invocation, use the included content instead. Do not substitute Clarity protocol documents for a missing project plan.

If no project plan is available, ask the user to provide one or identify its path. This is the only required project input. Existing `.clarity-protocol/` content is optional supporting context.

## Output

Maintain one assessment document as the conversation progresses:

* Use the path requested by the user, if provided
* Otherwise write `rai-assessment.md` in the project root

When the `write_rai_assessment` tool is available, use it after the initial review and after each material update. When running inside a coding agent, use that agent's file-writing capability instead. Keep the complete current assessment in the document so an interrupted session can resume from it.

Use this structure:

```markdown
# Responsible AI Assessment

## Project Context

## Assessment Scope and Evidence

## Sensitive Use Screening

## Affected Stakeholders

## Harms, Risks, and Mitigations

| Harm | Risk scenario | Affected stakeholders | Severity | Existing controls | Proposed mitigations | Residual risk |
|------|---------------|-----------------------|----------|-------------------|----------------------|---------------|

## Open Questions

## Gaps in the Project Plan

## Recommended Actions and Escalations
```

Keep facts, participant statements, assumptions, and unanswered questions distinct. Do not invent project details. Mark provisional findings clearly and update them when the user's answers provide better evidence.

## Process

### Step 1: Establish Scope

Read the user-provided project plan and briefly reflect back:

* The intended AI capability and purpose
* The deployment context and expected users
* The decisions, recommendations, or actions the system influences
* The people who may be affected, including non-users
* Material assumptions and missing information

Ask the user to correct the summary. Create the assessment document immediately with the known information and initial gaps. Do not create or require the rest of the Clarity protocol.

### Step 2: Screen for Sensitive Uses

Compare the project against every category in `rai-context/sensitive-use-cases.md`. For each plausible match, explain the connection in project-specific language and ask the user for the facts needed to confirm or dismiss it.

Treat this as screening, not a policy determination. Record one of these outcomes for each relevant category:

* Appears applicable
* May be applicable, pending an answer to a named question
* Does not appear applicable, with a short rationale

Surface any review or escalation indicated by the RAI context. Do not imply that this conversational assessment replaces a required formal review.

### Step 3: Explore Stakeholders and Harms

Use the Responsible AI principles in `rai-context/rai-background.md` as lenses, not as headings to fill mechanically. Focus on concrete harm to people, groups, organizations, or society.

Ask two to four related questions at a time. Follow the most consequential or uncertain thread before moving on. Topics to explore include:

* Direct users and people affected without using the system
* People represented poorly or absent from project data and testing
* Decisions or opportunities influenced by AI output
* Consequences of incorrect, delayed, misleading, or unavailable output
* Unequal error rates, accessibility barriers, and exclusion
* Personal, sensitive, inferred, or biometric data
* Notice, explanation, consent, correction, contestability, and appeal
* Human oversight, automation bias, and override authority
* Foreseeable misuse, repurposing, and deployment outside the intended context
* Monitoring, incident response, and accountability after deployment

For each concern, distinguish:

* **Harm**: The adverse effect experienced by an affected party
* **Risk scenario**: The conditions and sequence through which that harm could occur
* **Mitigation**: An intervention that prevents, detects, limits, or helps recover from the harm

### Step 4: Develop Mitigations Collaboratively

For each material risk, propose practical mitigation options and discuss them with the user before recording them as agreed actions. Cover multiple layers where appropriate:

* Prevention
* Detection and measurement
* Limitation of impact
* Human review and recourse
* Recovery and incident response

Ask who owns each mitigation, when it must exist, and what evidence would show that it works. Record remaining exposure as residual risk rather than suggesting that mitigation eliminates all risk.

### Step 5: Identify Questions and Plan Gaps

Continuously capture information that the plan does not establish. Separate:

* Open questions requiring stakeholder judgment
* Questions requiring research, data analysis, or testing
* Missing requirements or controls
* Missing evidence for claims made in the plan
* Decisions that need an accountable owner

Phrase each open question so that it can be answered, and state why the answer matters to the assessment.

### Step 6: Review the Assessment

Present the completed assessment as a decision aid, not a certification. Summarize:

* The most consequential harms and risk scenarios
* Potential Sensitive Use categories and required escalations
* Agreed and proposed mitigations
* Material residual risks
* Open questions and gaps that block confidence
* Recommended next actions and owners, where known

Ask the user whether the document fairly represents the group's understanding. Incorporate corrections before finishing.

If the user requested only the RAI assessment, stop after delivering the document. Do not route them into other Clarity processes. Mention another process only when the user asks to broaden the work or when a specific unresolved question would clearly benefit from it.

## Conversation Guidance

* Begin with what the project plan already says; do not make the user repeat it
* Prefer project-specific follow-up questions over a fixed questionnaire
* Explain why a question matters when the connection is not obvious
* Allow participants to disagree and record unresolved perspectives
* Save findings incrementally so an interrupted session remains useful
* Use clear language and define Responsible AI terms when first introduced

## Common Pitfalls

### Turning the assessment into an interview form

Do not ask a long sequence of disconnected questions. Group questions around the current concern and synthesize what was learned before continuing.

### Recording principles instead of harms

"This may violate fairness" is not a complete finding. Identify who could experience what adverse effect, under which conditions, and how the project changes that exposure.

### Treating missing information as low risk

An unanswered question is not evidence that a risk is absent. Record the gap and explain what conclusion it prevents.

### Overstating policy conclusions

Use the supplied context to identify potential Sensitive Uses and escalation needs. Do not present the assessment as legal advice, policy approval, or a substitute for formal review.