# Spotify Music Library Organizer

A personal web app that lets you organize your Spotify library like a physical record collection — create custom categories, arrange them spatially on screen, and browse by mood or vibe instead of Spotify's algorithm. React + GCP serverless architecture with real-time cross-device sync.

## The Problem

Spotify only offers algorithmic organization and alphabetical lists. You can't arrange your music library the way you could with physical records — grouped by custom categories (mood, genre, composer/performer), spatially positioned in a way that matches your mental model, and browsable by intuition rather than search.

## The Solution

A serverless React web app that:
- Syncs your Spotify saved albums and playlists
- Lets you create custom categories and assign albums to them (albums can be in multiple categories)
- Displays categories in a spatial layout you can navigate
- Shows albums as text-based "shelves" within each category, sorted by keys you choose (composer, performer, title, etc.)
- Clicking an album opens it in Spotify to play
- Automatically syncs organization across all your devices (phone and desktop)

## Tech Stack

**Frontend:** React, responsive web app
**Backend:** Cloud Functions on GCP (minimal — just OAuth proxy)
**Database:** Firestore (real-time sync, NoSQL)
**Hosting:** Firebase Hosting
**Integration:** Spotify Web API for library data, deep links for playback

## Key Design Principles

1. **Simplicity over features** — Recreate the physical browsing experience, not a feature-rich music manager
2. **Spatial organization** — Categories have consistent positions you can remember
3. **Flexible sorting** — Each album-category pair has its own sort key (classical sorted by composer, jazz by performer, etc.)
4. **Friction-free reorganization** — No physical shelf-space constraints
5. **Automatic sync** — Changes propagate instantly across devices

## Current Status

**Planning complete** — Problem defined, architecture designed, failure modes identified. Ready to implement.

**Next steps:**
1. Set up GCP/Firebase project
2. Implement Spotify OAuth flow
3. Build Firestore data model
4. Prototype spatial layout (open question: best approach for mobile + desktop)
5. Implement organizing workflow
6. Implement browsing and deep linking
7. Test cross-device sync
