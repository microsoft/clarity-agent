# Architecture

## Core Abstractions

**Nouns:** Album, Category, Assignment, Inbox.

- **Album**: A Spotify-saved album. Metadata (title, artists, cover art, Spotify URI) comes from Spotify; organizational state (assignments) lives in Firestore.
- **Category**: A named, spatially-positioned bucket the user creates. The Inbox is a permanent special-case Category.
- **Assignment**: The relationship between an Album and a Category. Carries a sort key (a string the user types, used to order albums within a Category). An Album can have many Assignments; each is independent.
- **Inbox**: A system-managed Category. Albums land here when newly synced from Spotify and have no other assignments. Cannot be renamed or deleted.

**Verbs:** Sync (pull Spotify library into Firestore), Assign (place an Album in a Category with a sort key), Move (reassign), Browse (navigate the spatial layout), Play (open album in Spotify).

---

## Components

### Frontend (React, Firebase Hosting)

The primary interface. Handles all browsing, organizing, and presentation. Calls Spotify's Web API directly for library data (using the access token from Firestore). Listens to Firestore in real time for organization state.

**Key responsibilities:**
- Spatial category layout (browsing mode)
- Shelf view within categories (text-based, sorted by sort key)
- Organize workflow: right-click → autocomplete category → autocomplete sort key → write Assignment to Firestore
- Undo stack: in-memory stack of recent Assignment writes; undo reverses the most recent write and propagates to Firestore
- Undo toast: after every Assignment write, show a toast ("Added to [Category] — Undo") for ~4 seconds
- Deep link with fallback: fire `spotify://album/{id}`, set 500ms timeout; if no `visibilitychange`/`blur` fires, open `https://open.spotify.com/album/{id}` in new tab; always show a visible web link too
- Graceful degradation: if Spotify API is unavailable, serve cached Firestore data with "last synced X ago" notice
- Auth error states: typed handling for token expiry (transparent), refresh failure (reconnect prompt), unknown error (retry prompt) — never blank screens

**Spatial layout:**
- Layout approach (CSS Grid/Flexbox vs. relative positioning vs. free-form canvas) to be determined during prototyping. Must be evaluated for cross-device behavior before commitment — see failure-11.
- Category positions stored in Firestore per device class (mobile and desktop stored separately). Prevents desktop layout bleeding into mobile view.
- If free-form canvas is chosen: pan/zoom with touch and mouse support; positions as percentage of viewport rather than absolute pixels where feasible.

### Cloud Functions (GCP)

Minimal backend. Handles only what can't run client-side safely: OAuth flow and token refresh. The client secret never touches the browser.

**Endpoints:**
- `GET /auth/spotify` — initiates OAuth flow, redirects to Spotify
- `GET /auth/callback` — handles OAuth callback, exchanges code for tokens, stores in Firestore, returns session
- `POST /auth/refresh` — called by frontend when access token is near expiry; refreshes and updates Firestore

**Token management:**
- Frontend proactively calls `/auth/refresh` when access token has <5 minutes remaining — eliminates most auth failures before the user notices
- Refresh failure (revoked token, password change) returns a typed error code; frontend shows "Reconnect with Spotify" prompt

### Firestore (GCP)

Stores all organizational state and tokens. Real-time listeners power cross-device sync.

**Data model:**

```
users/{userId}/
  spotifyTokens/
    accessToken: string        # short-lived; refreshed proactively
    refreshToken: string       # long-lived
    expiresAt: timestamp

  meta/
    lastSpotifySync: timestamp
    spotifyAlbumIds: string[]  # full set of known Spotify album IDs for reconciliation

  categories/{categoryId}/
    name: string
    positions/
      desktop: { x: number, y: number }
      mobile: { x: number, y: number }
    createdAt: timestamp
    isInbox: boolean

  albums/{albumId}/
    spotifyId: string
    spotifyUri: string
    title: string
    artists: string[]
    coverArt: string (url)
    addedAt: timestamp
    removedFromSpotify: boolean   # true if no longer in Spotify library; shown dimmed

  assignments/{assignmentId}/
    albumId: string
    categoryId: string
    sortKey: string
    assignedAt: timestamp
```

**Security rules:** Only the authenticated Firebase user can read or write their own `users/{userId}/` subtree. Rules are set before first deployment and reviewed in the deployment checklist (failure-08 management).

**Sync reconciliation:** On each app open, frontend fetches the current full Spotify album ID set and compares against `meta/spotifyAlbumIds`. New IDs → add Albums and Inbox Assignments. Missing IDs → set `removedFromSpotify: true` on those Albums (shown dimmed; removed on next manual "Sync now"). This bidirectional reconciliation prevents ghost entries (failure-04).

