# Convention 2 — 3-layer styling

Keep style values (styleboxes, colors, fonts, font sizes) in `.tres` and `.tscn`
files. Three layers, each with one job. The payoff: every visual value can be
tuned and previewed in the editor without a rebuild, and the structure code
stays free of style noise.

## Layer 1 — base controls use a project `Theme`

A `Theme` resource defines the default look of each `Control` type — `Button`,
`Label`, `Panel`, `ScrollBar`, `LineEdit`, tooltips, and so on. Assign it once
and every `Control` in the tree inherits it:

- project-wide: `display/theme/custom = "res://ui/app_theme.tres"` in
  `project.godot`, or
- on a root `Control` of a screen: its `theme` property.

Inside the `Theme`, base controls are skinned with **`StyleBoxTexture`** for a
hand-drawn look. A `StyleBoxTexture` is 9-slice: `texture_margin_left/top/
right/bottom` mark the four corners and borders of a small source PNG; the
center stretches. A 20×20 button PNG with `texture_margin = 2` skins a button of
any size — small art asset, 9-slice, arbitrary dimensions. One `Theme` with a
set of styleboxes covers the whole project.

You almost never touch the Theme from code. You build it in the editor's Theme
editor (or hand-edit the `.tres`).

## Layer 2 — art-driven buttons use `TextureButton`, not the Theme

Some buttons are *defined by their artwork* — a shop item card, a build-menu
option, an icon button, a tab. Their look is not "a themed Button"; it is a
specific picture. Use `TextureButton` and give it the art directly:

```
[node name="BuyButton" type="TextureButton" parent="..."]
texture_normal  = ExtResource("btn_normal.png")
texture_pressed = ExtResource("btn_pressed.png")
texture_hover   = ExtResource("btn_hover.png")
ignore_texture_size = true
stretch_mode = 5          # KEEP_ASPECT_CENTERED
```

`TextureButton` deliberately ignores the Theme — the art owns the appearance,
three states are explicit textures. Use a plain themed `Button` for ordinary
text buttons; use `TextureButton` when the button *is* a graphic. (A regular
`Button` with an `icon` is not the same: the Theme's content margins shrink the
icon — `TextureButton` uses the whole rect.)

### Icon-first controls

Prefer icons over visible text for state, information, emotion, and action
hints when the icon is recognizable from context. The skill bundles complete
CC0 asset packs for this:

- `assets/game-icon-pack-svg/no-padding/8-ui/` for common UI actions:
  `save.svg`, `settings.svg`, `search.svg`, `cross.svg`, `tick.svg`,
  `visible.svg`, `invisible.svg`, `lock.svg`, `unlock.svg`, arrows, zoom,
  menu, refresh, warning, info.
- `assets/game-icon-pack-svg/no-padding/11-symbols/` for symbols and mood:
  emoji faces, digits, math symbols, currency symbols.
- `assets/game-icon-pack-svg/no-padding/{1-game,2-items,3-gear,6-buildings}/`
  for domain-specific HUD and inventory icons.
- `assets/kenney_ui-pack/PNG/<Color>/<Default|Double>/` or
  `assets/kenney_ui-pack/Vector/<Color>/` for button shells, arrows, stars,
  checks, crosses, toggles, sliders, and icon-state artwork.

Use `TextureRect` for passive indicators and `TextureButton` for clickable
icon controls. Give icon controls stable square dimensions in the `.tscn`
(`custom_minimum_size`, anchors, and container size flags), so hover/pressed
states do not resize the layout. Do not replace exact numbers, player names, or
ambiguous commands with icons; pair those with text or keep text visible.

For a visible text-free action button, use an icon texture and set non-visible
metadata such as `tooltip_text` or an accessible name if the project has an
accessibility layer. The visible surface stays icon-only; the semantics remain
recoverable for hover/help/testing.

## Layer 3 — local tweaks use `theme_override_*` in the `.tscn`

When one specific node needs to differ from the Theme — a larger heading font, a
distinct panel background, a custom color — set a `theme_override` on that node
in the scene file:

```
[node name="Heading" type="Label" parent="..."]
text = "Shop"
theme_override_font_sizes/font_size = 22
theme_override_colors/font_color = Color(0.86, 0.66, 0.27, 1)

[node name="Card" type="PanelContainer" parent="..."]
theme_override_styles/panel = SubResource("SbCard")
```

This keeps the exception visible and editable right where the node lives.

## Two phases: prototype Theme, then art graduation

The three layers are not a flat menu you pick from once — they shift weight across
a project's life. *Which layer carries the look* tells you what phase you are in.

**Phase 1 — prototype ("find the feel").** Layer 1 (the Theme) does almost all the
work, and this is where it matters most. One `Theme.tres` with a set of semantic
variations (`PrimaryButton`, `Card`, `HeadingLabel`, `BadgeAvailable`, …) dresses
the entire UI at once, and every value tunes live in the editor. This is the
fastest path from grey-box to "reads like a game," and it is usable by a designer,
a game planner, or a solo dev with no bespoke art — the generic CC0 packs (Kenney,
Game-Icon) fill the texture slots. At this stage a themed `Button` / `Label` /
`PanelContainer` + `StyleBoxTexture` from a generic pack is exactly right; reaching
for custom `TextureButton`s or hand-drawn frames now is premature. The Theme is the
feel-finding instrument.

