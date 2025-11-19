"""Asciifier plugin entry point.

This module is the main plugin file for Picard and the library entry
point for the Asciifier plugin.
"""

PLUGIN_NAME = "Asciifier - to_ascii()"
PLUGIN_AUTHOR = "FRC + GitHub Copilot"
PLUGIN_DESCRIPTION = (
	"Expose a $asciify() script function that replaces accented and other "
	"non-ASCII characters with ASCII approximations using configurable "
	"character maps, plus an optional automatic mode for common tags."
)
PLUGIN_VERSION = '1.1.2'
PLUGIN_API_VERSIONS = ["2.0"]
PLUGIN_LICENSE = "GPL-3.0-or-later"
PLUGIN_LICENSE_URL = "https://gnu.org/licenses/gpl.html"

from picard.script import register_script_function
from picard import config, log, metadata
from picard.config import TextOption, BoolOption
from picard.ui.options import register_options_page, OptionsPage


import json


PLUGIN_OPTIONS = [
	TextOption("setting", "asciifier_maps", "{}"),
	BoolOption("setting", "asciifier_auto_enabled", True),
	TextOption(
		"setting",
		"asciifier_auto_tags",
		"album, albumartist, albumartists, albumartistsort, albumsort, "
		"artist, artists, artistsort, title",
	),
]


def _load_maps_from_config():
	if "asciifier_maps" in config.setting:
		raw = config.setting["asciifier_maps"]
	else:
		raw = "{}"
	try:
		data = json.loads(raw) if raw else {}
	except Exception:
		log.error("Asciifier: failed to parse asciifier_maps JSON; resetting", exc_info=True)
		data = {}
	if not isinstance(data, dict):
		data = {}
	if not data:
		data = {
			"alpha": {
				"enabled": True,
				"pairs": [
					["Å", "AA"],
					["å", "aa"],
					["Æ", "AE"],
					["æ", "ae"],
					["Œ", "OE"],
					["œ", "oe"],
					["ẞ", "ss"],
					["ß", "ss"],
					["Ø", "O"],
					["ø", "o"],
					["Ł", "L"],
					["ł", "l"],
					["Þ", "Th"],
					["þ", "th"],
					["Ð", "D"],
					["ð", "d"],
				],
			},
			"punct": {
				"enabled": True,
				"pairs": [
					["¡", "!"],
					["¿", "?"],
					["–", "--"],
					["—", "--"],
					["―", "--"],
					["«", "<<"],
					["»", ">>"],
					["‘", "'"],
					["’", "'"],
					["‚", ","],
					["‛", "'"],
					["“", '"'],
					["”", '"'],
					["„", ",,"],
					["‟", '"'],
					["‹", "<"],
					["›", ">"],
					["⹂", ",,"],
					["「", "|-"],
					["」", "-|"],
					["『", "|-"],
					["』", "-|"],
					["〝", '"'],
					["〞", '"'],
					["〟", ",,"],
					["﹁", "-|"],
					["﹂", "|-"],
					["﹃", "-|"],
					["﹄", "|-"],
					["｢", "|-"],
					["｣", "-|"],
					["・", "."],
				],
			},
			"math": {
				"enabled": True,
				"pairs": [
					["≠", "!="],
					["≤", "<="],
					["≥", ">="],
					["±", "+-"],
					["∓", "-+"],
					["×", "x"],
					["·", "."],
					["÷", "/"],
					["√", "\\/"],
					["∑", "E"],
					["≪", "<<"],
					["≫", ">>"],
				],
			},
			"other": {
				"enabled": True,
				"pairs": [
					["°", "o"],
					["µ", "u"],
					["ı", "i"],
					["†", "t"],
					["©", "(c)"],
					["®", "(R)"],
					["♥", "<3"],
					["→", "-->"],
					["☆", "*"],
					["★", "*"],
				],
			},
		}
	return data


def _save_maps_to_config(maps: dict) -> None:
	try:
		config.setting["asciifier_maps"] = json.dumps(maps, ensure_ascii=False)
	except Exception:
		log.error("Asciifier: failed to serialize asciifier_maps", exc_info=True)


def _build_effective_table() -> dict:
	maps = _load_maps_from_config()
	table = {}
	for name, spec in maps.items():
		if not isinstance(spec, dict):
			continue
		if not spec.get("enabled", True):
			continue
		pairs = spec.get("pairs", [])
		for pair in pairs:
			if not isinstance(pair, (list, tuple)) or len(pair) != 2:
				continue
			ch, repl = pair
			if not ch:
				continue
			table[str(ch)] = str(repl)
	return table


def _sanitize_char(ch: str, table: dict) -> str:
	if ch in table:
		return table[ch]
	return ch


