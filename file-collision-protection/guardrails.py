# -*- coding: utf-8 -*-
"""
Picard plugin: Guardrails — detect filename collisions and re-run naming.

When Picard saves and renames a file it uses picard.util.filenaming.get_available_filename
which appends " (n)" before the extension if the target path is already in use.
This plugin hooks into file_post_save and, if such a collision suffix is detected,
sets an in-memory variable for the file and immediately re-runs Picard's naming /
renaming logic so your naming script can switch to an alternate template.

Usage in your naming script:
- Check for $get(_guardrails_has_collision) to detect collisions and branch to an
  alternate path template.

Example snippet:
$if($get(_guardrails_has_collision),
  <alternate-template>,
  <normal-template>
)
"""

PLUGIN_NAME = 'Guardrails — collision-aware renamer'
PLUGIN_AUTHOR = 'FRC + GitHub Copilot'
PLUGIN_DESCRIPTION = (
    "Detects when a saved file had to be suffixed with ' (n)' due to a name "
    "collision. On normal mode it sets '_guardrails_has_collision' and re-runs "
    "renaming so your naming script can switch templates. On fatal mode it "
    "rolls back the move/rename to the original pre-save path and marks an error."
)
PLUGIN_VERSION = '1.1.1'
# Supports Picard 2.2+; enhanced rollback requires 2.9+ (pre-save hook)
PLUGIN_API_VERSIONS = ["2.2", "2.9"]

import os
import re
import shutil

from picard import log, config
from picard.file import register_file_post_save_processor, File
try:
    from picard.file import register_file_pre_save_processor  # Picard 2.9+
    _GUARDRAILS_HAS_PRESAVE = True
except Exception:
    register_file_pre_save_processor = None
    _GUARDRAILS_HAS_PRESAVE = False
from picard.script import register_script_function
from picard.ui.options import register_options_page, OptionsPage
from picard.config import BoolOption

# Picard uses this pattern for collisions in picard.util.filenaming.get_available_filename:
# new_path = "%s (%d)%s" % (tmp_filename, i, ext)
# Detect that canonical form: base + " (n)" + ext
_COLLISION_SUFFIX_RE = re.compile(r"^(?P<stem>.*) \((?P<num>\d+)\)(?P<ext>\.[^.]*)$")


def _has_collision_suffix(path: str) -> bool:
    name = os.path.basename(path)
    m = _COLLISION_SUFFIX_RE.match(name)
    if m:
        log.debug("Guardrails: detected collision suffix '(%s)' in %r", m.group('num'), name)
        return True
    return False


def _rerun_naming_with_flag(file_obj):
    """Set the in-memory flag and re-run renaming immediately.

    This does not re-save tags; it only renames/moves the file again using the
    current naming script, which now can react to '_guardrails_has_collision'.
    """
    # Mark collision for naming scripts (internal-only variable, not written to file)
    file_obj.metadata['_guardrails_has_collision'] = '1'
    log.debug("Guardrails: set '_guardrails_has_collision'=1 for %r", file_obj.filename)

    old_filename = file_obj.filename
    try:
        new_filename = file_obj._rename(old_filename, file_obj.metadata)
    except Exception:
        log.error("Guardrails: rename after collision failed for %r", old_filename, exc_info=True)
        return

    if new_filename and new_filename != old_filename:
        log.debug("Guardrails: collision detected, renaming %r => %r", old_filename, new_filename)
        # Update file bookkeeping similar to File._save_done
        try:
            del file_obj.tagger.files[old_filename]
        except KeyError:
            pass
        file_obj.filename = new_filename
        file_obj.base_filename = os.path.basename(new_filename)
        file_obj.tagger.files[new_filename] = file_obj
        # Update UI
        file_obj.update()
    else:
        log.debug("Guardrails: alternate naming produced same path; keeping %r", old_filename)


def _record_original_path(file_obj):
    """Store the current on-disk path before save so we can roll back if needed."""
    file_obj._guardrails_original_filename = file_obj.filename
    log.debug("Guardrails: recorded original path %r", file_obj.filename)


def _rollback_move(file_obj):
    """Roll back the collision rename to the original pre-save path.

    - Uses the path recorded in file_pre_save_processor; no fallbacks.
    - Does not overwrite existing files at the original location.
    - Updates Picard's internal file mapping and UI.
    """
    current = file_obj.filename
    orig = getattr(file_obj, "_guardrails_original_filename", None)
    if not orig:
        raise RuntimeError("original path not recorded; pre-save hook missing")

    if current == orig:
        log.debug("Guardrails: current == original, nothing to roll back for %r", current)
        return

    # Ensure parent dir exists; restore to original path without existence checks
    os.makedirs(os.path.dirname(orig), exist_ok=True)

    # Cross-volume safe move
    shutil.move(current, orig)

    # Update bookkeeping similar to File._save_done
    try:
        del file_obj.tagger.files[current]
    except KeyError:
        pass
    file_obj.filename = orig
    file_obj.base_filename = os.path.basename(orig)
    file_obj.tagger.files[orig] = file_obj
    file_obj.update()


