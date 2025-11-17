# Copilot instructions for asciifier

Context: This folder contains an asciifier plugin (`to_ascii.py`) that is meant to expose a function for scripts to translate unprintable / illegal / non-ASCII characters into a safe, printable representation.

Goals
- Provide a script-callable function (via `register_script_function`) that converts a given string to an ASCII-safe version.
- Provide a fully compatible, enhanced replacement for the `non_ascii_equivalents` plugin (see `3rd-party/non_ascii_equivalents/non_ascii_equivalents.py`), using exactly the same replacement table by default.
- Keep behavior predictable and safe for filenames, tags, and legacy devices that cannot display non-ASCII characters.
- Make the character mappings fully configurable via an options page: users can add/remove maps, toggle maps on and off, and edit character→replacement pairs.

Desired behavior
- Use one or more character maps to replace specific non-ASCII characters with meaningful ASCII sequences (e.g. `“` → `"`, `ß` → `ss`, `–` → `--`, etc.).
- Represent maps as JSON in `config.setting["asciifier_maps"]` with the schema `{name: {"enabled": bool, "pairs": [["char", "replacement"], ...]}}`.
- On first run (when no maps exist), seed four default maps `alpha`, `punct`, `math`, and `other` whose contents exactly match the categories in `non_ascii_equivalents`' `CHAR_TABLE`.
- Build an effective lookup table by merging all enabled maps (last map wins on conflicts).
- Allow users to create, rename (by delete+add), and delete maps; never force more than one default map to exist, but always ensure at least one map remains.
- Permit the user to remove all characters from the remaining map so it effectively does nothing.
- **Do not** use any implicit fallback like `unaccent()`; characters not in any enabled map are left untouched.
- Preserve ASCII characters (printable 7-bit) unchanged.
- Be idempotent: running the conversion multiple times should not further change already-converted text.

API expectations
- Expose a function that can be used in Picard scripts, for example:
	- `$asciify(%artist%)`
	- The backing Python function is `to_ascii(text)` registered via `register_script_function`.
- Keep the function pure: it should take a string and return a converted string without touching metadata objects directly (unlike the original plugin which iterates over tags).
- If more than one function is provided (e.g. strict vs relaxed mode), name them clearly and document in this file.

Implementation notes
- Look at `3rd-party/non_ascii_equivalents/non_ascii_equivalents.py` for the reference character mappings and base logic, but **do not** edit that file.
- Prefer small helpers like `_sanitize_char(c, table)` and `to_ascii(text)`; keep them free of Picard-specific types so they are easy to test.
- Use `PLUGIN_OPTIONS` to store `TextOption("setting", "asciifier_maps", "{}")` for the JSON maps; there is no `unaccent()` fallback toggle.
- Implement an `OptionsPage` subclass (`AsciifierOptionsPage`) that provides:
	- A map selector with add/remove and enabled/disabled controls.
	- A 2-column grid for character→replacement pairs for the currently selected map.
- Ensure at least one map always exists in the UI, but allow that map's pair list to be empty so the plugin can be effectively no-op.

Versioning
- Make sure `to_ascii.py` has full plugin metadata (name, version, author, description, URL) once the plugin is implemented.
- Bump version numbers according to behavior changes (new mappings or API surface → minor; bugfixes → patch).

Testing tips
- Write small unit-like tests inside a `if __name__ == "__main__":` block or in a separate helper to verify common cases:
	- Accented letters (e.g. `áéíóú`, `Å`, `Æ`) are converted to the expected ASCII sequences.
	- Punctuation and math symbols in `CHAR_TABLE` are mapped as intended.
	- Already-ASCII strings are returned unchanged.
- In Picard, test via a simple script using `$asciify()` and inspect the results on tags and filenames.
