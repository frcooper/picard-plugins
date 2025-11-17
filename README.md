# Picard Plugins

This repository contains a small collection of custom plugins for [MusicBrainz Picard](https://picard.musicbrainz.org/). All plugins target Picard 2.x.

## Plugins

### Featured Artists — Standardizer (`featured-artists-standardizer/feat_standardizer.py`)

- Standardizes how featured artists are represented at both track and album level.
- Track level: moves featured artists from `ARTIST` into the `TITLE` suffix `(feat. A; B)` once, keeping the lead artist in `ARTIST`/`artistsort`.
- Album level: pulls features out of `ALBUMARTIST` into the `ALBUM` title `(feat. …)`, skipping "Various Artists".
- Normalizes separators, de-duplicates guests, and optionally exposes a `FEATURED_ARTISTS` tag.
- Includes a configurable whitelist of artist credits that should never be altered.

### Guardrails — collision-aware renamer (experimental) (`file-collision-protection/guardrails.py`)

- Experimental plugin that watches for Picard's " (n)" filename collision suffix after saves.
- On normal mode: sets `_guardrails_has_collision` and immediately re-runs Picard's naming logic so your script can switch to an alternate template.
- On fatal mode: treats collisions as errors, attempting to roll back the rename/move to the original path when possible.
- Provides the `$collides()` script function to let naming scripts react cleanly to collisions.

### Asciifier — to_ascii() (`asciifier/to_ascii.py`)

- Provides the `$asciify()` script function for converting strings to ASCII-safe equivalents.
- Uses a replacement table based on the classic `Non-ASCII Equivalents` plugin, split into configurable maps (`alpha`, `punct`, `math`, `other`).
- Maps can be enabled/disabled and edited from an options page; you can add your own maps or clear the defaults to make the plugin a no-op.
- Optional automatic mode can clean a configurable list of tags (e.g. album, artist, title) on album/track processing.

