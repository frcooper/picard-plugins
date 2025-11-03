# Copilot instructions for this repo

Context: This repo contains MusicBrainz Picard plugins. No external deps.

Project conventions
- Logging: use picard's builtin log; prefix messages with the plugin name. 
- Settings: define with `BoolOption("setting", key, default)` in `PLUGIN_OPTIONS`; read via `config.setting[key]`.
- Options UI: subclass `OptionsPage`; set `NAME`, `TITLE`, `PARENT='plugins'`. Build widgets directly on `self` and assign `self.ui = self`. Uses PyQt5.
- use semantic commit messages.
- increment the version number intelligently based on the type of changes made.

Critical workflows (manual testing)
- Enable debug logs: in Picard, set Logging level to Debug and use Help → View Log to see `log.debug` output from these plugins.