**Phase 2 — art production ("make it ours").** Real art arrives element by element.
You do NOT rebuild — Convention 1 keeps paying off here: the scene structure is
untouched, you only swap style *resources* beneath it. Elements *graduate* out of
the Theme as their art becomes specific:

- A frame / card / panel that now has bespoke art → keep it themed if many surfaces
  share the new look (swap the stylebox in the `Theme`), or move that one node to
  `theme_override_styles/panel` with its own `StyleBoxTexture` (Layer 3) if it's a
  one-off. Same 9-slice mechanism, new PNG — whether the PNG came from a generic
  pack or the artist re-sliced their own is irrelevant to the mechanism. "Generic
  assets vs bespoke art" is not a project *type* decided up front; it is just which
  texture the same stylebox points at in this phase.
- A button that becomes "a specific picture with its own hover / press states" →
  graduates to Layer 2: a `TextureButton` with three state textures, or — at the
  high end — a small custom `Control` subclass wrapping a `TextureRect` + a shader
  that tints on hover / press. Reach for the custom-`Control` + shader form when you
  want one art asset recolored programmatically, plus per-control behavior
  (controller-icon swap, SFX, long-press, focus routing).
- Generic-pack frames get replaced by the artist's own 9-slice assets through the
  same `StyleBoxTexture` slots.

The Theme does not vanish in Phase 2; it *thins*. It keeps owning the long tail —
scrollbars, tooltips, default body text, debug screens — while hero elements move to
bespoke art. A fully-arted shipped game is the extreme endpoint: nearly everything
has graduated and the Theme layer has atrophied to near-nothing. Slay the Spire 2
ships with *no* project Theme at all — every surface is authored `TextureRect` art +
shader tint + per-node `theme_override_*`, and its buttons are custom `Control`
subclasses, not `TextureButton`s. That is the *end* state of full art replacement,
not a starting choice — and not evidence the Theme was wrong to use in Phase 1. It
was the right prototype instrument; it did its job and got replaced.

**Takeaway:** start Theme-first every time — it is how anyone finds the feel fast —
then let individual elements graduate to `theme_override` and art-driven controls as
real art lands, keeping the scene structure fixed the whole way.

## What this rules out: `add_theme_*` from code

Do **not** style from script:

```csharp
// Wrong — style welded into code, invisible in the editor, needs a rebuild to tune.
label.AddThemeFontSizeOverride("font_size", 22);
label.AddThemeColorOverride("font_color", new Color("d4a84b"));
panel.AddThemeStyleboxOverride("panel", MakeStyleBox());
```

Instead put the value where it belongs:

- a value many nodes share → the **Theme** (Layer 1);
- a one-off on a specific node → a **`theme_override`** in that node's `.tscn`
  (Layer 3).

```csharp
// Right — the script only references and binds; no styling.
_heading = GetNode<Label>("%Heading");   // font size / color already set in the .tscn
```

Why: a style in a resource can be edited and previewed in the editor in seconds;
a style in code is invisible until runtime and every change is a recompile. Code
that builds *and* styles UI also becomes very long very fast — separating
"structure in `.tscn`, style in resources, behavior in script" keeps each part
small and each change cheap.

### The rare exception

Genuinely data-driven color — e.g. a rarity tier that tints a label by a value
computed at runtime — is legitimately code. Keep it to that: a small, dynamic,
per-instance value. It is not a license to build static styling in code.

## Framed and bordered UI

Do not accept raw, unstyled Godot controls as the final UI skin for a game HUD,
menu, modal, shop, inventory, or settings screen. Establish a framed visual
surface first, then place layout containers and icon/text content inside it.

Default choices:

- Use `PanelContainer` with `theme_override_styles/panel = StyleBoxTexture` for
  scalable panels, cards, HUD strips, modal bodies, and framed lists.
- Use `NinePatchRect` only for a purely decorative frame behind controls when
  the node does not need container behavior.
- Use `TextureButton` for art buttons from `kenney_ui-pack`; do not imitate
  those buttons with code-side colors and borders.

Bundled frame assets:

- `assets/kenney_fantasy-ui-borders/PNG/Default/Panel/` — filled panels.
- `assets/kenney_fantasy-ui-borders/PNG/Default/Border/` — framed panels.
- `assets/kenney_fantasy-ui-borders/PNG/Default/Transparent border/` —
  transparent center frames for overlay panels.
- `assets/kenney_fantasy-ui-borders/PNG/Default/Divider/` and
  `Divider Fade/` — separators.
- `assets/kenney_fantasy-ui-borders/PNG/Double/...` — higher-resolution
  versions of the same assets.
- `assets/kenney_fantasy-ui-borders/Vector/fantasy-ui-borders.svg` — vector
  source if the project needs custom export sizes.

Build the `StyleBoxTexture` in a `.tres` or directly in the `.tscn`, set
`texture_margin_left/top/right/bottom` to preserve the corners, and keep it in
the Theme if many panels share it. Use one consistent margin value per asset
family after checking the PNG dimensions in the editor; do not compute or patch
these margins from script.

## Summary

| Need | Where it goes |
|---|---|
| Default look of `Button` / `Label` / `Panel` / ... | project `Theme` (`.tres`) |
| A button that is a piece of art | `TextureButton` + texture properties |
| One node differs from the Theme | `theme_override_*` in the `.tscn` |
| State/action/emotion hint with clear meaning | Icon asset in `TextureRect` / `TextureButton` |
| Game panel/card/HUD/modal frame | `PanelContainer` + `StyleBoxTexture` frame asset |
| Truly runtime-computed color/value | code — but only that |
