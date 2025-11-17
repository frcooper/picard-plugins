# -*- coding: utf-8 -*-
"""
Picard plugin: Standardize handling of featured artists.

Rules implemented
- Track level: Move featured artists from ARTIST credit into TITLE as
  "(feat. X; Y)" exactly once. Keep primary artist in ARTIST.
- Album level: If ALBUMARTIST contains a feature token, strip it from
  ALBUMARTIST/ALBUMARTISTSORT and append to ALBUM title as
  "(feat. …)". Skip Various Artists.
- Tokens recognized: "feat.", "featuring", "with" (case-insensitive).
- Separators normalized to "; " and duplicates removed while preserving order.

Based on Picard examples and the community plugin
"Feat. Artists in Titles" by Lukas Lalinsky, Michael Wiencek,
Bryan Toth, JeromyNix. Rewritten for stricter, idempotent behavior.

This plugin is a derivative work of GPL-licensed community code and is
distributed under the GPL-3.0-or-later license.
"""

PLUGIN_NAME = 'Featured Artists — Standardizer'
PLUGIN_AUTHOR = 'FRC + ChatGPT (derives from community plugin authors)'
PLUGIN_DESCRIPTION = 'Enforce label-style handling of featured artists: keep folders clean, move features to titles, normalize separators, avoid duplicates.'
PLUGIN_VERSION = '2.0.0'
PLUGIN_API_VERSIONS = ["0.9.0", "0.10", "0.15", "0.16", "2.0"]
PLUGIN_LICENSE = "GPL-3.0-or-later"
PLUGIN_LICENSE_URL = "https://gnu.org/licenses/gpl.html"

# Ensure required Picard configuration types are imported before use
from picard.config import BoolOption, TextOption

# Configuration options
PLUGIN_OPTIONS = [
    BoolOption("setting", "add_featured_artists_tag", False),
    TextOption("setting", "featured_artists_whitelist", ""),  # newline / comma / semicolon separated full artist credits to skip
]

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

# --- Patterns ---
# Marker like "feat.", "featuring", or "with"; case-insensitive
_FEAT_TOKEN_RE = re.compile(r"(?i)\b(?:feat\.|featuring|with)\b")
# Find the FIRST feature token and split lead vs featured tail
_FEAT_SPLIT_RE = re.compile(r"(?i)(.*?)(?:\bfeat\.|\bfeaturing\b|\bwith\b)\s*(.*)")
# Split multiple guest names by common separators
# Note: Do NOT split on bare '/' to avoid breaking names like 'AC/DC'.
# Only split on ' / ' (slash with spaces) and other standard separators.
_FEAT_SEP_RE = re.compile(
    r"(?:\s*,\s*|\s*&\s*|\s*;\s*|\s*\+\s*|\s+and\s+|\s+\/\s+)",
    re.IGNORECASE,
)

# Normalize any variant of ft/feat/featuring join phrases to " feat. "
_FT_NORMALIZE_RE = re.compile(r" f(ea)?t(\.|uring)? ", re.IGNORECASE)


# --- Logging ---
# Use Picard's built-in logger directly via `log.*`.


# --- Configuration UI ---

