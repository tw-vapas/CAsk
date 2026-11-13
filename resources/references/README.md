# UI References

These images are design mockups. Provider status, saved credentials, model availability,
and test controls are illustrative; no account was queried and no settings were changed.

| Image | Purpose |
| --- | --- |
| [Provider settings](provider-settings-mockup.png) | Shared provider connection, saved model configurations, and one active model per provider. |
| [Model picker](provider-model-picker-mockup.png) | Search a provider catalog, choose a model, and configure its display name and reasoning effort. |
| [Quick switch](provider-quick-switch-mockup.png) | Gemini-inspired capsule: query above, provider selector at the lower left, model selector and gear at the lower right. No send button. |
| [Provider menu](provider-quick-switch-provider-menu.png) | Expanded provider pill and rounded menu with connection labels and a selected-item checkmark. |
| [Model menu](provider-quick-switch-model-menu.png) | Expanded model pill and rounded menu with saved model configurations and reasoning descriptions. |
| [Original settings reference](model-settings-proposed.png) | Approved dark panel styling used by the current application. |

The provider fallback order and interaction details are proposals for review. These mockups
do not implement catalog discovery, request compatibility, or persistent selection.
The larger settings view illustrates content organization; the final HUD will need scrolling
to fit available screen space.

The latest input styling follows the user-supplied `gemini_1.png`, `gemini_2.png`, and
`gemini_3.png` references: borderless resting buttons, pill-shaped expanded buttons,
a rounded dark capsule, and rounded menus with secondary labels and checkmarks.
Only provider/model/settings controls are represented; Gemini-specific features are excluded.
Open-menu views are static compositions, not functional popup implementations.

Regenerate all provider mockups from the project root:

```bash
QT_QPA_PLATFORM=offscreen python3 resources/references/generate-provider-mockups.py
```

The renderer uses PyQt6, placeholder data, and transparent window hosts. It checks that
all four outer corners have zero alpha before saving each PNG beside this file.
The quick-switch renderer also verifies that the lower controls share the opaque capsule
background while the outer rounded corners remain transparent.
