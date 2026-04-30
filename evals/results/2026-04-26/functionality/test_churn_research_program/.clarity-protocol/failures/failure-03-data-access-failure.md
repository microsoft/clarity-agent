# Failure: Data Access Failure

## Summary

Key data sources the research program depends on are blocked — either because the product analytics system can't be exported, or because account managers withhold their exit interview notes. The team proceeds with an incomplete evidence base and either doesn't realize it, or acknowledges the gap without an adequate response. Findings are less grounded than they appear, and the executive presentation lacks the quantitative strand that would make it most credible.

## Failure Chain

1. Research program is scoped assuming access to product analytics and exit interview notes.
2. Analytics export is attempted. The system has no usable export API; engineering deprioritizes the request or the data structure makes it impractical to analyze in raw form.
   - *Intervention point (prevention):* In week 1, assess analytics access before building the plan around it. If export is blocked, identify what proxy signals are available (e.g., aggregate reports in the UI, data from a different tool, or a manual pull of a key metric).
3. Account managers are asked to share exit interview notes. They perceive the request as a performance audit.
   - *Intervention point (prevention):* Frame the request explicitly as program research, not performance evaluation. Get COO or manager sponsorship so the ask comes with organizational backing. Offer to anonymize account manager attribution in any published findings.
4. Access is partially or fully denied for one or both sources. **Harm begins.** The team loses quantitative usage signal and the richest existing qualitative data.
5. The team proceeds with NPS/CSAT, support tickets, and fresh interviews as the sole evidence base.
   - *Intervention point (mitigation):* Adjust the research design explicitly — lean harder on fresh interviews and acknowledge the data gaps in the synthesis document. Don't pretend the missing sources weren't important.
6. The executive presentation presents findings without noting the evidence gaps clearly.
   - *Intervention point (mitigation):* Add a "What we couldn't access and why" section to the methodology slide. Builds credibility rather than undermining it — the exec team will trust a team that acknowledges limitations.
7. **Harm ends** when findings are presented with appropriate caveats. Harm escalates if the exec team later discovers the gaps weren't disclosed and questions the entire diagnosis.

## Observations

- **Severity:** Medium — The program can still produce useful findings without these sources, but the diagnosis is thinner and the quantitative strand (usage as churn predictor) is lost. Credibility risk is higher if gaps are not disclosed.
- **Related failures:** Engineering dependency on analytics export could trigger Failure 4 (Program Execution Breakdown) if the access attempt consumes significant time in week 1.
- **Variants (from brainstorm):**
  - Product analytics are truly inaccessible within the six-week window
  - Account managers gate-keep exit interview notes

## Intervention Points

### Prevention
- Assess analytics access in the first two days of week 1 before building around it
- Frame account manager ask as research (not audit); get leadership sponsorship

### Detection
- If no response from account managers within 3 days, escalate through their manager
- If analytics export is blocked, assess available proxy metrics immediately

### Mitigation
- Redesign the evidence base around what's accessible; don't preserve the plan at the cost of accuracy
- Acknowledge data gaps explicitly in synthesis and presentation

### Recovery
- If gaps surface post-presentation: note as an area for future investigation; propose a follow-on quantitative study once analytics access is established

---

## Management Plan

Not yet developed. Run failure management to develop a plan for this failure mode.
