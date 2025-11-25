import pytest

from picard.metadata import Metadata


@pytest.fixture
def featured_artists_module(picard_plugin_loader):
	return picard_plugin_loader("featured-artists-standardizer/featured-artists-standardizer.py")


def test_normalize_feat_list_deduplicates_and_strips(featured_artists_module):
	normalize = featured_artists_module._normalize_feat_list
	result = normalize(" (Guest A) & Guest B, guest a / Guest C ")
	assert result == ["Guest A", "Guest B", "Guest C"]


def test_split_artist_feat_extracts_lead_and_guests(featured_artists_module):
	lead, guests = featured_artists_module._split_artist_feat("Lead Artist feat. Guest A & (Guest B)")
	assert lead == "Lead Artist"
	assert guests == ["Guest A", "Guest B"]


def test_apply_feat_suffix_replaces_existing_suffix(featured_artists_module):
	title = "Song Name (feat. Old Guest)"
	result = featured_artists_module._apply_feat_suffix(title, ["New Guest"])
	assert result == "Song Name (feat. New Guest)"


def test_whitelist_skips_processing_for_matching_lead(featured_artists_module):
	featured_artists_module.config.setting["featured_artists_whitelist"] = "Lead Artist"
	lead = "Lead Artist feat. Guest"
	assert featured_artists_module._is_whitelisted_credit_or_lead(lead)


def test_move_track_featartists_moves_guests_to_title(featured_artists_module):
	md = Metadata()
	md["artist"] = "Lead Artist feat. Guest A & Guest B"
	md["title"] = "Song Title"
	featured_artists_module.move_track_featartists(None, md, None, None)
	assert md["artist"] == "Lead Artist"
	assert md["title"] == "Song Title (feat. Guest A; Guest B)"


def test_move_track_featartists_respects_whitelist(featured_artists_module):
	featured_artists_module.config.setting["featured_artists_whitelist"] = "Lead Artist"
	md = Metadata()
	md["artist"] = "Lead Artist feat. Guest"
	md["title"] = "Song"
	featured_artists_module.move_track_featartists(None, md, None, None)
	assert md["artist"] == "Lead Artist feat. Guest"
	assert md["title"] == "Song"


def test_move_album_featartists_updates_album_title(featured_artists_module):
	md = Metadata()
	md["albumartist"] = "Lead Artist feat. Guest"
	md["album"] = "Album Title"
	featured_artists_module.move_album_featartists(None, md, None)
	assert md["albumartist"] == "Lead Artist"
	assert md["album"] == "Album Title (feat. Guest)"
