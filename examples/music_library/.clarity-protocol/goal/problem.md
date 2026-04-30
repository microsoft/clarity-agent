# Problem Statement

Spotify users cannot arrange their music library in a personally meaningful way. Unlike physical record collections where albums could be spatially organized according to personal logic (mood, custom genre groupings, performer/composer as relevant), Spotify only offers algorithmic recommendations and alphabetical lists.

The user previously organized physical albums with:
- Classical music sorted by composer or performer (whichever was most relevant)
- Modern music grouped by performer, sometimes split by vibe
- Categories that evolved over time
- Spatial browsing that matched their mental model and current mood

This personal arrangement system enabled intuitive browsing — the user could go to a section that matched their mood and explore until finding what they wanted.

## Why This Matters

The user wants to build a personal tool that provides the browsing and organization experience they had with physical records, while keeping Spotify for playback and recommendations.

## Scope

- Pulls in the user's Spotify library (saved/liked albums and playlists)
- Provides a custom organization interface
- Hands off to Spotify for actual playback
- Personal tool (single user)
- Separates "organizing music" from "listening to music" as distinct activities
- Responsive web app (used on both phone and desktop)
- Library size: dozens currently, will grow to hundreds with better organization

## Desired Experience

The user wants to recreate the physical experience of browsing a record collection, keeping it simple and physical-feeling without digital feature creep.

**Browsing flow:**
- Categories displayed spatially (like rooms or shelves you can navigate to)
- Within a category, albums shown with text labels (since cover art doesn't translate to spine view)
- Selecting an album takes you to Spotify to see details and play

**Organizing flow:**
- Friction-free reorganization — no physical shelf-space constraints
- Albums can exist in multiple categories
- Moving things happens quickly without cascading physical rearrangements

**Workflow separation:**
- **Organizing mode**: Creating/renaming categories, assigning albums, reorganizing
- **Browsing/listening mode**: Finding and playing music
- **Inbox workflow**: New Spotify saves appear as "waiting to be organized" with quick action to file them

**Design philosophy:** Keep it simple. The value is in spatial, visual browsing that matches the user's mental model — not in adding digital features beyond what physical collections offered.

**Open question:** Whether categories should support nesting/hierarchy (user wants to experiment)

## Success Criteria

- Syncs user's Spotify saved/liked albums and playlists
- Spatial layout of categories that can be navigated
- Within categories, albums displayed with text labels
- Albums can be assigned to multiple categories
- Selecting an album opens it in Spotify
- New items appear in an inbox for quick organization
- Reorganization is friction-free (no physical constraints)
- Organization persists between sessions
- Experience stays simple — no feature creep beyond physical collection analog
