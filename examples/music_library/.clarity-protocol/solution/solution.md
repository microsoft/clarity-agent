# Solution

## Overview

A serverless web application hosted on GCP that provides a spatial, visual interface for organizing and browsing Spotify albums. The app recreates the experience of browsing physical record shelves while leveraging cloud infrastructure for automatic cross-device synchronization.

## Architecture

### Frontend
**Technology:** React
- Responsive web app that works on mobile and desktop
- Client-side rendering with state management (likely Context API or simple state lib)
- Direct integration with Spotify Web API for fetching library data
- Visual components for spatial category layout and shelf browsing
- Real-time Firestore listeners for instant cross-device sync

### Backend
**Technology:** Cloud Functions (GCP)
**Purpose:** Minimal backend handling only what can't run client-side
- **OAuth proxy**: Spotify OAuth flow (required for security - can't expose client secret in browser)
- **Token management**: Refresh Spotify access tokens
- **API endpoints:**
  - `/auth/spotify` - Initiate OAuth flow
  - `/auth/callback` - Handle OAuth callback
  - `/auth/refresh` - Refresh access token

### Data Storage
**Technology:** Firestore (GCP's NoSQL database)
**Data model:**

```
users/{userId}/
  - spotifyTokens: { accessToken, refreshToken, expiresAt }
  - lastSync: timestamp

  categories/{categoryId}/
    - name: string
    - position: { x: number, y: number }
    - createdAt: timestamp

  albums/{albumId}/
    - spotifyId: string
    - spotifyUri: string
    - title: string
    - artists: string[]
    - coverArt: string (url)
    - addedAt: timestamp (from Spotify)
    - assignments: [
        { categoryId: string, sortKey: string }
      ]
```

**Why Firestore:**
- Real-time sync built-in (perfect for multi-device)
- Generous free tier (more than enough for single user)
- Simple document model matches our data structure
- Works seamlessly with Cloud Functions

### Hosting
**Technology:** Firebase Hosting (part of GCP)
- Static hosting for the frontend app
- CDN included for fast loading
- Free SSL certificates
- Custom domain support if desired

### Spotify Integration
**API calls from frontend:**
- `GET /me/albums` - Fetch user's saved albums
- Album metadata already returned includes artists array for autocomplete

**Deep linking:**
- Use `spotify:album:{id}` URIs to open albums in Spotify app
- Fallback to `open.spotify.com` URLs for web

## Key Workflows

### Initial Setup & Authentication
1. User visits app URL
2. Click "Connect with Spotify"
3. Cloud Function handles OAuth flow
4. Tokens stored in Firestore, session cookie returned
5. Frontend fetches initial library from Spotify API
6. Albums appear in Inbox category

### Organizing Albums
1. User right-clicks album in any category (including Inbox)
2. Context menu: "Move to..." or "Add to..."
3. Type category name (autocomplete from existing categories)
4. Type sort key (autocomplete from album's artists)
5. Frontend writes assignment to Firestore
6. Firestore real-time listener updates UI immediately
7. Other devices see change within seconds

### Browsing & Playing
1. User opens app, sees spatial layout of categories
2. Navigate to a category (click/tap)
3. View albums as text-based "shelf" sorted by their sort keys
4. Click album
5. Browser opens `spotify:album:{id}` URI
6. Spotify app opens to that album

### Sync Between Devices
1. User saves new album in Spotify mobile app
2. Next time they open the web app (any device):
   - Frontend checks Spotify API for new albums
   - New albums added to Firestore with Inbox assignment
   - Real-time listener updates UI
3. Organization changes sync automatically via Firestore

## Technical Decisions

### Why serverless over traditional server?
- No server maintenance
- Auto-scaling (though not needed for single user)
- Pay only for usage (essentially free for personal use)
- Simpler deployment

### Why Firestore over SQL?
- Real-time sync is built-in
- Document model matches our data naturally
- No schema migrations needed
- Generous free tier
- Simpler for this use case than managing PostgreSQL

### Why React?
- Need rich, interactive UI for spatial layout and drag-drop
- Component-based architecture fits well (Category component, Album component, etc.)
- Large ecosystem for UI components
- Excellent Firestore integration via Firebase SDK
- User preference

## Open Implementation Questions

### Q1: Category Rearrangement UX
- Drag and drop on desktop?
- Touch and hold to drag on mobile?
- Separate "edit layout" mode vs. always editable?

### Q2a: Spatial Layout Details
**Status:** Will be determined through experimentation during implementation
**Options to try:**
- Free-form 2D canvas with pan/zoom
- Grid-based with snap-to-grid
- CSS Grid/Flexbox web-native layout

Will prototype different approaches on both mobile and desktop to find what feels right.

## Next Steps

1. Set up GCP project structure (Firebase, Cloud Functions)
2. Implement OAuth flow and Spotify API integration
3. Build data model in Firestore
4. Prototype spatial layout options (addresses Q1)
5. Implement core organizing workflow
6. Implement browsing and deep linking
7. Polish UI and interactions
8. Test cross-device sync
