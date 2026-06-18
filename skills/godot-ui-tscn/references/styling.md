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

## Summary

| Need | Where it goes |
|---|---|
| Default look of `Button` / `Label` / `Panel` / ... | project `Theme` (`.tres`) |
| A button that is a piece of art | `TextureButton` + texture properties |
| One node differs from the Theme | `theme_override_*` in the `.tscn` |
| Truly runtime-computed color/value | code — but only that |
