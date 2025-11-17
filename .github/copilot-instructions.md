# Copilot instructions for this repo

Context: This repo contains MusicBrainz Picard plugins. No external deps. These plugins target Picard 2.0+.

Never make edits to anything in the 3rd-party/ tree.

Project conventions
- Logging: use picard's builtin log; prefix messages with the plugin name. 
- Settings: define with `BoolOption("setting", key, default)` in `PLUGIN_OPTIONS`; read via `config.setting[key]`.
- Options UI: subclass `OptionsPage`; set `NAME`, `TITLE`, `PARENT='plugins'`. Build widgets directly on `self` and assign `self.ui = self`. Uses PyQt5.
- use semantic commit messages.
- increment the version number intelligently based on the type of changes made.

Critical workflows (manual testing)
- Enable debug logs: in Picard, set Logging level to Debug and use Help → View Log to see `log.debug` output from these plugins.

This file is for general instructions to help GitHub Copilot provide better suggestions when working on this repository. Each plugin should also have its own specific instructions in its directory.

Every plugin should have complete metadata in its `__init__.py` file, including name, version, author, description, and URL.
