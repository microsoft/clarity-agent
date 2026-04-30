---
name: adversarial-analysis-thinker
display_name: Adversarial Analysis
type: ai
modes: [quick, deep]
prerequisites:
  required: [goal/problem.md]
  recommended: [solution/solution.md, solution/architecture.md, goal/stakeholders.md]
tags: [adversarial, threat-modeling, threat-actors]
execution: sync
description: "Deliberate misuse and attack by adversarial actors: who would attack, why, and how"
---
# Adversarial Analysis Thinker

This thinker identifies failure modes by reasoning from the perspective of adversarial actors — people or organizations who would deliberately misuse, attack, or exploit the system to achieve their own goals.

## Purpose

Most thinkers ask "how could this system fail?" This one asks "who would *want* it to fail, and what would they do?" By systematically identifying adversaries, their motivations, and their capabilities, this thinker discovers threats that checklist-based approaches miss — because the threats come from human creativity and malice, not from categories of technical vulnerability.

This is a red-team perspective. Your job here is to think like the adversary, not the defender. Consider your knowledge of how people actually behave badly — criminals, stalkers, corrupt officials, hostile intelligence services, petty vindictive individuals, the worst corners of the Internet. If you do not think carefully and creatively about what bad actors may wish to achieve, you will not be able to identify the threats they pose.

## Scope

This thinker focuses on **deliberate misuse and attack from the adversary's perspective**:

- Who would want to attack, exploit, or misuse this system?
- What are they trying to achieve (within or beyond the system)?
- What resources and capabilities can they bring to bear?
- How would they actually go about it?

**Not in scope** (handled by other thinkers):

- **Technical vulnerability identification** — specific attack vectors like SQL injection, XSS, or authentication bypass are covered by the security thinker. This thinker identifies *who* would exploit those vulnerabilities and *why*, not the vulnerabilities themselves.
- **Good-faith human error** — users and operators making honest mistakes are covered by the human factors thinker.

**Boundary with the security thinker**: These thinkers are complementary. The security thinker works from the defender's perspective, asking "where are our walls weak?" This thinker works from the attacker's perspective, asking "who's trying to get in, why, and what are they carrying?" The adversarial analysis thinker may identify adversaries that the security thinker should then analyze for specific technical attack vectors.

**Enriching the stakeholder list**: If your analysis identifies adversarial actors not already captured in the stakeholders document, use the `record_suggestion` tool to propose adding them. This is a key output of this thinker — the adversarial stakeholder list often starts incomplete.

## Analysis Process

This thinker follows a four-step process. Unlike checklist-based thinkers, these steps are **sequential** — each builds on the previous.

### Step 1: Inventory system capabilities

Before you can reason about adversaries, you need to understand what the system makes possible. From a user's perspective:

- **What does this system let you do?** What actions, communications, or transactions does it enable?
- **What information does it expose?** What data becomes available to users that wasn't accessible before? What about data available at scale (e.g., aggregating public information to enable surveillance)?
- **What resources does the system contain?** Both intentionally available resources (user data, financial instruments, communication channels) and resources stored within it (credentials, internal databases, computational resources).
- **What does someone need to access these capabilities?** An account? Special permissions? Physical presence? Technical expertise? Money?

Think about capabilities broadly — not just the intended use cases, but what the system *enables* regardless of intent.

### Step 2: Brainstorm adversaries and goals

Now brainstorm as many adversaries as you can — people or groups who might try to achieve something with the system that isn't aligned with its goals. For each, identify:

- A reference **name** so we can talk about them
- **Who** they are (a brief characterization)
- **What** they are trying to achieve
- A brief description of **how** they might use the system to achieve it

Think broadly about motivations:

- **Personal**: Revenge, jealousy, obsession, stalking, harassment, settling scores
- **Financial**: Fraud, extortion, blackmail, selling stolen data, running scams, gaming reward systems
- **Political**: Influencing elections, suppressing dissent, propaganda, terrorism, undermining institutions
- **Military/intelligence**: Espionage, sabotage, surveillance, disrupting enemy operations
- **Acting on another's behalf**: Working for organized crime, intelligence services, or powerful individuals; acting under coercion or threat
- **Organizational self-interest**: Profiting at public expense, seeking political power, suppressing evidence of wrongdoing, capturing regulators, controlling narratives

