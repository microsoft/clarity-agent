# The Clarity Agent

This folder contains the main logic of the clarity agent. It relies on various Python code which
lives in src/clarity-agent. In the ordinary order that they're invoked:

- clarity-agent.md is the "main" program which drives all the other skills and decides what to do.
- problem-clarification.md is used when the problem itself needs to be clarified. Includes a
  "discovery check" that identifies fundamental unknowns requiring investigation.
- discovery-prototype.md tests a specific hypothesis through minimal, focused implementation.
- discovery-research.md designs and executes a research program to answer open questions.
- solution-brainstorming.md is used to come up with a plan for how to fix the problem.
- architecture-design.md turns a solution into a concrete implementation architecture and plan.
- failure-brainstorming.md comes up with things that might go wrong.
- failure-analysis.md groups the outputs of raw (human and AI) brainstorms into failure modes that
  we can reason about.
- failure-management.md comes up with plans on how to manage these failures, usually modifying the
  solution and architecture -- and so we loop back.

When the project narrative needs work, or you're preparing to explain the project to people:

- message-clarification.md builds the summary and audience-specific messaging.

When nontrivial decisions need to be made, we log these in .clarity-protocol/decisions.

- decision-guidance.md is used to help think through a decision.

## The status of these files

| File | Status |
| :--- | :----- |
| `clarity-agent.md` | Core version implemented |
| `problem-clarification.md` | Core version implemented |
| `discovery-prototype.md` | Core version implemented |
| `discovery-research.md` | Core version implemented |
| `solution-brainstorming.md` | Basic version implemented; please improve. |
| `architecture-design.md` | Basic version implemented; please improve. |
| `failure-brainstorming.md` | Core version implemented (tool-based pipeline with thinker registry and 6 specialist thinkers). |
| `failure-analysis.md` | Basic version implemented; please improve. |
| `failure-management.md` | Basic version implemented; please improve. |
| `message-clarification.md` | Core version implemented. |
| `decision-guidance.md` | Basic version implemented; please improve. |