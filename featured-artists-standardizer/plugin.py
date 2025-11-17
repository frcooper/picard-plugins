"""Featured Artists — Standardizer plugin entry point.

This module is the main plugin file for Picard and the library entry
point for the Featured Artists — Standardizer plugin.
"""

from picard.config import TextOption
from picard.metadata import (
	register_album_metadata_processor,
	register_track_metadata_processor,
)
from picard import config, log
from picard.ui.options import (
	register_options_page,
	OptionsPage,
)
import re


PLUGIN_NAME = "Featured Artists  Standardizer"
PLUGIN_AUTHOR = "FRC + ChatGPT (derives from community plugin authors)"
PLUGIN_DESCRIPTION = "Enforce label-style handling of featured artists: keep folders clean, move features to titles, normalize separators, avoid duplicates."
PLUGIN_VERSION = '1.1.0'
PLUGIN_API_VERSIONS = ["0.9.0", "0.10", "0.15", "0.16", "2.0"]
PLUGIN_LICENSE = "GPL-3.0-or-later"
PLUGIN_LICENSE_URL = "https://gnu.org/licenses/gpl.html"


PLUGIN_OPTIONS = [
	TextOption("setting", "featured_artists_whitelist", ""),
]


_FEAT_TOKEN_RE = re.compile(r"(?i)\b(?:feat\.|featuring|with)\b")
_FEAT_SPLIT_RE = re.compile(r"(?i)(.*?)(?:\bfeat\.|\bfeaturing\b|\bwith\b)\s*(.*)")
_FEAT_SEP_RE = re.compile(
	r"(?:\s*,\s*|\s*&\s*|\s*;\s*|\s*\+\s*|\s+and\s+|\s+\/\s+)",
	re.IGNORECASE,
)
_FT_NORMALIZE_RE = re.compile(r" f(ea)?t(\.|uring)? ", re.IGNORECASE)


class FeaturedArtistsOptionsPage(OptionsPage):
	NAME = "featured_artists"
	TITLE = "Featured Artists"
	PARENT = "plugins"

	def __init__(self, parent=None):
		super().__init__(parent)
		from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPlainTextEdit

		layout = QVBoxLayout(self)

		description = QLabel(
			"Configure how featured artists are handled by the Featured Artists Standardizer plugin."
		)
		description.setWordWrap(True)
		layout.addWidget(description)

		format_info = QLabel(
			"Format enforced:\n"
			"- Track titles: append \"(feat. A; B)\" once; keep the lead artist in ARTIST.\n"
			"- Album titles: append \"(feat. )\" if ALBUMARTIST has features; skip Various Artists.\n"
			"- Recognizes tokens: feat., featuring, with.\n"
			"- Splits guests on commas, &, +, ;, ' and ', and ' / ' (slash only when surrounded by spaces).\n"
			"- Order preserved; duplicates removed case-insensitively.\n"
			"- Whitelist artist full credits to skip processing (e.g., an exact artist credit string)."
		)
		format_info.setWordWrap(True)
		layout.addWidget(format_info)

		whitelist_label = QLabel(
			"Artist whitelist (one per line, or separate with commas/semicolons).\n"
			"Exact full artist credits listed here will be left untouched even if they contain tokens like 'feat.' or 'with'."
		)
		whitelist_label.setWordWrap(True)
		layout.addWidget(whitelist_label)

		self.whitelist_edit = QPlainTextEdit()
		self.whitelist_edit.setPlaceholderText("Artist Name 1\nArtist Name 2")
		self.whitelist_edit.setFixedHeight(90)
		layout.addWidget(self.whitelist_edit)

		layout.addStretch()
		self.ui = self

	def load(self):
		self.whitelist_edit.setPlainText(config.setting.get("featured_artists_whitelist", ""))

	def save(self):
		raw_wl = self.whitelist_edit.toPlainText().strip()
		config.setting["featured_artists_whitelist"] = raw_wl
		log.debug("Featured Artists: updated whitelist (%d chars)", len(raw_wl))


def _strip_wrappers(s: str) -> str:
	if not s:
		return ""
	t = s.strip()
	pairs = [("(", ")"), ("[", "]"), ("{", "}")]
	changed = True
	while changed and t:
		changed = False
		for left, right in pairs:
			if t.startswith(left) and t.endswith(right):
				inner = t[1:-1].strip()
				t = inner
				changed = True
				break
	return t


def _normalize_feat_list(feat_tail: str):
	if not feat_tail:
		return []
	parts = [p for p in _FEAT_SEP_RE.split(feat_tail) if p]
	seen = set()
	ordered = []
	for p in parts:
		t = _strip_wrappers(p)
		if not t:
			continue
		k = t.casefold()
		if k in seen:
			continue
		seen.add(k)
		ordered.append(t)
	return ordered


def _already_has_feat_suffix(title: str) -> bool:
	return bool(re.search(r"(?i)\(\s*(?:feat\.|featuring|with)\s+.+\)\s*$", title or ""))


def _split_artist_feat(artist: str):
	if not artist:
		return "", []
	m = _FEAT_SPLIT_RE.match(artist)
	if not m:
		return artist, []
	lead, tail = m.group(1), m.group(2)
	lead = _strip_wrappers(lead)
	tail = _strip_wrappers(tail)
	return (lead or artist), _normalize_feat_list(tail)


def _parse_whitelist():
	try:
		raw = config.setting.get("featured_artists_whitelist", "")
	except Exception:
		raw = ""
	if not raw:
		return set()
	items = [
		itm.strip() for itm in re.split(r"[\n,;]", raw) if itm.strip()
	]
	return {itm.casefold() for itm in items}