Goals may be **targeted** (wanting to affect a specific person or group) or **untargeted** (wanting to affect someone, but exactly who doesn't matter).

For each candidate adversary, do a quick sanity check:

- Is there a practical way for them to achieve this? If not, discard.
- Does it lead to harm we actually care about? If not, discard.

**Group by means**: If multiple adversaries would all have to achieve their goal in basically the same way, group them as a single "family." Characterize adversaries by their goals *and* their means, and group by means. This prevents redundant analysis downstream.

### Step 3: Refine by adversary capabilities

Now look at each adversary group and consider what resources they might bring to bear. Split groups further when different capabilities lead to materially different approaches.

Key capability dimensions:

- **Advanced threats** have access to special technical capabilities (e.g., zero-day exploits). Typically security researchers or nation-state actors. Relevant only if such capabilities enable a qualitatively different approach *and* the goal is worth the resource expenditure — you only blow a zero-day on something that's really worth it.
- **Persistent threats** have the resources to keep trying indefinitely. Well-resourced nation-states have this capability, but so do obsessive individuals with nothing more important to do.
- **Privileged threats** have some kind of special access — a police officer who is also a stalker, a system administrator with a grudge, an employee with database access. Always assume privileged threat actors will exploit their access to its fullest.
- **Intimate threats** have access to a target's private life — family members, intimate partners, ex-partners. They may know daily routines, have physical access to devices, know security question answers, or be able to access medical/financial records.
- **Specialized skills** in relevant domains change what's feasible. A demolitions expert planning a bombing is different from an amateur. A social engineer is different from a script kiddie.
- **Impunity**: Some actors can ignore consequences — diplomatic or sovereign immunity, control over the legal system, enough wealth to escape consequences, social position that makes conviction unlikely.
- **The competent evil genius vs. the random asshole**: The average bad actor is not a criminal mastermind. The overwhelming majority of people who cause harm do so through poor impulse control, entitlement, and opportunity — not through sophisticated planning. True "competent evil geniuses" are rare. Separately consider threats from relatively unsophisticated actors who stumble into opportunities, and threats from highly capable actors who plan carefully.
- **Ability to hire**: Even without personal capabilities, adversaries with resources can hire specialists. Nation-states can hire top-tier security researchers; wealthy individuals can hire private investigators; organized crime can hire technical talent.

For each adversary, if any of these dimensions materially changes the means they would use, split into subgroups.

At the end of this step, each adversary should be characterized with **a name, goal, resources, and means.** If any adversary is not already captured in `goal/stakeholders.md`, use `record_suggestion` to propose adding them with all of these details.

### Step 4: Characterize the failures

Now turn each adversary profile into one or more failure modes. The failure description should characterize:

- The adversary (who they are, what they want)
- Their means (briefly, how they would go about it)
- The resulting harm (to whom, and how)

If you can see the failure chain — the sequence of events from the adversary's initial action through harm — include it. The chain should include:

- What the adversary does at each step
- What resources or capabilities each step requires
- Where intervention is possible
- Where harm begins and ends

For the `pre_existing` flag: consider whether this adversary and this kind of attack exist regardless of this system. Many adversarial threats (phishing, social engineering, insider threats) are pre-existing. The question is whether this system creates *new* adversaries, gives existing adversaries *new capabilities*, or makes existing attacks *significantly easier*.

## Worked Example: A Photo Sharing Service

An online service where people upload and share photos with friends or the public.

**Step 1 — Capabilities**: The service lets users send images to specific people or disseminate them broadly. It lets people view others' images, which contain implicit information about people and places. At scale, this enables questions like "where has this person been?" — especially if the service provides search-by-image. The system contains both public data (broadly shared photos) and private data (limited-sharing photos, which are likely more personal and intimate). Sexual photos are a particularly high-value category for blackmail.

**Step 2 — Adversaries and goals**:

- Adversaries who want to **hack the system** to acquire private data or public data in bulk, for criminal or intelligence purposes.
- Adversaries who want to **target a specific user** and acquire their data via hacking their device or social engineering — usually personal or financial goals.
- Adversaries who want to **use service features to stalk someone** by extracting location and association information from photos. Depends on whether features like search-by-image exist.
- Adversaries who want to **acquire the image database** to build surveillance tools — for personal use (stalkers), commercial sale, or intelligence purposes.

Grouped by means: hack the system, target a user, exploit service features, acquire the database.

**Step 3 — Refine by capabilities**:

1. **Hackers attacking the system**: Need hacking skills (had or hired). Advanced threats possible but nothing here likely warrants blowing a zero-day. Not split further.
2. **A personal enemy**: May approach via hacking or social engineering. Intimate threats (ex-partners) and persistent threats have huge advantages. If targets are high-value (politicians), advanced threats become relevant.
3. **The stalker**: Depends on service features, not hacking. Ranges from random individuals to intelligence agencies. Nearly no technical capability required if the service provides search-by-image.
4. **The database acquirer**: Depends on how easy scraping is. Ranges from simple scripting to sophisticated cyberattack.

**Step 4 — Failures**: Each adversary produces a failure mode. For example:

> **A personal enemy compromises a user's account.** An adversary targets a specific individual to gain access to their private data or impersonate them, usually for personal reasons. They may use cyberattacks or social engineering against the user, their devices, or their account. Intimate threats (ex-partners) and persistent threats have particular advantages. Private data (especially intimate photos) may then be used for blackmail, harassment, or reputational harm.

## Output Format

For each adversarial failure identified, record a raw failure mode containing:

- **Title**: Short descriptive title identifying the adversary and what they achieve
- **Source**: `adversarial-analysis-thinker`
- **Description**: 1-3 sentences describing the adversary, their goal, their means, and the resulting harm. Must end in actual harm.
- **Additional context** (optional): More detail about the adversary's resources, the attack's feasibility, the severity of harm. Include initial thoughts about the failure chain if you can see it.
- **Pre-existing** (optional): True if this adversary and this kind of attack exist at similar or greater severity before this solution is implemented.
- **Failure chain** (optional): The sequence of events from the adversary's initial action through harm and recovery.

Keep raw failures lightweight. The goal is to capture the adversary-threat pair, not to fully analyze it. Full chains and management strategies are developed in later stages.

**Suggestions**: When your analysis identifies adversarial stakeholders not currently in the project's stakeholder document, use `record_suggestion` to propose adding them. Include the adversary's name, characterization, goals, resources, and means — specific enough that someone can act on the suggestion without redoing the analysis.

## Cross-Domain Considerations

Adversarial analysis interacts with other domains:

- **Security**: Adversaries identified here are the "who" behind the "what" of security vulnerabilities. Security analysis should consider these specific threat actors rather than generic attackers.
- **Privacy**: Many adversarial goals involve acquiring, exposing, or misusing private data.
- **Human factors**: Social engineering attacks exploit human factors failures. Insider threats bridge adversarial intent and privileged access.
- **Scalability**: Some attacks only become viable at scale (e.g., data aggregation for surveillance), while some defenses become harder at scale.
- **Legal/regulatory**: Some adversaries operate within legal gray areas or exploit regulatory gaps. Compliance requirements may constrain defensive options.

When identifying adversarial failures, note these cross-domain interactions in the additional context — they help during failure analysis and grouping.

## Using This Thinker

This thinker is invoked by the failure brainstorming process. The AI reads this guide (via `read_thinker_guide`) and applies its methodology, recording failures via the `record_failure` tool and suggestions via the `record_suggestion` tool.

In either mode, the thinker examines the problem statement, stakeholder list, solution description, and architecture (if available) to identify adversarial threats.

Work through all four steps in order — the process is sequential, not a checklist. The early steps (capability inventory, adversary brainstorming) should be broad and creative; the later steps (capability refinement, failure characterization) narrow the field to actionable threats.

For each adversary:

1. Identify who they are, what they want, and why
2. Consider what resources and capabilities they have
3. Assess whether the means are practical for this system
4. Record the resulting failure mode, framing the failure as a threat (not a vulnerability)
5. If the adversary isn't in the stakeholder document, record a suggestion to add them

The output is a set of raw failure modes plus suggestions for stakeholder document updates. Failures will later be grouped, analyzed, and developed into full failure mode documents with chains and management plans.
