---
name: godot-ui-tscn
description: >-
  Conventions for authoring Godot 4 UI scenes and styling. Use whenever
  building or editing any Godot UI: HUDs, panels, menus, modals, dialogs, list
  cells, popups, buttons, icon-only controls, state/status cues, or game-styled
  framed interfaces. Rules: build each UI component as a `.tscn` scene plus a
  thin script, keep static layout in scenes, instantiate only runtime-count
  items, keep styles in Theme/TextureButton/theme_override resources, prefer
  icons over visible text for state/information/emotion/action hints when the
  icon is unambiguous, and build base UI from framed/bordered assets or
  StyleBoxTexture rather than unstyled default controls. Bundles CC0 Game Icon
  Pack SVG, Kenney Fantasy UI Borders, and Kenney UI Pack assets for reuse.
---

# Godot 4 UI authoring conventions

Three conventions for building UI in Godot 4 that keep scenes editable in the
editor, styling consistent across a project, and scripts thin.

Follow them from the very first UI node. The alternative — assembling Control
trees and styling them in code — is cheap to start and expensive to live with:
it grows into hundreds of lines of `new Panel()` / `AddChild()` /
`AddThemeStyleboxOverride()` that duplicate what the editor already does, can't
be tuned visually, and scatter style values where no one can find them. A
mature, shipped Godot project keeps UI in scenes and resources; a code-built one
becomes a 3000-line file nobody wants to touch.

## When to use this

Whenever building or editing any Godot 4 UI: a HUD, a panel, a menu, a modal or
dialog, a list cell, a popup, a button row, an icon-only control, a state/status
indicator, or a framed game UI surface. Whenever about to construct a Control
node tree in a script. Whenever styling Godot UI. This applies to test and
experimental scenes as much as production — the conventions are about keeping
work maintainable, which matters everywhere.

## Convention 1 — author UI as `.tscn` + script pairs

Every UI component that can be a scene *is* a scene. Lay out its node tree —
`Panel`, `VBoxContainer`, `Label`, fixed `Button`s, `ScrollContainer`, ... — in a
`.tscn`, in the editor, with every node explicitly named and parented. The
attached script (`.cs` or `.gd`) does only three things:

1. `GetNode<T>("%Name")` to reference nodes the scene already declares;
2. connect and handle signals;
3. push data into those referenced nodes.

The script does **not** call `new Button()` / `new VBoxContainer()` to assemble
layout. If you find yourself writing that, stop — move the structure into the
`.tscn`.

**The one exception:** elements whose *count* is only known at runtime — N list
cells, one button per data row. Author each item type as its own small `.tscn`
(a prefab, in Unity terms), declare a container for them in the parent scene,
and `Instantiate()` + `AddChild` into that container at runtime. The item is
still a scene; only *how many* exist is decided in code.

**Mock items in the container.** Don't leave that container empty in the scene:
pre-place 2–3 instances of the item scene as mock samples (placeholder text is
fine) so designers and devs see and tune the real list layout in the editor
without running the game. The runtime fill code clears the container before
instantiating real items, so the mocks vanish for free — list code already
starts with a clear-and-rebuild loop; no helper class, no special naming or
group is needed. The convention is simply: *everything pre-placed inside a
runtime-filled container is a mock and gets cleared.*

**Nesting content inside an instanced wrapper needs Editable Children.** If you
parent caller content under an *instanced* sub-scene's inner node (a panel /
collapsible / frame holding `Content`), mark that instance **Editable Children**
(`[editable path=...]` in the `.tscn`) — otherwise the editor hides the nodes and
the **export silently drops them** (works from the editor, then `%Name`/paths are
null in the APK). See `references/structure.md`.

Why this matters:

- **The editor is the layout tool.** A `.tscn` can be opened, seen, and dragged.
  A tree built in code is invisible until you run the game — every tweak is a
  rebuild-and-relaunch.
- **One source of truth.** Code-built UI duplicates the structure: the node tree
  exists implicitly in the script *and* conceptually in your head. A `.tscn` is
  the single authoritative copy.
- **Named nodes are navigable.** `%PanelChrome`, `%TabBody` in a scene are
  greppable and clickable; a node created at `script.cs:412` is not.