def _is_whitelisted(full_artist_credit: str) -> bool:
	if not full_artist_credit:
		return False
	wl = _parse_whitelist()
	if not wl:
		return False
	return full_artist_credit.strip().casefold() in wl


def _is_whitelisted_credit_or_lead(full_artist_credit: str) -> bool:
	if _is_whitelisted(full_artist_credit):
		return True
	lead, _ = _split_artist_feat(full_artist_credit or "")
	if lead and _is_whitelisted(lead):
		return True
	return False


def _standardize_join_phrases(artists_str: str, artists_list):
	try:
		if not artists_str or not artists_list:
			return artists_str
		match_exp = r"(\s*.*\s*)".join(map(re.escape, artists_list)) + r"(\s*.*$)"
		m = re.match(match_exp, artists_str)
		if not m:
			return artists_str
		joins = list(m.groups())
		joins = [_FT_NORMALIZE_RE.sub(" feat. ", j) for j in joins]
		joins.append("")
		return "".join(artist + join for artist, join in zip(artists_list, joins))
	except Exception:
		return artists_str


def _get_aav_lead_and_guests(md, scope: str):
	try:
		prefix = f"~artists_{scope}_"
		lead = md.get(prefix + "primary_cred") or md.get(prefix + "primary_std")
		guests = md.get(prefix + "additional_cred_multi") or md.get(prefix + "additional_std_multi")
		if isinstance(guests, str):
			guests = [guests]
		if lead and guests:
			return str(lead), [str(g) for g in guests if g]
	except Exception:
		pass
	return None, None


def move_album_featartists(tagger, metadata, release):
	lead, feat = _get_aav_lead_and_guests(metadata, "album")
	if lead is not None and _is_whitelisted_credit_or_lead(lead):
		log.debug("Featured Artists: skipping album (AAV lead %r whitelisted)", lead)
		return
	albumartist = metadata.get("albumartist", "")
	if not albumartist and lead:
		albumartist = lead
	if not albumartist:
		return
	if _is_whitelisted_credit_or_lead(albumartist):
		log.debug("Featured Artists: skipping albumartist %r (whitelisted)", albumartist)
		return
	try:
		albumartists_list = metadata.getall("~albumartists")
	except Exception:
		albumartists_list = []
	if albumartist and albumartists_list:
		std = _standardize_join_phrases(albumartist, albumartists_list)
		if std != albumartist:
			metadata["albumartist"] = std
			albumartist = std
	albumartistsort = metadata.get("albumartistsort", "")
	try:
		albumartists_sort_list = metadata.getall("~albumartists_sort")
	except Exception:
		albumartists_sort_list = []
	if albumartistsort and albumartists_sort_list:
		std_sort = _standardize_join_phrases(albumartistsort, albumartists_sort_list)
		if std_sort != albumartistsort:
			metadata["albumartistsort"] = std_sort
	if albumartist.strip().lower() == "various artists":
		log.debug("Featured Artists: %s", "Skipping Various Artists album")
		return
	if not feat:
		lead, feat = _split_artist_feat(albumartist)
	if not feat:
		return
	feat_str = "; ".join(feat)
	log.debug(
		"Featured Artists: %s",
		"Processing album '%s': moving featured artists '%s' from album artist to album title" % (metadata.get('album', 'Unknown'), feat_str),
	)
	metadata["albumartist"] = lead
	if metadata.get("albumartistsort"):
		lead_sort, _ = _split_artist_feat(metadata.get("albumartistsort", ""))
		metadata["albumartistsort"] = lead_sort
	album = metadata.get("album", "")
	if album and not _already_has_feat_suffix(album):
		new_album = "%s (feat. %s)" % (album, feat_str)
		metadata["album"] = new_album
		log.debug("Featured Artists: %s", "Updated album title to: '%s'" % new_album)


def move_track_featartists(tagger, metadata, track, release):
	lead, feat = _get_aav_lead_and_guests(metadata, "track")
	artist = metadata.get("artist", "")
	if not artist and lead:
		artist = lead
	if _is_whitelisted_credit_or_lead(artist or lead or ""):
		log.debug("Featured Artists: skipping artist %r (whitelisted via AAV or tags)", artist or lead)
		return
	try:
		artists_list = metadata.getall("artists")
	except Exception:
		artists_list = []
	if artist and artists_list:
		std = _standardize_join_phrases(artist, artists_list)
		if std != artist:
			metadata["artist"] = std
			artist = std
	artistsort = metadata.get("artistsort", "")
	try:
		artists_sort_list = metadata.getall("~artists_sort")
	except Exception:
		artists_sort_list = []
	if artistsort and artists_sort_list:
		std_sort = _standardize_join_phrases(artistsort, artists_sort_list)
		if std_sort != artistsort:
			metadata["artistsort"] = std_sort
	if not feat:
		lead, feat = _split_artist_feat(artist)
	feat_str = "; ".join(feat)
	if feat:
		log.debug(
			"Featured Artists: %s",
			"Processing track '%s': moving featured artists '%s' from artist to title" % (metadata.get('title', 'Unknown'), feat_str),
		)
		metadata["artist"] = lead
		if metadata.get("artistsort"):
			lead_sort, _ = _split_artist_feat(metadata.get("artistsort", ""))
			metadata["artistsort"] = lead_sort
	title = metadata.get("title", "")
	if feat and title and not _already_has_feat_suffix(title):
		new_title = "%s (feat. %s)" % (title, feat_str)
		metadata["title"] = new_title
		log.debug("Featured Artists: %s", "Updated title to: '%s'" % new_title)


register_album_metadata_processor(move_album_featartists)
register_track_metadata_processor(move_track_featartists)
register_options_page(FeaturedArtistsOptionsPage)
log.info("Featured Artists: %s", "Featured Artists Standardizer v%s loaded" % PLUGIN_VERSION)
