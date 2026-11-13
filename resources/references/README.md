# UI References

## Settings Revision 2

The newest proposal addresses typography, provider accordions, bounded model scrolling,
inline deletion confirmation, and Add/Edit navigation inside one Settings window.
These six images share an 800x760 viewport. They are proposals, not runtime changes.

| Image | State |
| --- | --- |
| [Overview](settings-v2-overview.png) | One expanded provider, compact model rows in a separate scroll container, collapsed connection details, and a fixed footer. |
| [Add Model](settings-v2-add-model.png) | Step 1: searchable provider catalog within the same window. |
| [Configure Model](settings-v2-configure-model.png) | Step 2: display name, reasoning, and collapsed Advanced options. |
| [Edit Model](settings-v2-edit-model.png) | Edit a saved configuration; Back returns to the provider page. |
| [Remove Model](settings-v2-remove-model.png) | Inline confirmation inside the model list. |
| [Remove Provider](settings-v2-remove-provider.png) | Inline confirmation showing the affected model count. |

Typography uses the current CAsk font family with 14pt page titles, 11pt provider names,
10pt controls/model names, and 9pt secondary text. Panel opacity remains 75%, with
translucent nested surfaces and transparent rounded corners.

```bash
python3 resources/references/generate-settings-v2-mockups.py
```

For a local navigation/accordion/scrolling preview, run with `--preview` in a graphical
session. This is an illustrative prototype: model data is fixed, some controls are
presentation-only, and no credentials, network calls, or configuration files are used.
The renderer verifies that only one top-level window is visible, the model list can
scroll, and all exported images preserve the expected alpha values.

## Earlier References

These images are design mockups. Provider status, saved credentials, model availability,
and test controls are illustrative; no account was queried and no settings were changed.

| Image | Purpose |
| --- | --- |
| [Provider settings](provider-settings-mockup.png) | Shared provider connection, saved model configurations, and one active model per provider. |
| [Model picker](provider-model-picker-mockup.png) | Search a provider catalog, choose a model, and configure its display name and reasoning effort. |
| [Quick switch](provider-quick-switch-mockup.png) | Gemini-inspired capsule: query above, provider selector at the lower left, model selector and gear at the lower right. No send button. |
| [Provider menu](provider-quick-switch-provider-menu.png) | Expanded provider pill and rounded menu with connection labels and a selected-item checkmark. |
| [Model menu](provider-quick-switch-model-menu.png) | Expanded model pill and rounded menu with saved model configurations and reasoning descriptions. |
| [Original settings reference](model-settings-proposed.png) | Earlier settings layout, updated with a proposed translucent panel and card backgrounds. |

The provider fallback order and interaction details are proposals for review. These mockups
do not implement catalog discovery, request compatibility, or persistent selection.
The larger settings view illustrates content organization; the final HUD will need scrolling
to fit available screen space.

The latest input styling follows the user-supplied `gemini_1.png`, `gemini_2.png`, and
`gemini_3.png` references: borderless resting buttons, pill-shaped expanded buttons,
a rounded capsule, and rounded menus with secondary labels and checkmarks.
Colors and opacity retain the current CAsk theme: input background
`rgba(27, 31, 38, 0.75)`, menu background `rgba(27, 31, 38, 0.95)`, translucent
white borders, `#e6ebf5` text, and the existing yellow hover/selection accents.
Only provider/model/settings controls are represented; Gemini-specific features are excluded.
Open-menu views are static compositions, not functional popup implementations.

Provider Settings, Model Picker, and the original settings reference now also use 75%
opacity on the outer panel, with translucent card and selection surfaces. Stacked surfaces
combine their opacity; text and primary action buttons retain contrast. These are preview
changes only; the application's current settings stylesheet is unchanged.

Regenerate all six reference images from the project root:

```bash
QT_QPA_PLATFORM=offscreen python3 resources/references/generate-provider-mockups.py
```

The renderer uses PyQt6, placeholder data, and transparent window hosts. It checks that
all four outer corners have zero alpha before saving each PNG beside this file.
The quick-switch renderer also verifies 75% capsule background opacity and 95% menu
background opacity while the outer rounded corners remain transparent.
The three settings/picker references also have 75% outer panel alpha checks.
