"""Picard plugin: Asciifier

Expose a script function that converts strings to ASCII-safe equivalents,
mirroring the behavior of the legacy `Non-ASCII Equivalents` plugin but in a
script-friendly way.
"""

PLUGIN_NAME = "Asciifier — to_ascii()"
PLUGIN_AUTHOR = "FRC + GitHub Copilot (derived from Non-ASCII Equivalents)"
PLUGIN_DESCRIPTION = (
	"Expose a $asciify() script function that replaces accented and other "
	"non-ASCII characters with ASCII approximations, using the exact "
	"replacement table from the Non-ASCII Equivalents plugin by Anderson "
	"Mesquita and Konrad Marciniak, with configurable maps."
)
PLUGIN_VERSION = "0.3.1"
PLUGIN_API_VERSIONS = ["2.0"]
PLUGIN_LICENSE = "GPL-3.0-or-later"
PLUGIN_LICENSE_URL = "https://gnu.org/licenses/gpl.html"

from picard.script import register_script_function
from picard import config, log
from picard.config import TextOption
from picard.ui.options import register_options_page, OptionsPage


# Configuration model
# --------------------
# We support multiple named "maps" of character replacements. Each map can be
# toggled on/off, and users can create or delete maps entirely. Internally we
# persist maps as JSON in a single TextOption so they remain editable and
# future-proof without introducing a complex schema.
import json


PLUGIN_OPTIONS = [
	# JSON-serialized dict of maps: {name: {"enabled": bool, "pairs": [["char", "replacement"], ...]}}
	TextOption("setting", "asciifier_maps", "{}"),
]


def _load_maps_from_config():
	"""Return dict of maps from config; never raise.

	Schema:
	{
	  "Default": {"enabled": true, "pairs": [["Å", "AA"], ["ß", "ss"]]}
	}
	"""
	raw = config.setting.get("asciifier_maps", "{}")
	try:
		data = json.loads(raw) if raw else {}
	except Exception:
		log.error("Asciifier: failed to parse asciifier_maps JSON; resetting", exc_info=True)
		data = {}
	if not isinstance(data, dict):
		data = {}
	# If no maps configured yet, seed with four defaults mirroring
	# Non-ASCII Equivalents' CHAR_TABLE split into categories.
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
	"""Combine all enabled maps into a single lookup table.

	Last map wins on duplicate characters, in insertion order of the dict.
	"""
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
	"""Return an ASCII-safe equivalent for a single character.

	- If the character is explicitly mapped in the effective table, use that.
	- Otherwise, return the original character unchanged.
	"""
	if ch in table:
		return table[ch]
	return ch


def to_ascii(text: str) -> str:
	"""Convert a string to an ASCII-safe representation.

	This function is intentionally simple and pure so it can be used both
	from tests and from Picard scripts. It is also idempotent: running it
	multiple times on the same string will not keep changing the output.
	"""
	if not text:
		return ""
	table = _build_effective_table()
	return "".join(_sanitize_char(ch, table) for ch in text)


def asciify(parser, value: str = "") -> str:
	"""Script function `$asciify()`.

	Usage in Picard scripts:
		$asciify(%artist%)

	The `parser` argument is provided by Picard's script engine and is not
	used here; we only care about the string value.
	"""
	# Picard passes values as strings; if nothing provided, return empty.
	if value is None:
		return ""
	return to_ascii(str(value))


register_script_function(asciify)

# Manual smoke-test examples (run from a separate helper or REPL):
#   from asciifier.to_ascii import to_ascii
#   for s in [
#       "Beyoncé — Déjà Vu",
#       "Ångström — Weißß",
#       "Rock & Roll – Live ★",
#       "Normal ASCII string",
#   ]:
#       print(s, "->", to_ascii(s))


class AsciifierOptionsPage(OptionsPage):
	"""Options page to manage character maps.

	Each map is a grid of characters and their replacements. Users can:
	- Toggle maps on/off.
	- Add/remove maps.
	- Edit the character→replacement pairs for each map.

	Storage is JSON in `config.setting["asciifier_maps"]`.
	"""

	NAME = "asciifier"
	TITLE = "Asciifier"
	PARENT = "plugins"

	def __init__(self, parent=None):
		from PyQt5.QtWidgets import (
			QVBoxLayout, QLabel, QCheckBox, QHBoxLayout,
			QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
		)
		from PyQt5.QtCore import Qt

		super().__init__(parent)
		self._maps = {}
		self._current_map_name = None

		layout = QVBoxLayout(self)

		desc = QLabel(
			"Configure character maps used by $asciify(). "
			"Each map is a set of character → replacement pairs. "
			"You can enable/disable maps, edit them, or create your own."
		)
		desc.setWordWrap(True)
		layout.addWidget(desc)

		self.unaccent_checkbox = QCheckBox("Use unaccent() fallback for unmapped characters")
		layout.addWidget(self.unaccent_checkbox)

		# Map selection row
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

		# Character grid for current map
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

		# Wire signals
		self.add_map_btn.clicked.connect(self._on_add_map)
		self.remove_map_btn.clicked.connect(self._on_remove_map)
		self.map_select.currentTextChanged.connect(self._on_map_changed)
		self.map_enabled_checkbox.toggled.connect(self._on_map_enabled_toggled)
		self.add_row_btn.clicked.connect(self._on_add_row)
		self.remove_row_btn.clicked.connect(self._on_remove_row)

	def _ensure_at_least_one_map(self):
		if self._maps:
			return
		# Create an empty default map that does nothing but can be edited.
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
		# Do not allow removing the last map; keep at least one.
		if len(self._maps) == 1:
			self._maps[name]["pairs"] = []
			self._load_current_map_into_table()
			return
		self._maps.pop(name, None)
		self._current_map_name = next(iter(self._maps.keys()), None)
		self._refresh_map_list()

	def _on_map_changed(self, name: str):
		# Persist any edits from the previous map before switching.
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
		self.unaccent_checkbox.setChecked(
			config.setting.get("asciifier_use_unaccent_fallback", True)
		)
		self._maps = _load_maps_from_config()
		self._ensure_at_least_one_map()
		self._refresh_map_list()

	def save(self):
		self._save_table_into_current_map()
		_save_maps_to_config(self._maps)
		config.setting["asciifier_use_unaccent_fallback"] = (
			self.unaccent_checkbox.isChecked()
		)
		log.debug("Asciifier: saved %d maps", len(self._maps))


register_options_page(AsciifierOptionsPage)