### Spotify Web API (External)

Source of album metadata and library state. Called directly from the frontend using the access token. Rate limits are avoided by incremental sync (only albums added since `lastSpotifySync` on normal syncs; full reconciliation only when needed).

---

## Key Flows

### Initial Setup

1. User visits app → no session found → frontend redirects to `/auth/spotify`
2. Cloud Function redirects to Spotify OAuth consent screen
3. User grants access → Spotify redirects to `/auth/callback`
4. Cloud Function exchanges code for tokens, stores in Firestore, returns session cookie
5. Frontend fetches initial library from Spotify API, writes Albums + Inbox Assignments to Firestore
6. Albums appear in Inbox

### On Every App Open (Sync)

1. Frontend checks token expiry; calls `/auth/refresh` if <5 min remaining
2. Fetches Spotify albums added since `lastSpotifySync` → adds to Firestore + Inbox
3. Fetches full Spotify album ID set → reconciles against `meta/spotifyAlbumIds` → marks removed albums
4. Updates `lastSpotifySync`
5. Firestore real-time listeners update UI

### Organizing (Assign)

1. User right-clicks album → context menu appears
2. User types category name → autocomplete from existing categories (recently-used ranked first)
3. User types sort key → autocomplete from album metadata fields
4. Frontend writes Assignment to Firestore
5. Undo toast shown ("Added to [Category] — Undo"); undo stack updated
6. Firestore listener updates UI on all connected devices within seconds

### Browsing & Playing

1. User sees spatial category layout
2. Taps/clicks category → sees shelf view (albums sorted by sort key, text-based)
3. Taps/clicks album → `spotify://album/{id}` fired + 500ms timeout started
4. If Spotify app opens: done. If timeout fires without navigation: `open.spotify.com/album/{id}` opens in new tab
5. Visible "Open in Spotify" web link always present as explicit alternative

---

## Cross-Cutting Concerns

### Auth & Security

- Client secret lives only in Cloud Functions (never in frontend bundle)
- Spotify tokens stored in Firestore under strict security rules: authenticated user reads only their own subtree
- Access token proactively refreshed; refresh failures surface typed error states
- Deployment checklist includes Firestore security rules review before any deploy

### Reliability & Graceful Degradation

- All Spotify API failures degrade to cached Firestore data + "last synced X ago" notice — app remains browsable
- All Cloud Function calls show loading state immediately (cold start cosmetic mitigation)
- Typed error handling throughout: 401 → auth flow, 429 → backoff, 5xx → retry, unexpected schema → log + surface in doctor

### "Doctor" Command

A dev script (and/or in-app diagnostics panel) that checks system health and returns plain-language status + next steps:

- Spotify token validity (valid / expiring soon / invalid)
- Firestore connectivity
- Last successful sync timestamp
- GCP quota usage (Cloud Functions invocations, Firestore reads/writes)
- Any logged API errors since last check

Run when something feels wrong. Replaces needing to know which GCP console page to check.

### Data Export

A "Download my library" function accessible from the app exports the full organizational state as a portable JSON file:

```json
{
  "exportedAt": "...",
  "categories": [{ "name": "...", "id": "..." }],
  "albums": [{ "spotifyId": "...", "title": "...", "artists": [...] }],
  "assignments": [{ "albumId": "...", "categoryId": "...", "sortKey": "..." }]
}
```

Available even if Spotify sync is broken. Protects against data loss from GCP account issues (failure-07) and makes abandonment low-stakes (failure-09).

### Infrastructure

- Firebase Hosting: static CDN hosting for frontend
- Cloud Functions: serverless, no maintenance; cold start mitigated by loading states
- GCP billing: enabled with a spending cap (e.g., $5/month); quota alerts configured at 80% to catch runaway bugs before the app breaks
- Firestore writes: idempotent and bounded; no unbounded read-triggered write loops

---

## Open Questions / Prototyping Decisions

**Q1 — Spatial layout approach:** The choice between CSS Grid/Flexbox, relative positioning, and free-form 2D canvas must be made during prototyping by testing on both phone and desktop. Cross-device behavior is the primary evaluation criterion. This decision has downstream implications for Firestore position storage (per-device vs. shared) and mobile UX. See failure-11.

**Q2 — Ghost album handling:** When `removedFromSpotify` is true, show dimmed in category with a "no longer in your library" indicator. On click, prompt "Remove from collection?" rather than attempting the deep link. Full removal happens on next "Sync now" or immediate on confirmation.

**Q3 — Inbox sort order:** Requirements say "date added, newest to oldest or vice versa" — needs a user preference. Simple toggle, default newest-first.