def to_ascii(text: str) -> str:
	if not text:
		return ""
	table = _build_effective_table()
	return "".join(_sanitize_char(ch, table) for ch in text)


def asciify(parser, value: str = "") -> str:
	if value is None:
		return ""
	return to_ascii(str(value))


register_script_function(asciify)


def _parse_auto_tags(raw: str):
	if not raw:
		return []
	parts = []
	for piece in raw.replace("\n", ",").split(","):
		name = piece.strip()
		if name:
			parts.append(name)
	return parts


def _auto_clean_metadata(md: metadata.Metadata, table: dict, tag_names):
	for name in tag_names:
		if name in md:
			val = md.get(name)
			if isinstance(val, list):
				md[name] = ["".join(_sanitize_char(ch, table) for ch in str(x)) for x in val]
			else:
				md[name] = "".join(_sanitize_char(ch, table) for ch in str(val))


class AsciifierOptionsPage(OptionsPage):
	NAME = "asciifier"
	TITLE = "Asciifier"
	PARENT = "plugins"

	def __init__(self, parent=None):
		from PyQt5.QtWidgets import (
			QVBoxLayout, QLabel, QCheckBox, QHBoxLayout,
			QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
		)
		from PyQt5.QtCore import Qt  # noqa: F401

		super().__init__(parent)
		self._maps = {}
		self._current_map_name = None

		layout = QVBoxLayout(self)

		desc = QLabel(
			"Configure Asciifier. "
			"Character maps control how non-ASCII characters are replaced. "
			"You can also enable automatic cleaning of common tags."
		)
		desc.setWordWrap(True)
		layout.addWidget(desc)

		self.auto_enabled_checkbox = QCheckBox("Automatically clean common tags on load")
		layout.addWidget(self.auto_enabled_checkbox)

		self.auto_tags_label = QLabel(
			"Tags/variables to clean (comma or newline separated), "
			"e.g. album, artist, title."
		)
		self.auto_tags_label.setWordWrap(True)
		layout.addWidget(self.auto_tags_label)

		from PyQt5.QtWidgets import QPlainTextEdit
		self.auto_tags_edit = QPlainTextEdit()
		self.auto_tags_edit.setPlaceholderText(
			"album, albumartist, albumartists, albumartistsort, albumsort,\n"
			"artist, artists, artistsort, title"
		)
		self.auto_tags_edit.setFixedHeight(60)
		layout.addWidget(self.auto_tags_edit)

		row = QHBoxLayout()
		row.addWidget(QLabel("Map:"))
		self.map_select = QComboBox()
		row.addWidget(self.map_select, 1)
		self.map_enabled_checkbox = QCheckBox("Enabled")
		row.addWidget(self.map_enabled_checkbox)
		self.add_map_btn = QPushButton("Add map")
		self.remove_map_btn = QPushButton("Remove map")
		row.addWidget(self.add_map_btn)
		row.addWidget(self.remove_map_btn)
		layout.addLayout(row)

		self.table = QTableWidget(0, 2)
		self.table.setHorizontalHeaderLabels(["Character", "Replacement"])
		self.table.horizontalHeader().setStretchLastSection(True)
		layout.addWidget(self.table, 1)

		self.add_row_btn = QPushButton("Add row")
		self.remove_row_btn = QPushButton("Remove selected row")
		row2 = QHBoxLayout()
		row2.addWidget(self.add_row_btn)
		row2.addWidget(self.remove_row_btn)
		row2.addStretch(1)
		layout.addLayout(row2)

		layout.addStretch()
		self.ui = self

		self.add_map_btn.clicked.connect(self._on_add_map)
		self.remove_map_btn.clicked.connect(self._on_remove_map)
		self.map_select.currentTextChanged.connect(self._on_map_changed)
		self.map_enabled_checkbox.toggled.connect(self._on_map_enabled_toggled)
		self.add_row_btn.clicked.connect(self._on_add_row)
		self.remove_row_btn.clicked.connect(self._on_remove_row)

	def _ensure_at_least_one_map(self):
		if self._maps:
			return
		self._maps = {
			"Default": {"enabled": True, "pairs": []},
		}
		self._current_map_name = "Default"

	def _refresh_map_list(self):
		self.map_select.blockSignals(True)
		self.map_select.clear()
		for name in self._maps.keys():
			self.map_select.addItem(name)
		if self._current_map_name and self._current_map_name in self._maps:
			index = list(self._maps.keys()).index(self._current_map_name)
			self.map_select.setCurrentIndex(index)
		self.map_select.blockSignals(False)
		self._load_current_map_into_table()

	def _load_current_map_into_table(self):
		from PyQt5.QtWidgets import QTableWidgetItem

		name = self.map_select.currentText()
		self._current_map_name = name or None
		self.table.setRowCount(0)
		if not name or name not in self._maps:
			self.map_enabled_checkbox.setChecked(False)
			return
		data = self._maps.get(name, {"enabled": True, "pairs": []})
		self.map_enabled_checkbox.setChecked(bool(data.get("enabled", True)))
		pairs = data.get("pairs", [])
		self.table.setRowCount(len(pairs))
		for row, (ch, repl) in enumerate(pairs):
			self.table.setItem(row, 0, QTableWidgetItem(str(ch)))
			self.table.setItem(row, 1, QTableWidgetItem(str(repl)))

	def _on_add_map(self):
		base = "Map"
		i = 1
		while f"{base} {i}" in self._maps:
			i += 1
		name = f"{base} {i}"
		self._maps[name] = {"enabled": True, "pairs": []}
		self._current_map_name = name
		self._refresh_map_list()

	def _on_remove_map(self):
		name = self.map_select.currentText()
		if not name or name not in self._maps:
			return
		if len(self._maps) == 1:
			self._maps[name]["pairs"] = []
			self._load_current_map_into_table()
			return
		self._maps.pop(name, None)
		self._current_map_name = next(iter(self._maps.keys()), None)
		self._refresh_map_list()

	def _on_map_changed(self, name: str):
		self._save_table_into_current_map()
		self._current_map_name = name or None
		self._load_current_map_into_table()

	def _on_map_enabled_toggled(self, checked: bool):
		name = self.map_select.currentText()
		if not name or name not in self._maps:
			return
		self._maps[name]["enabled"] = bool(checked)

	def _on_add_row(self):
		from PyQt5.QtWidgets import QTableWidgetItem

		row = self.table.rowCount()
		self.table.insertRow(row)
		self.table.setItem(row, 0, QTableWidgetItem(""))
		self.table.setItem(row, 1, QTableWidgetItem(""))

	def _on_remove_row(self):
		row = self.table.currentRow()
		if row < 0:
			return
		self.table.removeRow(row)

	def _save_table_into_current_map(self):
		name = self._current_map_name
		if not name or name not in self._maps:
			return
		pairs = []
		for row in range(self.table.rowCount()):
			item_ch = self.table.item(row, 0)
			item_repl = self.table.item(row, 1)
			ch = item_ch.text() if item_ch else ""
			repl = item_repl.text() if item_repl else ""
			if not ch:
				continue
			pairs.append([ch, repl])
		self._maps[name]["pairs"] = pairs

	def load(self):
		self.auto_enabled_checkbox.setChecked(
			config.setting["asciifier_auto_enabled"]
			if "asciifier_auto_enabled" in config.setting
			else True
		)
		self.auto_tags_edit.setPlainText(
			config.setting["asciifier_auto_tags"]
			if "asciifier_auto_tags" in config.setting
			else (
				"album, albumartist, albumartists, albumartistsort, albumsort, "
				"artist, artists, artistsort, title"
			)
		)
		self._maps = _load_maps_from_config()
		self._ensure_at_least_one_map()
		self._refresh_map_list()

	def save(self):
		self._save_table_into_current_map()
		_save_maps_to_config(self._maps)
		config.setting["asciifier_auto_enabled"] = (
			self.auto_enabled_checkbox.isChecked()
		)
		config.setting["asciifier_auto_tags"] = (
			self.auto_tags_edit.toPlainText().strip()
		)
		log.debug("Asciifier: saved %d maps; auto_enabled=%r", len(self._maps), self.auto_enabled_checkbox.isChecked())


