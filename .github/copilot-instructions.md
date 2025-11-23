# Copilot instructions for this repo

Context: This repo contains MusicBrainz Picard plugins. No external deps. These plugins target Picard 2.0+.

Never make edits to anything in the 3rd-party/ tree.
Never make edits to anything in the picard/ tree. This is Picard's own codebase for reference only.

Project conventions
- Logging: use picard's builtin log; prefix messages with the plugin name. 
- Settings: define with `BoolOption("setting", key, default)` in `PLUGIN_OPTIONS`; read via `config.setting[key]`. When loading settings in code or options pages, follow Picard's standard behaviour: use the stored value if the key exists in `config.setting`, otherwise fall back to the default from `PLUGIN_OPTIONS`.
- Options UI: subclass `OptionsPage`; set `NAME`, `TITLE`, `PARENT='plugins'`. Build widgets directly on `self` and assign `self.ui = self`. Uses PyQt5.
- Reset controls: each plugin must expose a "Reset" action that deletes all of its stored keys from `config.setting` (equivalent to a fresh install) without disturbing other plugins.
- Self-uninstall: each plugin's options page must offer a "Self-Uninstall" action that runs the reset logic and then disables/uninstalls the plugin as if the user clicked the uninstall button on Picard's Plugins page.
- Release assets: when packaging a plugin zip for a release, name the archive exactly after the plugin module (e.g. `asciifier.zip`) with no version suffix so Picard can import it.
- use semantic commit messages.
- increment the version number intelligently based on the type of changes made.

Content style
- Do not use emojis anywhere in this repository (code, docs, commit messages, or automated comments).

Critical workflows (manual testing)
- Enable debug logs: in Picard, set Logging level to Debug and use Help → View Log to see `log.debug` output from these plugins.

This file is for general instructions to help GitHub Copilot provide better suggestions when working on this repository. Each plugin should also have its own specific instructions in its directory.

Every plugin should have complete metadata in its python file, including name, version, author, description, and URL.
