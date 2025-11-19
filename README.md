# Picard Plugins

This repository contains a small collection of custom plugins for [MusicBrainz Picard](https://picard.musicbrainz.org/). All plugins target Picard 2.x.

## Plugins

### Featured Artists — Standardizer (`featured-artists-standardizer/featured-artists-standardizer.py`)

- Standardizes how featured artists are represented at both track and album level.
- Track level: moves featured artists from `ARTIST` into the `TITLE` suffix `(feat. A; B)` once, keeping the lead artist in `ARTIST`/`artistsort`.
- Album level: pulls features out of `ALBUMARTIST` into the `ALBUM` title `(feat. …)`, skipping "Various Artists".
- Normalizes separators and de-duplicates guests while preserving order.
- Includes a configurable whitelist of artist credits that should never be altered.
- When the `Additional Artists Variables` plugin is installed, uses its primary/additional artist variables as the main source of lead vs guest artists, falling back to heuristic parsing otherwise.

### Asciifier — to_ascii() (`asciifier/asciifier.py`)

- Provides the `$asciify()` script function for converting strings to ASCII-safe equivalents.
- Uses a replacement table based on the classic `Non-ASCII Equivalents` plugin, split into configurable maps (`alpha`, `punct`, `math`, `other`).
- Maps can be enabled/disabled and edited from an options page; you can add your own maps or clear the defaults to make the plugin a no-op.
- Optional automatic mode can clean a configurable list of tags (e.g. album, artist, title) on album/track processing.

## Releases and automation

- GitHub Actions: On any pushed tag matching `*-vMAJOR.MINOR.PATCH`, the `Plugin Release` workflow runs.
  - It derives the plugin name from the tag prefix (e.g. `asciifier-v1.0.0` -> `asciifier`).
  - It validates that the version string is in `MAJOR.MINOR.PATCH` format.
  - It checks that the `PLUGIN_VERSION` defined in that plugin's `<plugin-name>.py` matches the tag version.
  - It builds a zip archive named `<plugin>-<version>.zip` from the plugin directory and publishes a GitHub Release attaching that archive.
- Helper scripts: To cut a release for a plugin from this repo root, you can use either script below (they both perform the same steps):
  - Bash: `./mk-plugin-release.sh <plugin-name> <MAJOR.MINOR.PATCH>`
  - PowerShell: `./mk-plugin-release.ps1 -PluginName <plugin-name> -Version <MAJOR.MINOR.PATCH>`

These scripts will:

1. Validate the version format.
2. Update the `PLUGIN_VERSION` line in `<plugin-name>/<plugin-name>.py`.
3. Commit the change with a semantic-style message (`chore(<plugin>): release vX.Y.Z`).
4. Create a tag `<plugin-name>-vX.Y.Z`.
5. Push the commit and tag to `origin`, which in turn triggers the GitHub Actions release workflow.

## Recommended plugins

These third-party plugins pair well with this collection:

- Additional Artists Variables — <https://github.com/rdswift/picard-plugins/tree/master/plugins/additional_artists_variables>
- Standardise Performers — <https://github.com/Sobak/picard-plugins/tree/master/plugins/standardise_performers>

## Experimental - Seriously

### Guardrails — collision-aware renamer (`file-collision-protection/file-collision-protection.py`)

- Experimental plugin that watches for Picard's " (n)" filename collision suffix after saves.
- On normal mode: sets `_guardrails_has_collision` and immediately re-runs Picard's naming logic so your script can switch to an alternate template.
- On fatal mode: treats collisions as errors, attempting to roll back the rename/move to the original path when possible.
- Provides the `$collides()` script function to let naming scripts react cleanly to collisions.
