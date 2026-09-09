---
title: Responsible AI review background
description: Guidance on Frontier Engineering Responsible AI reviews
---

## What is a Responsible AI review?

A Responsible AI (RAI) review is a way for Frontier Engineering to support all our engagements in upholding Microsoft's RAI principles. It builds our organizational knowledge on the topic, enables teams to get an outside perspective on their engagements, and helps us put Microsoft's RAI principles into practice.

It also contributes to the trusted partnership we build with our customers, who frequently provide positive feedback on the opportunity to engage on this topic, and even bring their own responsible AI teams into the process.

By securing AI system benefits and identifying and mitigating negative impacts, we help our customers envision their AI transformation responsibly and in compliance with emerging regulations governing AI technologies. This work mitigates the risk of human, reputational, and financial harm to Microsoft and upholds our legal obligations.

This process must start as early as possible and be revisited as the scope and nature of the engagement evolve. Customers should also be engaged by communicating our RAI commitments up front, collaborating with them on the Impact Assessment, and sharing any resulting guidance as input into the work.

The process entails completing an Impact Assessment document with your team and submitting it for review by the Frontier Engineering RAI Review committee. The Impact Assessment captures key information and risks relating to the Responsible AI Standard.

## Which engagements are in scope for a Frontier Engineering Responsible AI review?

All customer-facing, co-engineering engagements (MVE, MVP, and advisory) that use AI and involve sharing code require a Frontier Engineering RAI review. This includes projects where Frontier Engineering provides code samples or chat prompts to a customer.

For accelerators or internal tools that do not use AI directly but contain chat prompts, a Frontier Engineering RAI review is required. Also see the MCAPS guidance, *Responsible use of AI for MCAPS*.

## Does my hack project need a RAI Impact Assessment and a FE RAI Review?

Hack projects are experimental by nature, but RAI principles still apply: fairness, reliability and safety, privacy and security, inclusiveness, transparency, and accountability.

Whether you need a RAI Impact Assessment and a FE RAI Review depends on where the hack runs and what happens afterward:

* Microsoft tenant, throwaway, and no handoff: No submission is required. Still hold the RAI conversation with your team.

* Customer tenant, handed off, or continuing after the hack: Complete the FE RAI Review process, including the RAI Impact Assessment, before handoff.

* Already covered by an existing project RAI Impact Assessment: Confirm that it includes the hack scope.

One exception applies to these tenant-based rules: if your hack involves Restricted Uses or Sensitive Uses, talk to your Studio RAI Champ first, even if the hack is temporary and stays in a Microsoft tenant.

## How can I mitigate risks?

When we identify risks relating to RAI, how do we mitigate those risks and implement RAI in real-world contexts? Effective strategies depend on a wide range of factors, including the people affected, the environment in which the product will be used, the severity of the potential harms, and the maturity of the technology being developed.

There is no single mitigation strategy, but several resources within Frontier Engineering can guide you through the RAI journey. Including mitigations for RAI-related risks in your submission to the Frontier Engineering RAI Review team and in the ORA submission forms can help speed your review.

As the project progresses, consider whether red teaming would help refine mitigation strategies. Red teaming is a structured process for probing AI systems and products to identify harmful capabilities, outputs, or infrastructure threats.

Examples of mitigations from previous projects include:

* Data analysis of model accuracy for different demographic groups
* Documentation about the limitations of the training dataset
* UI warnings when model confidence is low
* Physical signage that makes people aware of recording

You can also use reusable assets and lessons from previous engagements. Engaging with the Frontier Engineering RAI Review and ORA Sensitive Use review will provide further mitigation guidance relevant to your project.

## Six Responsible AI principles

There are six Responsible AI principles:

* Fairness
* Transparency
* Accountability
* Reliability and safety
* Security and privacy
* Inclusiveness