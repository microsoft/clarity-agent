# Notes

## Guiding Principles

**Simplicity over features**: The core value is recreating the physical record collection experience — spatial, visual browsing that matches the user's mental model. Resist adding digital features beyond what physical collections offered. The user explicitly doesn't want fancy features.

## Failure Analysis

**Consequence categories (user-defined, use in all failure work):** App stops working | Silent wrongness | Data loss | Behavioral traps | Experience degradation. These are more useful for design than a flat severity ranking — behavioral traps and silent wrongness are harder to detect and design against than "app stops working."

**Key cross-cutting interventions:** (1) Undo/change history addresses failures 05, 06, 10. (2) Data export de-risks both data loss and abandonment. (3) Sync must reconcile removals as well as additions. (4) Spatial layout responsiveness must be decided before building — retrofitting is hard.
