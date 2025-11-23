# Copilot instructions for asciifier

Context: This folder contains an asciifier plugin (`asciifier.py`) that exposes a script function and an optional automatic mode to translate non-ASCII characters into ASCII-safe equivalents.

Goals
- Provide a script-callable function (via `register_script_function`) that converts a given string to an ASCII-safe version.
- Offer an automatic mode that cleans a configurable list of tags/variables as tracks and albums are processed.
- Use a table of explicit character mappings, configurable via an options page.
- Keep behavior predictable and safe for filenames, tags, and legacy devices that cannot display non-ASCII characters.

Desired behavior
- Use one or more character maps to replace specific non-ASCII characters with meaningful ASCII sequences (e.g. `“` → `"`, `ß` → `ss`, `–` → `--`, etc.).
- Represent maps as JSON in `config.setting["asciifier_maps"]` with the schema `{name: {"enabled": bool, "pairs": [["char", "replacement"], ...]}}`.
- On first run (when no maps exist), seed four default maps `alpha`, `punct`, `math`, and `other` with a useful starter set of mappings.
- Build an effective lookup table by merging all enabled maps (last map wins on conflicts).
- Allow users to create, rename (by delete+add), and delete maps; never force more than one default map to exist, but always ensure at least one map remains.
- Permit the user to remove all characters from the remaining map so it effectively does nothing.
- **Do not** use any implicit fallback like `unaccent()`; characters not in any enabled map are left untouched.
- Preserve ASCII characters (printable 7-bit) unchanged.
- Be idempotent: running the conversion multiple times should not further change already-converted text.
- In automatic mode, clean a configurable list of tags (default: `album, albumartist, albumartists, albumartistsort, albumsort, artist, artists, artistsort, title`) on both album and track metadata.

API expectations
- Expose a function that can be used in Picard scripts, for example:
	- `$asciify(%artist%)`
	- The backing Python function is `to_ascii(text)` registered via `register_script_function`.
- Keep the script function pure: it should take a string and return a converted string.
- Automatic mode should be implemented via album/track metadata processors that call the same core conversion logic.

Implementation notes
- Prefer small helpers like `_sanitize_char(c, table)` and `to_ascii(text)`; keep them free of Picard-specific types so they are easy to test.
- Use `PLUGIN_OPTIONS` to store:
	- `TextOption("setting", "asciifier_maps", "{}")` for the JSON maps.
	- `BoolOption("setting", "asciifier_auto_enabled", False)` for automatic mode.
	- `TextOption("setting", "asciifier_auto_tags", "...")` for the default tag list.
- Implement an `OptionsPage` subclass (`AsciifierOptionsPage`) that provides:
	- Automatic mode controls (checkbox + editable tag list).
	- A map selector with add/remove and enabled/disabled controls.
	- A 2-column grid for character→replacement pairs for the currently selected map.
- Ensure at least one map always exists in the UI, but allow that map's pair list to be empty so the plugin can be effectively no-op.
- On module import, pre-seed `config.setting` with default maps/flags if the keys are missing so a freshly enabled plugin behaves as intended without visiting the options page.
- Always read settings directly via `config.setting["…"]` so Picard's option defaults apply on first run; avoid checking `'key in config.setting'` before accessing.

Versioning
- Use semantic versions in `MAJOR.MINOR.PATCH` form for `PLUGIN_VERSION`.
- Make sure `asciifier.py` has full plugin metadata (name, version, author, description, URL) once the plugin is implemented.
- Bump version numbers according to behavior changes (new mappings or API surface → minor; bugfixes → patch; major for breaking changes).

Tagging & releases
- Release this plugin independently by tagging commits with `asciifier-vMAJOR.MINOR.PATCH` (for example, `asciifier-v0.4.1`).

Testing tips
- Write small unit-like tests inside a `if __name__ == "__main__":` block or in a separate helper to verify common cases:
	- Accented letters (e.g. `áéíóú`, `Å`, `Æ`) are converted to the expected ASCII sequences.
	- Punctuation and math symbols in `CHAR_TABLE` are mapped as intended.
	- Already-ASCII strings are returned unchanged.
- In Picard, test via a simple script using `$asciify()` and inspect the results on tags and filenames.
