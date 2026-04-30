# Open Questions

## Q1: Composer Metadata Availability
**Status:** resolved
**Resolution:** Spotify API doesn't distinguish composer from performer

**Finding:** The Spotify API provides an `artists` array for each album, where each artist has a `name` field. There's no dedicated "composer" field, and no way to distinguish composers from performers in the API response. For classical albums, both composers and performers appear in the artists array without differentiation.

**Impact on design:** The user-entered string approach for sort keys (requirement R6) handles this perfectly. When organizing a classical album, the user types the relevant name (composer or performer) as the sort key, with autocomplete suggestions from the artists array. This gives flexibility without depending on metadata that doesn't exist.

**Sources:**
- [Web API Reference | Spotify for Developers](https://developer.spotify.com/documentation/web-api/reference/get-an-album)
- [Concertmaster - Classical music front-end for Spotify](https://getconcertmaster.com/) (uses external Open Opus library to supplement Spotify data)

## Q2: Spatial Layout Implementation
**Status:** open
**Strategy:** prototyping

**Question:** What does "spatial layout" actually look like in practice? How literal should the positioning be?

**Why it matters:** This is core to the browsing experience but vaguely defined. Need to understand the trade-offs between:
- Free-form 2D positioning (pan around a space)
- Grid layout with consistent positions
- Something else entirely

**Considerations:**
- Must work on both mobile (small screen, touch) and desktop (large screen, mouse/keyboard)
- Must feel consistent enough that user remembers where categories are
- Must support manual rearrangement
- Performance with dozens of categories

**Next steps:** Build quick prototypes to see what feels right in practice
