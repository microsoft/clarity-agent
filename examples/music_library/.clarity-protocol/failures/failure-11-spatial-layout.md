# Failure: Spatial Layout Breaks Across Screen Sizes

## Summary

Categories are positioned at absolute x/y coordinates in a shared layout. On a significantly different screen size — phone vs. desktop — the layout may render categories off-screen, overlapping, or too small to use comfortably. The core browsing experience (spatially navigating a visual collection) becomes degraded or unusable on one class of device.

**Consequence category: Experience degradation**

## Failure Chain

1. User arranges categories spatially on desktop — placing them where they feel right on a large canvas.
2. User opens the app on their phone (or vice versa).
3. The stored x/y positions are rendered on a canvas with very different dimensions.
4. **Harm begins.** Categories appear off-screen, overlap each other, or are scaled so small that text is unreadable and tap targets are unusable.
5. The spatial browsing experience — the core value of the tool — is broken on this device class.
   - *Intervention point (prevention):* Design the layout system to be responsive from the start: relative positions (percentage-based) or a layout system that adapts to viewport dimensions.
   - *Intervention point (mitigation):* A "reset layout" option that auto-arranges categories in a grid for the current viewport, without destroying the user's deliberate layout on other devices.
6. User either avoids using the app on that device or uses it in a degraded state.
7. **Harm ends** when layout system is made responsive or the user adjusts.

## Observations

- **Severity:** Medium — the app is technically functional (albums are still there, links still work) but the spatial browsing experience — the whole point — is broken on that device class. Multi-device usability was an explicit goal.
- **Observation:** This is a design decision that needs to be made early. Retrofitting a fixed-coordinate layout system to be responsive is significantly harder than building responsively from the start. The choice of spatial layout approach (free-form 2D, grid-based, CSS layout) has major implications here.
- **Related failures:** Behavioral traps (failure-09) — a poor mobile experience may cause the user to stop using the app on their phone, which is one of the intended device classes.
- **Variants:**
  - `20260302-201045` — Spatial layout breaks on different screen sizes

## Intervention Points

### Prevention
- Choose a layout approach that is responsive by design (CSS Grid/Flexbox, or relative positioning)
- Test the layout on both phone and desktop during initial prototyping (this is explicitly planned in the solution)

### Detection
- Test on both device classes before considering the layout "done"

### Mitigation
- "Fit to screen" or "auto-arrange" option that reflows categories for the current viewport
- Per-device layout overrides: store separate position data for mobile vs. desktop

### Recovery
- User manually repositions categories for the new screen size

---

## Management Plan

### Strategy

Prevention by design choice: pick a layout approach that is responsive by default, rather than building with absolute coordinates and retrofitting later. This is a decision that must be made before the spatial layout is built — it's noted as a constraint for architecture design. Per-device layout storage (separate positions for mobile vs. desktop) is the medium-term solution if the chosen approach can't adapt automatically.

### Planned Interventions

- **Responsive layout approach from the start**: During the spatial layout prototype phase (already planned in the solution), evaluate options specifically for cross-device behavior. CSS Grid/Flexbox or relative/percentage-based positioning handles viewport differences automatically. Free-form 2D canvas with absolute coordinates requires explicit adaptation logic.
  - Type: Prevention
  - Addresses: Chain steps 2–4 (fixed positions breaking on different viewports)
  - *Note: This is an architecture input — the layout system choice must be made before building.*

- **Cross-device testing during prototyping**: Test every spatial layout prototype on both phone and desktop before committing to an approach. This is already planned ("prototype different approaches on both mobile and desktop") — make cross-device behavior an explicit evaluation criterion.
  - Type: Detection
  - Addresses: Chain step 4 (breakage discovered after the layout system is built)

- **Per-device layout storage** *(if needed)*: If the chosen layout approach stores positions, store separate position sets for mobile and desktop viewports. Editing the layout on one device doesn't disrupt the other. Implement only if the chosen approach doesn't handle this automatically.
  - Type: Mitigation
  - Addresses: Chain step 3 (desktop layout applied unchanged to phone)

### Accepted Risks

- Some layout approaches that feel most natural spatially (free-form, drag-anywhere canvas) are inherently harder to make responsive. There may be a genuine tradeoff between layout freedom and cross-device consistency. That tradeoff is deferred to the prototyping phase, where it can be evaluated with real layouts rather than hypothetically.

### Monitoring

Manual: test on both device classes whenever the layout system changes.
