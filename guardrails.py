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
    "collision, sets '_guardrails_has_collision', and re-runs renaming so your "
    "naming script can switch templates."
)
PLUGIN_VERSION = '1.0.2'
PLUGIN_API_VERSIONS = ["2.2"]

import os
import re

from picard import log, config
from picard.file import register_file_post_save_processor, File
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
        # Debug which suffix number was detected
        try:
            num = m.group('num')
            log.debug("Guardrails: detected collision suffix '(%s)' in %r", num, name)
        except Exception:
            log.debug("Guardrails: detected collision suffix in %r", name)
        return True
    else:
        return False


def _rerun_naming_with_flag(file_obj):
    """Set the in-memory flag and re-run renaming immediately.

    This does not re-save tags; it only renames/moves the file again using the
    current naming script, which now can react to '~guardrails_collision'.
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


def file_post_save_processor(file_obj):
    try:
        # Only act if Picard had to append " (n)" to resolve a collision
        if _has_collision_suffix(file_obj.filename):
            try:
                fatal_cfg = config.setting["guardrails_fatal_on_collision"]
            except Exception:
                fatal_cfg = False
            if fatal_cfg:
                # Mark as error and don't attempt alternate rename
                try:
                    file_obj.state = File.ERROR
                except Exception:
                    pass
                try:
                    file_obj.error_append("Guardrails: filename collision detected for '%s'" % file_obj.filename)
                except Exception:
                    pass
                log.error("Guardrails: collision treated as fatal for %r", file_obj.filename)
            else:
                _rerun_naming_with_flag(file_obj)
        else:
            # Non-collision save: clear previously set flag so scripts revert to normal
            try:
                if '_guardrails_has_collision' in file_obj.metadata:
                    try:
                        del file_obj.metadata['_guardrails_has_collision']
                    except Exception:
                        file_obj.metadata['_guardrails_has_collision'] = ''
                    log.debug("Guardrails: cleared collision flag for %r", file_obj.filename)
            except Exception:
                log.debug("Guardrails: unable to clear collision flag for %r", file_obj.filename)
            log.debug("Guardrails: no collision suffix for %r", file_obj.filename)
    except Exception:
        log.error("Guardrails: post-save processing failed for %r", file_obj, exc_info=True)


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
    try:
        val = parser.context.get('_guardrails_has_collision', '')
        result = '1' if val else ''
        log.debug("Guardrails: $collides() -> %r (val=%r)", result, val)
        return result
    except Exception:
        log.error("Guardrails: $collides() failed", exc_info=True)
        return ''


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
        try:
            fatal = config.setting["guardrails_fatal_on_collision"]
        except Exception:
            fatal = False
        if fatal:
            self.radio_fatal.setChecked(True)
        else:
            self.radio_retry.setChecked(True)

    def save(self):
        # Log when configuration is changed
        try:
            old_value = config.setting["guardrails_fatal_on_collision"]
        except Exception:
            old_value = False
        new_value = self.radio_fatal.isChecked()
        config.setting["guardrails_fatal_on_collision"] = new_value
        if old_value != new_value:
            log.debug(
                "Guardrails: configuration changed guardrails_fatal_on_collision: %r -> %r",
                old_value,
                new_value,
            )


register_options_page(GuardrailsOptionsPage)
