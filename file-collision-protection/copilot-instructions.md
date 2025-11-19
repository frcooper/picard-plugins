# Copilot instructions for Guardrails — collision-aware renamer

Context: This folder contains the `Guardrails — collision-aware renamer (experimental)` plugin (`file-collision-protection.py`). It detects filename collisions after Picard saves files and either retries naming with a flag or treats the collision as a fatal error. Behaviour is experimental and may be fragile across Picard versions.

Key behaviors
- Hooks: Uses `register_file_post_save_processor` (and optionally `register_file_pre_save_processor` on Picard 2.9+) to inspect saved file paths.
- Collision detection: Detects Picard's standard `" (n)"` collision suffix pattern using `_COLLISION_SUFFIX_RE` and treats those saves as collisions.
- Non-fatal mode (default): Sets `_guardrails_has_collision` on the file metadata, logs the event, and re-runs Picard's naming logic via `_rename` so scripts can choose an alternate naming template.
- Fatal mode: When `guardrails_fatal_on_collision` is enabled, marks the file state as `File.ERROR`, appends error messages, and attempts to roll back the move/rename to the original pre-save path recorded by the pre-save hook.
- Script function: Exposes `$collides()` (via `register_script_function`) which returns `'1'` when a collision has occurred for the current file; this is the preferred way for naming scripts to react.

Implementation notes
- Keep `_has_collision_suffix`, `_rerun_naming_with_flag`, `_record_original_path`, and `_rollback_move` small and focused; add new helpers rather than overloading existing ones if behavior diverges.
- Do not change the semantics of `$collides()`; if you add more internal flags, keep them internal and documented in the plugin file.
- Always use Picard's `log` with the `"Guardrails:"` prefix for debug/error messages.
- Be careful when touching filesystem operations in `_rollback_move` and `_rerun_naming_with_flag`; avoid data loss and preserve Picard's internal file mapping updates.

Config & UI
- A single `BoolOption` `guardrails_fatal_on_collision` controls behavior; keep it in `PLUGIN_OPTIONS`.
- The options UI is implemented by `GuardrailsOptionsPage`. Extend this page if you add more behavior modes, but maintain the existing radio-button flow for backward compatibility.

Versioning
- Use semantic versions in `MAJOR.MINOR.PATCH` form for `PLUGIN_VERSION`.
- Bump the version for any behavioral change in collision detection, rollback logic, or script-visible behavior (patch for fixes, minor for new modes, major only for breaking changes).

Tagging & releases
- Release this plugin independently by tagging commits with `file-collision-protection-vMAJOR.MINOR.PATCH` (for example, `file-collision-protection-v1.1.2`).

Testing tips
- Use a test naming script that deliberately produces duplicate target filenames to exercise both non-fatal and fatal modes.
- Watch Picard's debug log to confirm detection of collision suffixes, re-run behavior, and rollback details.
- Validate that UI updates and file mappings are correct after collisions (files appear under the expected paths in Picard).
