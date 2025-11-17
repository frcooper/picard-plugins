# Copilot instructions for asciifier

Context: This folder contains an asciifier plugin (`to_ascii.py`) that is meant to expose a function for scripts to translate unprintable / illegal / non-ASCII characters into a safe, printable representation.

Goals
- Provide a script-callable function (e.g. via `register_script_function`) that converts a given string to an ASCII-safe version.
- Replicate and modernize the functionality of the `non_ascii_equivalents` plugin (see `3rd-party/non_ascii_equivalents/non_ascii_equivalents.py`) without modifying the 3rd-party file.
- Keep behavior predictable and safe for filenames, tags, and legacy devices that cannot display non-ASCII characters.

Desired behavior
- Use a mapping table similar to `CHAR_TABLE` from `non_ascii_equivalents` to replace specific non-ASCII characters with meaningful ASCII sequences (e.g. `“` → `"`, `ß` → `ss`, `–` → `--`, etc.).
- For all other non-ASCII characters, fall back to Picard's `unaccent()` to strip diacritics where possible.
- Preserve ASCII characters (printable 7-bit) unchanged.
- Be idempotent: running the conversion multiple times should not further change already-converted text.

API expectations
- Expose a function that can be used in Picard scripts, for example:
	- `$asciify(%artist%)`
	- The backing Python function will likely be something like `to_ascii(text)` registered via `register_script_function`.
- Keep the function pure: it should take a string and return a converted string without touching metadata objects directly (unlike the original plugin which iterates over tags).
- If more than one function is provided (e.g. strict vs relaxed mode), name them clearly and document in this file.

Implementation notes
- Look at `3rd-party/non_ascii_equivalents/non_ascii_equivalents.py` for the reference character mappings and base logic, but **do not** edit that file.
- Prefer small helpers like `sanitize_char(c)` and `to_ascii(text)`; keep them free of Picard-specific types so they are easy to test.
- If you add configuration later (e.g. which tags to filter, how aggressive to be), use the standard Picard `PLUGIN_OPTIONS` / `OptionsPage` patterns defined in the repo root instructions.

Versioning
- Make sure `to_ascii.py` has full plugin metadata (name, version, author, description, URL) once the plugin is implemented.
- Bump version numbers according to behavior changes (new mappings or API surface → minor; bugfixes → patch).

Testing tips
- Write small unit-like tests inside a `if __name__ == "__main__":` block or in a separate helper to verify common cases:
	- Accented letters (e.g. `áéíóú`, `Å`, `Æ`) are converted to the expected ASCII sequences.
	- Punctuation and math symbols in `CHAR_TABLE` are mapped as intended.
	- Already-ASCII strings are returned unchanged.
- In Picard, test via a simple script using `$asciify()` and inspect the results on tags and filenames.
