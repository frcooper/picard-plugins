import importlib.util
import pathlib
import sys
import types

import pytest

MODULE_NAME = "asciifier_plugin_under_test"


class SettingStore(dict):
	"""Dictionary-like store that mimics Picard's config.setting."""

	def remove(self, key):
		if key in self:
			del self[key]


def _ensure_picard_stubs():
	if "picard" in sys.modules:
		return

	picard_module = types.ModuleType("picard")
	sys.modules["picard"] = picard_module

	config_module = types.ModuleType("picard.config")
	setattr(config_module, "setting", SettingStore())

	class _Option:  # pragma: no cover - used only for compatibility
		def __init__(self, *args, **kwargs):
			self.args = args
			self.kwargs = kwargs

	setattr(config_module, "TextOption", _Option)
	setattr(config_module, "BoolOption", _Option)
	sys.modules["picard.config"] = config_module

	log_module = types.ModuleType("picard.log")

	def _log(*args, **kwargs):  # pragma: no cover
		return None

	setattr(log_module, "debug", _log)
	setattr(log_module, "info", _log)
	setattr(log_module, "error", _log)
	setattr(log_module, "warning", _log)
	sys.modules["picard.log"] = log_module

	script_module = types.ModuleType("picard.script")
	setattr(script_module, "registered", [])

	def register_script_function(func):  # pragma: no cover - exercised indirectly
		script_module.registered.append(func)

	setattr(script_module, "register_script_function", register_script_function)
	sys.modules["picard.script"] = script_module

	metadata_module = types.ModuleType("picard.metadata")

	class Metadata(dict):
		pass

	setattr(metadata_module, "Metadata", Metadata)
	setattr(metadata_module, "_album_processors", [])
	setattr(metadata_module, "_track_processors", [])

	def register_album_metadata_processor(func):  # pragma: no cover - exercised indirectly
		metadata_module._album_processors.append(func)

	def register_track_metadata_processor(func):  # pragma: no cover - exercised indirectly
		metadata_module._track_processors.append(func)

	setattr(metadata_module, "register_album_metadata_processor", register_album_metadata_processor)
	setattr(metadata_module, "register_track_metadata_processor", register_track_metadata_processor)
	sys.modules["picard.metadata"] = metadata_module

	ui_module = types.ModuleType("picard.ui")
	sys.modules["picard.ui"] = ui_module

	options_module = types.ModuleType("picard.ui.options")
	setattr(options_module, "registered", [])

	class OptionsPage:  # pragma: no cover - compatibility shim
		def __init__(self, parent=None):
			self.parent = parent

	setattr(options_module, "OptionsPage", OptionsPage)

	def register_options_page(cls):  # pragma: no cover - exercised indirectly
		options_module.registered.append(cls)

	setattr(options_module, "register_options_page", register_options_page)
	sys.modules["picard.ui.options"] = options_module

	setattr(picard_module, "config", config_module)
	setattr(picard_module, "log", log_module)
	setattr(picard_module, "metadata", metadata_module)
	setattr(picard_module, "ui", ui_module)
	setattr(ui_module, "options", options_module)
	setattr(picard_module, "script", script_module)


def _load_asciifier_module():
	module_path = pathlib.Path(__file__).resolve().parents[1] / "asciifier" / "asciifier.py"
	spec = importlib.util.spec_from_file_location(MODULE_NAME, module_path)
	module = importlib.util.module_from_spec(spec)
	sys.modules[MODULE_NAME] = module
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_ensure_picard_stubs()


@pytest.fixture
def asciifier_module():
	config_module = sys.modules["picard.config"]
	config_module.setting.clear()

	metadata_module = sys.modules["picard.metadata"]
	metadata_module._album_processors.clear()
	metadata_module._track_processors.clear()

	script_module = sys.modules["picard.script"]
	script_module.registered.clear()

	options_module = sys.modules["picard.ui.options"]
	options_module.registered.clear()

	sys.modules.pop(MODULE_NAME, None)
	module = _load_asciifier_module()
	yield module
	sys.modules.pop(MODULE_NAME, None)
