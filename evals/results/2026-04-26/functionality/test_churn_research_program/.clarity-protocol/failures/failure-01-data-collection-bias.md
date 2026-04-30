# Failure: Data Collection Bias

## Summary

The qualitative data collected from interviews doesn't accurately represent reality — either because customers self-censor (social desirability bias), the sample is unrepresentative (survivorship or recruitment bias), interviewers contaminate responses (interviewer bias), or data quality degrades mid-session (interview fatigue). Elena and the team analyze data that looks valid but misrepresents why customers actually churned. Findings point to the wrong drivers. The executive team acts on a flawed diagnosis.

## Failure Chain

1. Interview guide and sampling approach are developed without explicit safeguards against bias.
   - *Intervention point (prevention):* Design the guide with open-ended, non-leading questions. Have someone outside the team review it for leading language before use.
2. Churned customers who agree to participate skew toward less hostile churners, a particular segment, or specific churn reasons.
   - *Intervention point (prevention):* Map the recruitment sample against the full churned population by segment and churn date. Flag and acknowledge coverage gaps explicitly.
3. Interviewers conduct sessions with the working hypothesis in mind.
   - *Intervention point (prevention):* Brief interviewers explicitly on confirmation bias and interviewer effect. Assign a second interviewer as a neutral observer on at least a subset of sessions.
4. During sessions, customers frame their answers to be polite, sessions run long and quality drops, or interviewers react visibly to confirmatory answers.
   - *Intervention point (prevention):* Keep sessions to 45 minutes max. Use a strict guide sequence with probing questions that assume nothing. Avoid verbal/non-verbal reactions to specific answers.
5. Transcripts and notes are coded without a shared guide.
   - *Intervention point (prevention):* Build a coding guide before the first interview. Have two coders independently tag a shared transcript and compare; resolve disagreements before coding the full set.
6. **Harm begins.** Themes emerge that reflect bias artifacts — not customer reality. The team believes they have valid signal.
7. Biased themes are carried into the synthesis and presented as findings.
   - *Intervention point (mitigation):* At synthesis, test each theme against the full dataset: "Does this hold for churned customers across all segments, or just for those who participated?" Explicitly note where coverage is thin.
8. Executive presentation recommends interventions targeting the wrong drivers. **Harm ends** only when the company discovers that churn hasn't improved and investigates why.

## Observations

- **Severity:** High — A diagnosis built on biased data leads to wasted remediation effort and continued churn. The six-week window makes it unlikely the bias will be caught before the presentation.
- **Related failures:** Feeds directly into Failure 2 (Analytical Error) — biased inputs make analytical errors harder to detect because the data appears internally consistent. Contributes to Failure 6 (Post-Program Failure) if the exec team acts on wrong recommendations.
- **Variants (from brainstorm):**
  - Social desirability bias — interviewees aren't candid
  - Survivorship bias — loyal customer sample skews contrast
  - Interview sample misrepresents the churned customer population
  - Interview fatigue — interviewees disengage mid-session
  - Interviewer bias — team members lead or guide responses

## Intervention Points

### Prevention
- Review interview guide for leading questions before first session
- Map recruitment sample against full churned population; document gaps
- Brief interviewers on confirmation and interviewer bias
- Assign a neutral observer to a subset of sessions
- Develop a shared coding guide before coding begins; calibrate between coders

### Detection
- At synthesis: check whether themes hold across all segments or only in covered ones
- Compare finding distribution with the known churn population distribution

### Mitigation
- Explicitly flag low-confidence themes in the synthesis document with coverage rationale
- Triangulate with non-interview sources (NPS scores, usage data, support tickets) before presenting as a finding

### Recovery
- If bias is discovered post-presentation: acknowledge limitations honestly; propose a targeted follow-on study for the most affected segment

---

## Management Plan

Not yet developed. Run failure management to develop a plan for this failure mode.