class FeaturedArtistsOptionsPage(OptionsPage):
    NAME = "featured_artists"
    TITLE = "Featured Artists"
    PARENT = "plugins"

    def __init__(self, parent=None):
        super().__init__(parent)
        # Picard 2.x uses PyQt5
        from PyQt5.QtWidgets import QVBoxLayout, QLabel, QCheckBox, QPlainTextEdit

        # Build UI directly on this OptionsPage widget to avoid blank pages
        layout = QVBoxLayout(self)

        # Description
        description = QLabel(
            "Configure how featured artists are handled by the Featured Artists Standardizer plugin."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        # Explain the enforced formatting so users know exactly what to expect
        format_info = QLabel(
            "Format enforced:\n"
            "- Track titles: append \"(feat. A; B)\" once; keep the lead artist in ARTIST.\n"
            "- Album titles: append \"(feat. …)\" if ALBUMARTIST has features; skip Various Artists.\n"
            "- Recognizes tokens: feat., featuring, with.\n"
            "- Splits guests on commas, &, +, ;, ' and ', and ' / ' (slash only when surrounded by spaces).\n"
            "- Order preserved; duplicates removed case-insensitively.\n"
            "- Optional: write FEATURED_ARTISTS as a multivalue tag.\n"
            "- Whitelist artist full credits to skip processing (e.g., an exact artist credit string)."
        )
        format_info.setWordWrap(True)
        layout.addWidget(format_info)

        # Add featured artists tag option
        self.add_featured_artists_checkbox = QCheckBox(
            "Add 'Featured Artists' multivalue tag"
        )
        self.add_featured_artists_checkbox.setToolTip(
            "When enabled, adds a 'FEATURED_ARTISTS' tag containing the normalized list of featured artists. "
            "This can be useful for scripts or other plugins that need to access the featured artists separately."
        )
        layout.addWidget(self.add_featured_artists_checkbox)

        # Whitelist textbox
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
        # Some Picard versions expect `self.ui` to reference the widget
        self.ui = self

    def load(self):
        self.add_featured_artists_checkbox.setChecked(
            config.setting["add_featured_artists_tag"]
        )
        self.whitelist_edit.setPlainText(config.setting.get("featured_artists_whitelist", ""))

    def save(self):
        config.setting["add_featured_artists_tag"] = \
            self.add_featured_artists_checkbox.isChecked()
        raw_wl = self.whitelist_edit.toPlainText().strip()
        config.setting["featured_artists_whitelist"] = raw_wl
        log.debug("Featured Artists: updated whitelist (%d chars)", len(raw_wl))


# --- Utility functions ---


def _strip_wrappers(s: str) -> str:
    """Trim balanced outer wrappers and whitespace.

    Only removes one or more layers of matching (), [], {} around the entire
    string. Does not strip dashes or inner punctuation to avoid altering
    legitimate artist names. Always trims surrounding whitespace.
    """
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
                # Only strip if it appears to be a single wrapping layer
                t = inner
                changed = True
                break
    return t


def _normalize_feat_list(feat_tail: str):
    """Return a de-duplicated list of featured artist names.

    - Splits the tail using conservative separators
    - Trims wrappers
    - Preserves original order while removing case-insensitive duplicates
    """
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
    # Detect any trailing suffix like "(feat. …)", "(featuring …)", or "(with …)"
    return bool(re.search(r"(?i)\(\s*(?:feat\.|featuring|with)\s+.+\)\s*$", title or ""))


def _split_artist_feat(artist: str):
    """Return (lead, [feat_list]) or (artist, []) if no token found."""
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
    """Parse configured whitelist into a casefolded set of full artist credits.

    Users can separate entries by newlines, commas, or semicolons. Empty lines ignored.
    """
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
    """Return True if the exact credit OR its lead artist is whitelisted.

    This ensures no alterations happen when the primary artist is in the
    whitelist, even if the displayed credit includes feature tokens.
    """
    if _is_whitelisted(full_artist_credit):
        return True
    lead, _ = _split_artist_feat(full_artist_credit or "")
    if lead and _is_whitelisted(lead):
        return True
    return False


def _standardize_join_phrases(artists_str: str, artists_list):
    """Normalize join phrases between credited artists to ' feat. '.

    This mirrors the behavior of the 'Standardise Feat.' plugin but keeps
    implementation local to this plugin. It reconstructs the string by
    finding the text between the credited artist names and replacing any
    variant of ft/feat/featuring with ' feat. '.

    If matching fails (e.g., mismatch between artists_list and artists_str),
    returns the original string unmodified.
    """
    try:
        if not artists_str or not artists_list:
            return artists_str
        # Build a regex that captures the text between each credited artist
        # Example: (\s*.*\s*) escaped(A) (\s*.*\s*) escaped(B) ... (\s*.*$)
        match_exp = r"(\s*.*\s*)".join(map(re.escape, artists_list)) + r"(\s*.*$)"
        m = re.match(match_exp, artists_str)
        if not m:
            return artists_str
        joins = list(m.groups())
        # Replace variants with canonical ' feat. '
        joins = [_FT_NORMALIZE_RE.sub(" feat. ", j) for j in joins]
        # There is one fewer join than artists; add empty tail to zip cleanly
        joins.append("")
        return "".join(artist + join for artist, join in zip(artists_list, joins))
    except Exception:
        # Be conservative: never break metadata if anything unexpected happens
        return artists_str


# --- Album-level processor ---

def move_album_featartists(tagger, metadata, release):
    albumartist = metadata.get("albumartist", "")
    if not albumartist:
        return
    if _is_whitelisted_credit_or_lead(albumartist):
        log.debug("Featured Artists: skipping albumartist %r (whitelisted)", albumartist)
        return
    # Pre-pass: normalize join phrases to 'feat.' using album artist credits list
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
    # Skip VA
    if albumartist.strip().lower() == "various artists":
        log.debug("Featured Artists: %s", "Skipping Various Artists album")
        return
    
    lead, feat = _split_artist_feat(albumartist)
    if not feat:
        return
    
    feat_str = "; ".join(feat)
    log.debug(
        "Featured Artists: %s",
        "Processing album '%s': moving featured artists '%s' from album artist to album title" % (metadata.get('album', 'Unknown'), feat_str),
    )
    
    # Update artists
    metadata["albumartist"] = lead
    if metadata.get("albumartistsort"):
        lead_sort, _ = _split_artist_feat(metadata.get("albumartistsort", ""))
        metadata["albumartistsort"] = lead_sort
    
    # Append to album title if not already present
    album = metadata.get("album", "")
    if album and not _already_has_feat_suffix(album):
        new_album = "%s (feat. %s)" % (album, feat_str)
        metadata["album"] = new_album
        log.debug("Featured Artists: %s", "Updated album title to: '%s'" % new_album)


# --- Track-level processor ---

def move_track_featartists(tagger, metadata, track, release):
    artist = metadata.get("artist", "")
    if _is_whitelisted_credit_or_lead(artist):
        log.debug("Featured Artists: skipping artist %r (whitelisted)", artist)
        return
    # Pre-pass: normalize join phrases to 'feat.' using credited artists list
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
    
    # Add to title once
    title = metadata.get("title", "")
    if feat and title and not _already_has_feat_suffix(title):
        new_title = "%s (feat. %s)" % (title, feat_str)
        metadata["title"] = new_title
        log.debug("Featured Artists: %s", "Updated title to: '%s'" % new_title)
    
    # Optional: expose clean featured list for user workflows (controlled by config)
    if feat and config.setting["add_featured_artists_tag"]:
        metadata["FEATURED_ARTISTS"] = feat
        log.debug("Featured Artists: %s", "Added FEATURED_ARTISTS tag: '%s'" % feat_str)
    elif feat:
        log.debug("Featured Artists: %s", "Featured artists found but FEATURED_ARTISTS tag disabled in configuration")


register_album_metadata_processor(move_album_featartists)
register_track_metadata_processor(move_track_featartists)

# Register the options page
register_options_page(FeaturedArtistsOptionsPage)

# Log initialization
log.info("Featured Artists: %s", "Featured Artists Standardizer v%s loaded" % PLUGIN_VERSION)
