# Requirements

## Data Sync & Integration

**R1**: The system shall sync with Spotify to retrieve the user's saved/liked albums and playlists
- Uses Spotify Web API with OAuth 2.0 and `user-library-read` scope
- Retrieves album metadata: title, artist(s), composer (if available), cover art, Spotify URI

**R2**: The system shall automatically detect new albums added to Spotify library
- New albums appear in the Inbox category
- Sync happens automatically across devices

**R3**: The system shall maintain organization data (categories, assignments, sort keys) with automatic sync between devices
- User's organization persists between sessions
- Changes made on one device appear on other devices without manual refresh

## Organization Experience

**R4**: The system shall support user-defined categories
- User can create new categories
- User can rename categories
- User can delete categories (moves albums to Inbox/uncategorized)
- Categories persist across sessions

**R5**: Albums can be assigned to multiple categories simultaneously
- Same album can appear in different categories
- Removing from one category doesn't affect other assignments

**R6**: Each album-category assignment has an associated sort key (string)
- Sort key is typed during organization, with autocomplete suggestions from Spotify metadata fields (performer, composer, title, etc.)
- Albums within a category are alphabetized by their sort keys
- Missing metadata gracefully handled (empty string sorts first/last)
- Sort key is specific to each (album, category) pair, so same album can be sorted differently in different categories

**R7**: The Inbox is a special category that always exists
- Contains albums not yet organized into other categories
- Sorted by date added (newest to oldest, or vice versa)
- Cannot be deleted or renamed

**R8**: The organizing workflow shall be quick and keyboard-friendly
- Right-click (or equivalent gesture) on an album shows organization options
- "Move to category" (default): removes from current category, adds to target category
- "Add to category": keeps in current category, also adds to target category
- Type/autocomplete category name
- Type/autocomplete sort key for that assignment
- Album immediately appears in target category

**R8a**: Users can rearrange category positions in the spatial layout
- Manual repositioning of categories
- Positions persist across sessions

## Browsing Experience

**R9**: Categories shall be displayed in a spatial layout
- Visual positioning on screen is consistent
- User can learn where categories are located without reading labels
- Layout persists (categories don't move around randomly)

**R10**: Within a category, albums are displayed as text-based "shelf" view
- Shows information that would appear on album spine: title, performer/composer
- Highly legible text
- Displayed in order according to category's sort key

**R11**: User can navigate spatially to categories and browse albums within them
- Browsing mode is separate from organizing mode
- Focus is on finding music, not managing organization

**R12**: Selecting an album opens it in Spotify for playback
- Uses `spotify:album:id` URI for deep linking
- Falls back to `open.spotify.com` URL if Spotify app not installed
- Works on both mobile and desktop

## Platform & Performance

**R13**: Responsive web app that works on both phone and desktop
- Interface adapts to screen size
- Touch-friendly on mobile
- Keyboard-friendly on desktop
- Experience may differ between platforms as appropriate for each context

**R14**: System shall handle library size from dozens to hundreds of albums
- Performance remains acceptable as library grows
- UI remains navigable with large collections

## Out of Scope

The following are explicitly NOT requirements (maintaining simplicity):
- Search/filtering during browsing
- Play history or listening statistics
- Notes or ratings on albums
- Recommendations or discovery features
- Social features or sharing
- In-app playback (Spotify handles this)
- Custom album metadata beyond what Spotify provides
