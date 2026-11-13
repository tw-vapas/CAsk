# UI References

These images are design mockups. Provider status, saved credentials, model availability,
and test controls are illustrative; no account was queried and no settings were changed.

| Image | Purpose |
| --- | --- |
| [Provider settings](provider-settings-mockup.png) | Shared provider connection, saved model configurations, and one active model per provider. |
| [Model picker](provider-model-picker-mockup.png) | Search a provider catalog, choose a model, and configure its display name and reasoning effort. |
| [Quick switch](provider-quick-switch-mockup.png) | A rounded container encloses only input and the right-arrow send button. Provider/model selection buttons and a gear settings button sit separately below, with transparent space around them. |
| [Original settings reference](model-settings-proposed.png) | Approved dark panel styling used by the current application. |

The provider fallback order and interaction details are proposals for review. These mockups
do not implement catalog discovery, request compatibility, or persistent selection.
The larger settings view illustrates content organization; the final HUD will need scrolling
to fit available screen space.

Regenerate the three provider mockups from the project root:

```bash
QT_QPA_PLATFORM=offscreen python3 resources/references/generate-provider-mockups.py
```

The renderer uses PyQt6, placeholder data, and transparent window hosts. It checks that
all four outer corners have zero alpha before saving each PNG beside this file.
The quick-switch renderer also verifies transparency between the input container and
the detached controls, and in the empty area beside those controls.
