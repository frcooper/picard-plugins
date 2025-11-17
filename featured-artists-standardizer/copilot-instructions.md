# Copilot instructions for Featured Artists — Standardizer

Context: This folder contains the `Featured Artists — Standardizer` plugin (`feat_standardizer.py`). It enforces label-style handling of featured artists on both track and album level.

Key behaviors
- Track level: Move featured artists from `ARTIST` into `TITLE` suffix `(feat. A; B)` exactly once; keep only the lead artist in `ARTIST` / `artistsort`.
- Album level: If `ALBUMARTIST` contains a feature token, move the guests into `ALBUM` as `(feat. …)` and keep `ALBUMARTIST` / `albumartistsort` as the lead artist. Skip Various Artists.
- Tokens: Recognize `feat.`, `featuring`, and `with` (case-insensitive).
- Splitting: Split guests on commas, `&`, `+`, `;`, ` and `, and ` / ` (slash only with spaces) but NOT bare `/` (so names like `AC/DC` are safe).
- Normalization: De-duplicate guests case-insensitively while preserving order, and normalize separators to `; ` inside the `(feat. …)` suffix.
- Integration: Includes the behavior of the third-party `Standardise Feat.` plugin by normalizing join phrases like `ft`, `ft.`, `featuring` to `feat.` before further processing.
- Whitelist: A configurable whitelist of exact artist credits that should never be altered. If a full credit or its lead artist is whitelisted, no changes at all are applied to that credit.
- Optional tag: When enabled in settings, writes a multivalue `FEATURED_ARTISTS` tag with the normalized guest list.

Implementation notes
- Keep logic idempotent: never append multiple `(feat. …)` suffixes and avoid re-processing already-normalized strings.
- Prefer small, composable helpers for parsing, splitting, and normalization. Reuse `_split_artist_feat`, `_normalize_feat_list`, `_parse_whitelist`, and `_standardize_join_phrases` instead of duplicating logic.
- Any new behavior that changes tagging/renaming should log via `log.debug` with the `"Featured Artists:"` prefix.

Config & UI
- Settings live in `PLUGIN_OPTIONS` (currently a `BoolOption` for `add_featured_artists_tag` and a `TextOption` for `featured_artists_whitelist`).
- The options UI is implemented by `FeaturedArtistsOptionsPage` and should be expanded in-place if new options are added. Build widgets directly on `self` and keep `self.ui = self`.

Versioning
- When you change normalization rules, whitelist behavior, or config surface, bump `PLUGIN_VERSION` appropriately (patch for bugfix, minor for behavior/config additions).

Testing tips
- Use Picard's debug log to verify transformations. Log both decisions (e.g. skipping due to whitelist) and resulting values (new title/album strings).
- Test edge cases such as: multiple features, duplicate guests, names with `/`, and credits that already contain `(feat. …)`.
