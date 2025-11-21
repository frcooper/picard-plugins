# Copilot instructions for Guardrails

Context: This folder contains the `Guardrails` plugin (`file-collision-protection.py`). It detects filename collisions after Picard saves files and provides a way for naming scripts to react, either by applying a different naming template or rolling the rename back and throwing an error.

Key behaviors
- Collision detection: Detects Picard's standard `" (n)"` collision suffix pattern using `_COLLISION_SUFFIX_RE` and treats those saves as collisions.
- Non-fatal mode (default): Sets `_guardrails_has_collision` on the file metadata, logs the event, and re-runs Picard's naming logic via `_rename` so scripts can choose an alternate naming template.
- Fatal mode: marks the file state as `File.ERROR`, appends error messages, and attempts to roll back the move/rename to the original pre-save path recorded by the pre-save hook.
- Script function: Exposes `$collides()` (via `register_script_function`) which returns the number of collisions that have occurred for the current file. The number of collisions is determined from the suffix count (e.g. `" (2)"` means 2 collisions).

Implementation notes
- this is a picard 3+ plugin; it requires both file pre-save and post-save hooks.
- Do not change the semantics of `$collides()`.
- Always use Picard's `log` with the `"Guardrails:"` prefix for debug/error messages.
- avoid data loss and preserve Picard's internal file mapping updates.

Config & UI
- use a standard config page to toggle fatal vs non-fatal mode. non-fatal is default.

Versioning
- Use semantic versions in `MAJOR.MINOR.PATCH` form for `PLUGIN_VERSION`.
- Bump the version for any behavioral change in collision detection, rollback logic, or script-visible behavior (patch for fixes, minor for new modes, major only for breaking changes).

Tagging & releases
- Release this plugin independently by tagging commits with `file-collision-protection-vMAJOR.MINOR.PATCH` (for example, `file-collision-protection-v1.1.2`).

Testing tips
- Use a test naming script that deliberately produces duplicate target filenames to exercise both non-fatal and fatal modes.
- Watch Picard's debug log to confirm detection of collision suffixes, re-run behavior, and rollback details.
- Validate that UI updates and file mappings are correct after collisions (files appear under the expected paths in Picard).
