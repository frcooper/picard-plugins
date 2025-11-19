"""Guardrails plugin entry point.

This module is the main plugin file for Picard and the library entry
point for the Guardrails — collision-aware renamer plugin.
"""

PLUGIN_NAME = 'Guardrails  collision-aware renamer (experimental)'
PLUGIN_AUTHOR = 'FRC + GitHub Copilot'
PLUGIN_DESCRIPTION = (
	"Experimental collision-handling plugin. Detects when a saved file had to be suffixed with "
	"' (n)' due to a name collision and either re-runs naming with a collision flag or attempts "
	"a rollback to the original path. Behaviour is likely to be fragile across Picard versions "
	"and should be treated as experimental and potentially broken."
)
PLUGIN_VERSION = '1.2.0'
PLUGIN_API_VERSIONS = ["2.2", "2.9"]

import os
import re
import shutil

from picard import log, config
from picard.file import register_file_post_save_processor, File # pyright: ignore[reportAttributeAccessIssue]
try:
	from picard.file import register_file_pre_save_processor  # pyright: ignore[reportAttributeAccessIssue]
	_GUARDRAILS_HAS_PRESAVE = True
except Exception:
	register_file_pre_save_processor = None
	_GUARDRAILS_HAS_PRESAVE = False
from picard.script import register_script_function # pyright: ignore[reportAttributeAccessIssue]
from picard.ui.options import register_options_page, OptionsPage # pyright: ignore[reportAttributeAccessIssue]
from picard.config import BoolOption


_COLLISION_SUFFIX_RE = re.compile(r"^(?P<stem>.*) \((?P<num>\d+)\)(?P<ext>\.[^.]*)$")


def _has_collision_suffix(path: str) -> bool:
	name = os.path.basename(path)
	m = _COLLISION_SUFFIX_RE.match(name)
	if m:
		log.debug("Guardrails: detected collision suffix '(%s)' in %r", m.group('num'), name)
		return True
	return False


def _rerun_naming_with_flag(file_obj):
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
		try:
			del file_obj.tagger.files[old_filename]
		except KeyError:
			pass
		file_obj.filename = new_filename
		file_obj.base_filename = os.path.basename(new_filename)
		file_obj.tagger.files[new_filename] = file_obj
		file_obj.update()
	else:
		log.debug("Guardrails: alternate naming produced same path; keeping %r", old_filename)


def _record_original_path(file_obj):
	file_obj._guardrails_original_filename = file_obj.filename
	log.debug("Guardrails: recorded original path %r", file_obj.filename)


def _rollback_move(file_obj):
	current = file_obj.filename
	orig = getattr(file_obj, "_guardrails_original_filename", None)
	if not orig:
		raise RuntimeError("original path not recorded; pre-save hook missing")

	if current == orig:
		log.debug("Guardrails: current == original, nothing to roll back for %r", current)
		return

	os.makedirs(os.path.dirname(orig), exist_ok=True)

	shutil.move(current, orig)

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
		if _has_collision_suffix(file_obj.filename):
			fatal_cfg = config.setting["guardrails_fatal_on_collision"]
			if fatal_cfg:
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
			if '_guardrails_has_collision' in file_obj.metadata:
				del file_obj.metadata['_guardrails_has_collision']
	except Exception:
		log.error("Guardrails: post-save processing failed for %r", file_obj, exc_info=True)


if register_file_pre_save_processor is not None:
	register_file_pre_save_processor(file_pre_save_processor)
register_file_post_save_processor(file_post_save_processor)


def collides(parser):
	val = parser.context.get('_guardrails_has_collision', '')
	return '1' if val else ''


register_script_function(collides)


PLUGIN_OPTIONS = [
	BoolOption("setting", "guardrails_fatal_on_collision", False),
]


class GuardrailsOptionsPage(OptionsPage):
	NAME = "guardrails"
	TITLE = "Guardrails"
	PARENT = "plugins"

	def __init__(self, parent=None):
		super().__init__(parent)
		from PyQt5.QtWidgets import QVBoxLayout, QLabel, QRadioButton, QGroupBox, QLayout

		layout: QLayout = QVBoxLayout()
		self.setLayout(layout)

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
		self.ui = self

	def load(self):
		fatal = config.setting["guardrails_fatal_on_collision"]
		if fatal:
			self.radio_fatal.setChecked(True)
		else:
			self.radio_retry.setChecked(True)

	def save(self):
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
