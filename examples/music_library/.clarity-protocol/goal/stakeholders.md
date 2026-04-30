# Stakeholders

## Primary User

**The user (builder and sole user)**

*Needs:*
- Personal music organization system that matches their mental model
- Spatial, visual browsing experience that evokes physical record collections
- Ability to organize albums by custom categories (mood, genre, composer/performer as relevant)
- Multi-device access (phone and desktop)
- Simple, friction-free interface without feature creep

*Concerns:*
- Keeping the experience simple and physical-feeling
- Multi-device synchronization
- Time investment in building vs. value received

## Technical Dependencies

**Spotify API** ✅ Verified feasible

The Spotify Web API provides all necessary capabilities:
- `GET /me/albums` endpoint retrieves saved albums with metadata (titles, artists, cover art, URIs)
- Similar endpoints for playlists
- OAuth 2.0 authentication with `user-library-read` scope
- Deep linking via `spotify:album:id` URIs opens albums directly in Spotify app
- Fallback to `open.spotify.com` web URLs if app not installed
- Rate limits exist but won't be an issue for personal use with hundreds of albums
