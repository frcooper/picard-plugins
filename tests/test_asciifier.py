import json

from picard.metadata import Metadata


def test_asciify_replaces_characters_using_default_maps(asciifier_module):
	value = "Æon—Flux ß"
	result = asciifier_module.asciify(None, value)
	assert result == "AEon--Flux ss"


def test_asciify_returns_empty_string_for_none_input(asciifier_module):
	assert asciifier_module.asciify(None, None) == ""


def test_to_ascii_honors_custom_char_maps(asciifier_module):
	custom_maps = {
		"greek": {
			"enabled": True,
			"pairs": [["Ω", "Omega"], ["☆", "*"]],
		}
	}
	asciifier_module.config.setting["asciifier_maps"] = json.dumps(custom_maps, ensure_ascii=False)
	assert asciifier_module.to_ascii("Ω☆Ω") == "Omega*Omega"


def test_to_ascii_ignores_disabled_maps(asciifier_module):
	disabled_maps = {
		"custom": {
			"enabled": False,
			"pairs": [["ß", "XX"]],
		}
	}
	asciifier_module.config.setting["asciifier_maps"] = json.dumps(disabled_maps, ensure_ascii=False)
	assert asciifier_module.to_ascii("ß") == "ß"


def test_parse_auto_tags_handles_commas_and_newlines(asciifier_module):
	raw = "title, album\nartist , \ncomment"
	assert asciifier_module._parse_auto_tags(raw) == ["title", "album", "artist", "comment"]


def test_auto_clean_metadata_updates_strings_and_lists(asciifier_module):
	md = Metadata()
	md["title"] = "Æon—Flux"
	md["artists"] = ["Æ", "ß"]
	md["comment"] = "Æ"
	table = {"Æ": "AE", "—": "--", "ß": "ss"}
	tags = ["title", "artists"]
	asciifier_module._auto_clean_metadata(md, table, tags)
	assert md["title"] == "AEon--Flux"
	assert md["artists"] == ["AE", "ss"]
	assert md["comment"] == "Æ"


def test_auto_album_processor_respects_disabled_setting(asciifier_module):
	asciifier_module.config.setting["asciifier_auto_enabled"] = False
	md = Metadata({"title": "Æon"})
	asciifier_module._auto_album_processor(None, md, None)
	assert md["title"] == "Æon"


def test_auto_track_processor_cleans_only_configured_tags(asciifier_module):
	asciifier_module.config.setting["asciifier_auto_enabled"] = True
	asciifier_module.config.setting["asciifier_auto_tags"] = "title, artist"
	md = Metadata()
	md["title"] = "Æon"
	md["artist"] = "Æ"
	md["comment"] = "Æ"
	asciifier_module._auto_track_processor(None, md, None, None)
	assert md["title"] == "AEon"
	assert md["artist"] == "AE"
	assert md["comment"] == "Æ"