def file_pre_save_processor(file_obj):
    _record_original_path(file_obj)


def file_post_save_processor(file_obj):
    try:
        # Only act if Picard had to append " (n)" to resolve a collision
        if _has_collision_suffix(file_obj.filename):
            fatal_cfg = config.setting["guardrails_fatal_on_collision"]
            if fatal_cfg:
                # Fatal: roll back the move/rename to the original path and mark error
                file_obj.state = File.ERROR
                file_obj.error_append("Guardrails: filename collision detected for '%s'" % file_obj.filename)
                try:
                    _rollback_move(file_obj)
                    file_obj.error_append("Guardrails: rolled back to original path: %s" % file_obj.filename)
                    log.error("Guardrails: collision fatal; rolled back to %r", file_obj.filename)
                except Exception as e:
                    log.error("Guardrails: fatal collision - rollback failed: %s", e, exc_info=True)
            else:
                _rerun_naming_with_flag(file_obj)
        else:
            # Non-collision save: clear previously set flag so scripts revert to normal
            if '_guardrails_has_collision' in file_obj.metadata:
                del file_obj.metadata['_guardrails_has_collision']
    except Exception:
        log.error("Guardrails: post-save processing failed for %r", file_obj, exc_info=True)


if _GUARDRAILS_HAS_PRESAVE:
    register_file_pre_save_processor(file_pre_save_processor)
register_file_post_save_processor(file_post_save_processor)


# --- Scripting function: $collides() ---

def collides(parser):
    """`$collides()`

    Returns '1' if this file previously collided with an existing path during save,
    otherwise ''.

    Details:
    - Picard resolves naming collisions by appending " (n)" before the extension.
    - When this happens, the Guardrails plugin sets the internal variable
      `_guardrails_has_collision` for the file and re-runs the naming script so
      your script can pick an alternate template.
    - On the next non-collision save the variable is cleared automatically.

    Notes:
    - Prefer using `$collides()` in scripts; alternatively use `$get(_guardrails_has_collision)`.
    """
    val = parser.context.get('_guardrails_has_collision', '')
    return '1' if val else ''


register_script_function(collides)


# ---------------- Options -----------------

# Persisted setting controlling behavior on collision
# False (default): set flag and rerun naming
# True: treat as fatal error
PLUGIN_OPTIONS = [
    BoolOption("setting", "guardrails_fatal_on_collision", False),
]


class GuardrailsOptionsPage(OptionsPage):
    NAME = "guardrails"
    TITLE = "Guardrails"
    PARENT = "plugins"

    def __init__(self, parent=None):
        super().__init__(parent)
        # Picard 2.x uses PyQt5
        from PyQt5.QtWidgets import QVBoxLayout, QLabel, QRadioButton, QGroupBox

        layout = QVBoxLayout(self)

        desc = QLabel(
            "On filename collision Picard appends ' (n)'. This plugin can either "
            "treat that as a fatal error or re-run the naming script with a collision flag."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        group = QGroupBox("Collision behavior")
        gl = QVBoxLayout(group)

        self.radio_retry = QRadioButton("Re-run naming script (set collision flag)")
        self.radio_fatal = QRadioButton("Treat as fatal error")
        gl.addWidget(self.radio_retry)
        gl.addWidget(self.radio_fatal)
        layout.addWidget(group)

        layout.addWidget(QLabel(
            "Scripting: Use $collides() or $get(_guardrails_has_collision) in your naming script "
            "to switch templates when a collision is detected."
        ))

        layout.addStretch()
        # Some Picard versions expect self.ui to reference the page widget
        self.ui = self

    def load(self):
        fatal = config.setting["guardrails_fatal_on_collision"]
        if fatal:
            self.radio_fatal.setChecked(True)
        else:
            self.radio_retry.setChecked(True)

    def save(self):
        # Log when configuration is changed
        old_value = config.setting["guardrails_fatal_on_collision"]
        new_value = self.radio_fatal.isChecked()
        config.setting["guardrails_fatal_on_collision"] = new_value
        if old_value != new_value:
            log.debug(
                "Guardrails: configuration changed guardrails_fatal_on_collision: %r -> %r",
                old_value,
                new_value,
            )


register_options_page(GuardrailsOptionsPage)