- **Designers and future-you can edit it** without reading C#.

→ `references/structure.md` — concrete good/bad examples and the pairing pattern.

## Convention 2 — 3-layer styling, styles live in resources

Style values — `StyleBox`es, colors, font sizes — belong in `.tres` and `.tscn`
files, not in script. Three layers, each with a clear job:

1. **Base controls → a project `Theme`.** A `Theme` resource defines styleboxes,
   fonts, and colors for `Button` / `Label` / `ScrollBar` / `Panel` / etc. Every
   `Control` inherits it automatically. Set it once.
2. **Art-driven buttons → `TextureButton`, bypassing the Theme.** A button whose
   look *is* a piece of art — a shop card, a build option, an icon button — is a
   `TextureButton` with explicit `texture_normal` / `texture_pressed` /
   `texture_hover`. The Theme deliberately doesn't touch it; the art owns the
   look.
3. **Local tweaks → `theme_override_*` in the `.tscn`.** When one specific node
   needs a different stylebox or font size, set `theme_override_styles/panel`,
   `theme_override_font_sizes/font_size`, etc. on that node in the scene file.

What this rules out: calling `add_theme_stylebox_override` /
`add_theme_color_override` / `add_theme_font_size_override` from script. When a
style needs to change, change the resource — don't run code to patch it. Styles
in resources can be tuned and previewed in the editor without a rebuild; styles
in code can't.

These layers also describe a **timeline**, not just a static split. Early on the
**Theme** carries the whole look — one resource + semantic variations + generic
CC0 art lets a designer or planner find the feel fast with no bespoke assets. As
real art arrives, individual elements *graduate* out of the Theme into
`theme_override` and art-driven controls (`TextureButton`, or a custom `Control` +
shader tint), while the scene structure stays fixed. The Theme thins but rarely
disappears. Start Theme-first, graduate elements as art lands.

→ `references/styling.md` — the three layers with concrete examples, including
9-slice `StyleBoxTexture` setup, and the prototype-to-production shift.

## Convention 3 — icons first, framed surfaces first

For status, information, emotion, and action prompts, use a recognizable icon
instead of visible text whenever the meaning stays clear in context: save,
close, settings, lock, warning, success, visible/invisible, menu, arrows,
mood, resource type, item type. Keep visible text only for exact values,
names, sentences, ambiguous commands, or accessibility-critical labels.

The bundled assets are part of this skill and may be copied into a project:

- `assets/game-icon-pack-svg/` — CC0 SVG icons. Prefer `no-padding/8-ui` for
  generic UI actions, `no-padding/11-symbols` for symbols/mood, and domain
  folders such as `1-game`, `2-items`, `3-gear`, or `6-buildings` for game HUDs.
- `assets/kenney_fantasy-ui-borders/` — CC0 panel, border, divider, and
  transparent-border art for `PanelContainer` + `StyleBoxTexture`.
- `assets/kenney_ui-pack/` — CC0 buttons, sliders, checks, arrows, sounds, and
  font assets for `TextureButton`, toggle/check states, and art-driven controls.

Do not leave UI as raw unstyled Godot defaults unless it is a throwaway debug
screen. Start from `PanelContainer` / `NinePatchRect` / `StyleBoxTexture` frame
assets, then place icon controls inside the frame.

## The anti-pattern to recognize

A script with long stretches of `new Control()`, `AddChild()`,
`AddThemeStyleboxOverride()`, `AddThemeColorOverride()` — a whole UI built and
styled imperatively. When you see this, or feel tempted to write it, that's the
signal to move the structure into a `.tscn`, the style into a `Theme` or
`theme_override`, and state/action hints into icon resources where possible.
Done well, the script collapses to references + signals + data binding, and the
layout becomes something you can actually open and look at.

## Reference files

- `references/structure.md` — Convention 1 in depth: a wrong-vs-right example,
  the `.tscn` + script pairing, `unique_name_in_owner` / `%Name`, and the
  runtime-list exception.
- `references/styling.md` — Convention 2 in depth: the Theme layer, `TextureButton`,
  `theme_override`, 9-slice `StyleBoxTexture`, icon-first controls, framed UI
  assets, and why code-side `add_theme_*` is avoided.