register_options_page(AsciifierOptionsPage)


def _auto_album_processor(tagger, metadata_obj, release):
	if "asciifier_auto_enabled" in config.setting:
		auto_enabled = bool(config.setting["asciifier_auto_enabled"])
	else:
		auto_enabled = False
	if not auto_enabled:
		return
	table = _build_effective_table()
	if "asciifier_auto_tags" in config.setting:
		raw_tags = config.setting["asciifier_auto_tags"]
	else:
		raw_tags = ""
	tags = _parse_auto_tags(raw_tags)
	if not tags or not table:
		return
	_auto_clean_metadata(metadata_obj, table, tags)


def _auto_track_processor(tagger, metadata_obj, track, release):
	if "asciifier_auto_enabled" in config.setting:
		auto_enabled = bool(config.setting["asciifier_auto_enabled"])
	else:
		auto_enabled = False
	if not auto_enabled:
		return
	table = _build_effective_table()
	if "asciifier_auto_tags" in config.setting:
		raw_tags = config.setting["asciifier_auto_tags"]
	else:
		raw_tags = ""
	tags = _parse_auto_tags(raw_tags)
	if not tags or not table:
		return
	_auto_clean_metadata(metadata_obj, table, tags)


metadata.register_album_metadata_processor(_auto_album_processor)
metadata.register_track_metadata_processor(_auto_track_processor)
