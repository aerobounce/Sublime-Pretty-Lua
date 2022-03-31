# 🌙 Pretty Lua

### Lua Formatter for Sublime Text

[![](https://img.shields.io/badge/Platforms-Linux%20/%20macOS%20/%20Windows-blue.svg)][packagecontrol]
[![](https://img.shields.io/badge/Sublime%20Text-3+-orange.svg)][packagecontrol]
[![](https://img.shields.io/github/v/tag/aerobounce/Sublime-Pretty-Lua?display_name=tag)][tags]

- Uses [`stylua`][stylua]
- Format on Save
- Fast Formatting
- Syntax Checking
- Inline Syntax Error Popup
- Auto Scroll to the point Parsing Error occurred
- Multiple Candidate Paths to `.stylua.toml`


## Install

1. Install [`stylua`][stylua]
2. `Package Control: Install Package`
3. Install `Pretty Lua`
4. Linux / Windows users: Open Settings by <kbd>Preferences: Pretty Lua Settings</kbd> and setup path to `stylua`

```js
{
    // Absolute Path to `stylua` Binary
    "binary": ".../stylua"
}
```

[tags]: https://github.com/aerobounce/Sublime-AutoClosePanel/tags
[packagecontrol]: https://packagecontrol.io/packages/Pretty%20Lua
[stylua]: https://github.com/JohnnyMorganz/StyLua
