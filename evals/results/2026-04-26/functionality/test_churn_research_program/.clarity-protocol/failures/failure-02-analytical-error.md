# Failure: Analytical Error

## Summary

The team collects usable data but reasons about it incorrectly — confirming a hypothesis rather than testing it, applying different interpretive standards across the dataset, treating two distinct churn patterns as one, or being unable to reconcile conflicting signals. The analysis produces a diagnosis that is internally consistent but wrong. Stakeholders make decisions based on it.

## Failure Chain

1. Team enters analysis with a strong working hypothesis (value prop delivery failure) and a fixed framework.
   - *Intervention point (prevention):* Articulate the hypothesis explicitly at the start of analysis. Then list two or three competing hypotheses that are also plausible. Actively look for evidence for each, not just the primary one.
2. Data is coded and themed without a blind review step.
   - *Intervention point (prevention):* Separate data collection from analysis. One team member codes; a second reviews a sample of the coded data for consistency and alternative interpretations.
3. Evidence that confirms the hypothesis is treated as signal; contradictory evidence is treated as outlier.
   - *Observation:* This is particularly insidious because the team will feel confident. The failure mode doesn't announce itself.
   - *Intervention point (detection):* At synthesis, explicitly count and document contradictory evidence. If more than 20–25% of data points don't fit the leading theme, treat that as a signal to investigate the exception, not discount it.
4. The Q4 spike and the year-long drift are analyzed together, masking that they have different causes.
   - *Intervention point (prevention):* Segment the analysis by churn date from the start. Run the theme analysis separately on Q4 churners and on the longer-term cohort. Look for divergence before collapsing them.
5. Conflicting signals across data sources (e.g., interviews say "missing features"; usage data shows high feature adoption) are left unresolved.
   - *Intervention point (prevention):* Build a conflict register during synthesis — a list of places where sources disagree. For each conflict, write a one-line explanation of why the conflict might exist. Resolve or explicitly acknowledge each one before presenting.
6. **Harm begins.** The synthesis produces a confident-sounding diagnosis that reflects the team's priors and analysis choices more than the data.
7. The diagnosis is presented to marketing, product, and the exec team as evidence-based.
8. Resources are directed at addressing the identified drivers. The actual drivers go unaddressed. **Harm ends** when the company recognizes that churn hasn't improved and revisits the research.

## Observations

- **Severity:** High — Analytical error produces a diagnosis that feels rigorous but isn't. It's harder to challenge than an openly speculative one and may consume significant resources in the wrong direction.
- **Related failures:** Tightly coupled with Failure 1 (Data Collection Bias) — biased inputs amplify analytical errors. Also feeds Failure 5 (Cross-Functional Resistance) — if findings implicate one department, that department may suspect (correctly or incorrectly) that analysis was biased.
- **Variants (from brainstorm):**
  - Confirmation bias — team validates starting hypothesis
  - Interview coding inconsistency produces unreliable themes
  - Q4 spike and year-long drift treated as one problem
  - Conflicting data signals leave diagnosis ambiguous

## Intervention Points

### Prevention
- State the working hypothesis and 2–3 alternatives at the start; actively gather evidence for each
- Separate coder and reviewer roles; calibrate before full coding run
- Segment churn analysis by date cohort from day one
- Build a conflict register for cross-source disagreements

### Detection
- Count and document contradictory evidence at synthesis; investigate rather than dismiss
- Cross-check theme distribution across segments — if a theme holds in only one segment, flag it

### Mitigation
- Present findings with explicit confidence levels (high/medium/low) based on source triangulation
- Publish the conflict register as an appendix in the executive presentation

### Recovery
- If analytical error surfaces post-presentation: treat it as new data, not as a failure of the team; run a focused re-analysis on the contested hypothesis

---

## Management Plan

Not yet developed. Run failure management to develop a plan for this failure mode.
