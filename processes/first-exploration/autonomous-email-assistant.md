# Scenario: Autonomous Email Assistant

## Seed situation

A technology company's AI assistant can read employees' email and draft replies. The team is now considering allowing the assistant to send some messages without the employee reviewing each one first.

### Intentional ambiguities

- What "automatically" means is undefined — it could range from scheduled sends to fully autonomous composition.
- The boundary between "draft" and "send" is a design choice, not a given.
- Whether the assistant acts as the employee, for the employee, or as a distinct entity is unresolved.
- The scope of "some messages" is open — routine acknowledgments? Scheduling? Substantive replies?
- Who authorized this capability and on whose behalf it operates is unclear.

## Dimensions and tensions

These are aspects of the problem space that can produce consequential insights, depending on where the user's reasoning goes:

- **Authority and identity.** The assistant sends as the employee. Whose judgment does the message represent? Whose reputation is at stake? What happens when those diverge?
- **Approval and execution gap.** Time passes between any human decision and the system's action. What can change in that interval?
- **Automation trust decay.** Reliable systems erode the vigilance that made them safe. The human-in-the-loop degrades into a rubber stamp.
- **Reversibility and commitment.** A sent message creates social and legal obligations. Unlike most software actions, it cannot be rolled back.
- **Boundary classification.** Any rule distinguishing "safe to send" from "needs review" requires a classifier. Classifiers have error modes at their boundaries.
- **Delegation and accountability.** When the employee delegates to the assistant, do they delegate authority or only labor? Who is accountable for a message sent while the employee is unavailable?
- **Observability.** Can the employee tell what was sent on their behalf? Can recipients tell they're interacting with an AI?
- **Human baseline and comparative risk.** The alternative to automation is not perfect human performance. Humans currently miss messages, delay responses, misroute replies, and handle sensitive content inconsistently. Constrained autonomy might reduce some risks while introducing others.

## Deepening questions

Use these to follow threads the user opens — not as a checklist:

- "Who bears the consequence if that goes wrong?" (surfaces accountability gaps)
- "What has to remain true for that safeguard to work?" (exposes unstable preconditions)
- "Would the recipient know?" (surfaces consent and transparency)
- "What happens between approval and execution?" (opens temporal gaps)
- "If the system works perfectly for six months, what changes?" (surfaces trust decay)
- "Whose authority is the assistant exercising when the employee is offline?" (surfaces delegation ambiguity)
- "What goes wrong today without this capability?" (surfaces human-baseline failures and reframes the comparison)

## Indicators of promising insight

A productive thread is forming when:

- The user proposes a safeguard that assumes a stable condition (approval, classification, availability) — probe whether that condition actually holds.
- The user distinguishes categories of messages — probe where the boundary fails or shifts.
- The user focuses on the employee's experience — introduce the recipient's perspective, or vice versa.
- The user invokes "human in the loop" as a solution — probe what degrades the loop over time.
- The user treats "approval" as binary — probe what the approval actually covers and whether that scope can drift.

## Premise changes for reassessment

Select based on what the conversation has established:

- The organization permits autonomous sending for internal routine messages but never for external recipients. *(Introduces a classification boundary that can be crossed.)*
- The employee goes on leave and delegates inbox management to the assistant. *(Shifts from augmentation to autonomous operation; context degrades.)*
- A regulatory body requires that AI-generated communications be disclosed to recipients. *(Adds an observability constraint that interacts with the assistant's identity.)*
- The assistant's training data includes messages from before the current organizational policy. *(Introduces stale context as a source of drift.)*

## Fallback examples

*Use these only when the conversation stalls or the user gives very short answers. They are illustrative, not destinations.*

**Example requirement (not the requirement):** "The system must not create externally visible communication without authority appropriate to the message, recipient, and current context."

**Example failure chain (not the failure):** User approves a draft → thread receives a new reply before send → system sends the approved text into a changed conversational context → the message is now inappropriate or contradictory → approval has been treated as authorization for an action the human did not review.

**Example alternative failure:** System performs reliably for months → employee stops reading the approval queue carefully → a subtly wrong message appears routine → reduced scrutiny allows it through → the human-in-the-loop safeguard has silently degraded.

## Anti-pattern

Do not sample several dimensions aloud or present a menu of risks after the user responds. Choose one promising thread and deepen it. Serendipity should feel like discovery, not coverage.
