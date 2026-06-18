---
name: godot-ui-tscn
description: >-
  Conventions for authoring UI in Godot 4. Two rules: (1) build every UI
  component as a `.tscn` scene plus a thin script — author the node tree in the
  editor, and let the script only do GetNode references, signal wiring, and data
  binding; never assemble layout with `new Button()` / `new VBoxContainer()` in
  code. (2) Keep styling in resources with a 3-layer strategy — a project Theme
  for base controls, `TextureButton` for art-driven buttons, and
  `theme_override_*` in the `.tscn` for local tweaks; never call `add_theme_*`
  from script. Use this whenever building or editing any Godot 4 UI — a HUD,
  panel, menu, modal, dialog, list cell, popup, or button — whenever about to
  construct a Control node tree in a script, or whenever styling Godot UI. It
  applies to test and experimental scenes too. Consult it before writing Godot
  UI code so scenes stay editable in the editor and styling stays consistent.
---

# Godot 4 UI authoring conventions

Two conventions for building UI in Godot 4 that keep scenes editable in the
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
dialog, a list cell, a popup, a button row. Whenever about to construct a Control
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

→ `references/styling.md` — the three layers with concrete examples, including
9-slice `StyleBoxTexture` setup.

## The anti-pattern to recognize

A script with long stretches of `new Control()`, `AddChild()`,
`AddThemeStyleboxOverride()`, `AddThemeColorOverride()` — a whole UI built and
styled imperatively. When you see this, or feel tempted to write it, that's the
signal to move the structure into a `.tscn` and the style into a `Theme` or
`theme_override`. Done well, the script collapses to references + signals + data
binding, and the layout becomes something you can actually open and look at.

## Reference files

- `references/structure.md` — Convention 1 in depth: a wrong-vs-right example,
  the `.tscn` + script pairing, `unique_name_in_owner` / `%Name`, and the
  runtime-list exception.
- `references/styling.md` — Convention 2 in depth: the Theme layer, `TextureButton`,
  `theme_override`, 9-slice `StyleBoxTexture`, and why code-side `add_theme_*` is
  avoided.
