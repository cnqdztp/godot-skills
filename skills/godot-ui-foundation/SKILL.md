---
name: godot-ui-foundation
description: |
  Cross-cutting UI foundation for any Godot 4 project: viewport stretch (the single most common reason UI looks "too small" on real devices), content_scale_factor on Retina / HiDPI / 4K displays (Godot 4 leaves it at 1.0 so desktop UI renders tiny inside the 2× backing buffer — fix via a Paragraphic-style RetinaManager autoload that reads DisplayServer.screen_get_scale and compensates window size), theme variation taxonomy (TitleLabel / HeadingLabel / PrimaryButton / BadgeAvailable / etc.), and variable-font weights done right (the FourCC integer-key gotcha that silently breaks string keys). Apply BEFORE authoring per-screen scenes. Complements godot-ui-tscn (scene structure + 3-layer styling principle) and godot-scaffold (generates project skeleton).
---

# Godot UI Foundation

The cross-cutting layer that sits beneath every screen. If these three things aren't set right, every later scene fights an uphill battle:

1. **Viewport stretch** — how the design-time viewport maps to the actual device window
2. **Theme variation taxonomy** — named semantic styles you reach for in every scene
3. **Variable font weights** — typographic hierarchy that actually renders the weights you ask for

This skill is the "set it once, forget it" foundation. After this, write scenes with `godot-ui-tscn`'s 3-layer principle (Theme → TextureButton → `theme_override_*`).

## When to use

- Setting up a new Godot project's UI from zero (after `godot-scaffold`)
- Diagnosing "UI looks tiny on real device" / "UI stretches weirdly" / "fonts all look the same weight"
- **Diagnosing "UI is tiny on my Retina Mac / 4K monitor / scaled Windows display" in a desktop creative tool** — the content_scale_factor issue (Section 1b)
- Designing a theme variation taxonomy from scratch
- Adding variable font weights and they don't appear

## 1 — Viewport stretch is NEVER `disabled` in production

The Godot 4 default is `window/stretch/mode = "disabled"`. That setting only fits pixel-art games where the design viewport equals the window. **Any UI project that renders on multiple device sizes must override**, or the design viewport (say 420×760) will draw at native pixels in the top-left of a 1080×2400 device and look ~17% of expected size.

### Decision: stretch/mode

| Mode | When | Effect |
|---|---|---|
| `disabled` | Pixel-art games where 1 design px = 1 window px | No scaling; UI may be tiny |
| `canvas_items` | **Default for UI projects** | Auto-scales 2D drawing; layout containers recompute against scaled viewport |
| `viewport` | Old-school fixed virtual resolution | Whole viewport rasterizes then scales; UI gets blurry on large screens |

For any modern UI app: **`canvas_items`**.

### Decision: stretch/aspect

| Aspect | When | Behavior |
|---|---|---|
| `ignore` | Never (distorts) | Stretches to fill, breaks circles into ovals |
| `keep` | Fixed-ratio games (consoles) | Letterboxes to preserve design ratio |
| `keep_width` | Portrait apps where you control top/bottom | Locks width; vertical content extends |
| `keep_height` | Landscape with controlled left/right | Locks height; horizontal content extends |
| **`expand`** | **Most mobile UIs** | Locks the shorter axis; long axis extends, your anchored layouts (e.g., bottom nav) reanchor naturally |

For a portrait mobile UI with bottom-anchored nav bar: **`expand`**.

### Required block in `project.godot`

```ini
[display]
window/size/viewport_width=420
window/size/viewport_height=760
window/handheld/orientation=1      ; portrait
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"
window/stretch/scale_mode="fractional"  ; default; lets non-integer scales (e.g. 2.57x) be smooth
```

### Diagnostic: "UI too small in real device"

99% of the time: `window/stretch/mode` is missing or `disabled`. `grep stretch project.godot` first. If empty, that's it.

If it's set but still wrong: check viewport_width/height matches your design baseline (a 1920×1080 viewport on a 1080×2400 phone is going to letterbox heavily — pick a viewport that matches the device aspect or live with letterboxing).

If `stretch/mode = canvas_items` is set and UI **still** looks tiny on a Retina laptop / 4K monitor, you're hitting a different problem — see the next section.

## 1b — `content_scale_factor` on Retina / HiDPI displays (desktop apps)

**Stretch mode and content_scale_factor are orthogonal.** stretch_mode handles design-viewport → window mapping. content_scale_factor handles design-density → pixel-density. A desktop creative tool needs **both** dialed in.

### The Godot 4 gotcha

Godot 4 leaves `window.content_scale_factor = 1.0` by default, including on macOS Retina / Linux Wayland HiDPI / Windows scaled-DPI. The Retina **backing buffer** is 2× (so a 1600×900 window has a 3200×1800 framebuffer), but UI elements still render at 1× design density inside that 2× buffer — they look ~half the expected physical size.

The OS *knows* the right scale. Godot just doesn't apply it. **You have to apply it explicitly per window.**

### The common wrong fix

Hard-coding `content_scale_factor = 1.0` on macOS because "Godot already applies Retina." It doesn't — that conflates the backing scale with the content scale. If you find a function in your codebase that says

```gdscript
if OS.get_name() == "macOS":
    return 1.0    # macOS already applies Retina backing scale
```

— that's the bug. Delete it. macOS needs the SAME explicit `content_scale_factor` assignment as everywhere else.

### The Paragraphic-style RetinaManager pattern

A pure-function autoload that reads the OS-reported scale and applies it to a window, compensating window size so the physical pixel footprint stays stable across scale changes. Faithful Godot 4 port:

```gdscript
# scripts/system/retina_manager.gd  (register as autoload "RetinaManager")
extends Node

func retina_scale_for_screen(screen: int) -> float :
    var s: float = 1.0
    var os_name: String = OS.get_name()
    if os_name == "macOS" or (os_name == "Linux" and DisplayServer.get_name() == "Wayland") :
        s = DisplayServer.screen_get_scale(screen)
        if DisplayServer.get_screen_count() > 1 :
            s = DisplayServer.screen_get_max_scale()   # don't shrink when dragged to retina
    elif os_name == "Windows" :
        var dpi: int = DisplayServer.screen_get_dpi(screen)
        if dpi > 119 : s = 1.25
        if dpi > 130 : s = 1.5
        if dpi > 160 : s = 1.75
        if dpi > 180 : s = 2.0
    return max(s, 1.0)

func update_window_retina_mode(window: Window, move: bool = true, resize: bool = true) -> void :
    if window == null : return
    var target: float = retina_scale_for_screen(window.current_screen)
    if is_equal_approx(window.content_scale_factor, target) : return
    var relative: float = target / window.content_scale_factor
    window.content_scale_factor = target
    if resize :
        var new_size: Vector2i = Vector2i(window.size.x * relative, window.size.y * relative)
        if move :
            var center: Vector2i = window.position + window.size / 2
            window.size = new_size
            window.position = center - new_size / 2
        else :
            window.size = new_size

func _ready() -> void :
    # Popups inherit the right scale when added
    get_tree().node_added.connect(_on_node_added)

func _on_node_added(node: Node) -> void :
    if node is Popup and node.get_children().size() == 1 :
        update_window_retina_mode.call_deferred(node, false)
```

### Required wiring at the main window

```gdscript
# In your main scene's _ready():
var win: Window = get_window()
RetinaManager.update_window_retina_mode(win, false)     # initial apply
win.dpi_changed.connect(func(): RetinaManager.update_window_retina_mode(win))  # screen-move
```

`window.dpi_changed` fires when the window moves between displays with different scales — re-apply so UI doesn't grow/shrink mid-session.

### Trap: don't auto-apply RetinaManager to embedded Popups

Paragraphic's PGRetinaManager has a `SceneTree.node_added` hook that auto-applies retina scale to every new Popup. **That only works if your project sets `window/subwindows/embed_subwindows = false`** — Paragraphic does this, every popup is a native OS window with its own content_scale_factor, so an explicit `update_window_retina_mode(popup, false)` is necessary.

Godot 4's **default** is `embed_subwindows = true`. Embedded popups already inherit scaling from the parent window's viewport. Applying RetinaManager to them DOUBLE-scales: content min_size is computed against the popup's own 2× factor on top of the parent's 2×, and the popup balloons to ~4× expected size (text huge, buttons huge, no padding because content overflows the panel).

**Decision rule:**

| `embed_subwindows` | Include popup `node_added` handler? |
|---|---|
| `false` (Paragraphic / native popups) | **Yes** — port the handler |
| `true` (Godot 4 default) | **No** — drop the popup branch; embedded popups inherit automatically |

If you copy PGRetinaManager verbatim into a project with default embed mode, the connection popovers / context menus / dropdowns will look 2× too big. Symptom: popup occupies a third of the screen for a 3-button menu.

### project.godot

```ini
[display]
window/stretch/aspect="ignore"          ; let RetinaManager own scaling; don't compete
```

Don't combine `stretch/mode = canvas_items` with `content_scale_factor` writes from RetinaManager — pick one path. For desktop creative tools the RetinaManager path is right; `canvas_items` is for mobile / responsive web-style apps.

### Why "the OS is ground truth, not a user setting"

Paragraphic ships no UI for "Pick your UI scale 1.0 / 1.5 / 2.0." The OS already lets the user pick HiDPI behavior in System Settings; the app just obeys. Two reasons:

1. **Most users don't know what `content_scale_factor` means.** Exposing it triggers fiddling and "why is my UI weird" support load.
2. **It's already a per-screen OS preference.** A user with a Retina built-in screen + a non-Retina external monitor wants different scales on each — and `screen_get_scale(idx)` per-screen + `dpi_changed` signal solves it for free.

That said, **a manual override is fine to ship** for power users who want a non-OS value (e.g., 1.8 on a 2.0 Retina because they like denser UI). Pattern: keep `UserSettings.ui_scale_mode ∈ {auto, manual}` with `auto` = RetinaManager, `manual` = a user-chosen float. Don't make `manual` the default — too many users will inherit a stale 1.0 and never discover they're on a Retina that wants 2.0.

### Diagnostic: "UI is tiny on my Retina Mac / 4K Windows"

In order:
1. `get_tree().root.content_scale_factor` — if 1.0, that's the bug. Add RetinaManager.
2. Inspect any `_auto_dpi_base()` / `compute_scale()` style helper — does it short-circuit to 1.0 on macOS? Delete the short-circuit.
3. Window size compensation missing → UI is the right density but window appears half-size. Multiply `window.size` by `relative_scale` when applying.
4. Stretch mode is `canvas_items` AND you also write `content_scale_factor` — they fight. Pick one (`stretch/aspect = "ignore"` for desktop).

## 2 — Theme variation taxonomy

`godot-ui-tscn` mandates "use a project Theme + `theme_type_variation` on nodes." This section names *which* variations to create — a portable taxonomy that covers ~95% of admin / dashboard / form UIs.

This taxonomy is the **prototype "find the feel" instrument** — its whole value is dressing an entire UI at once, from generic assets, before any bespoke art exists, so a designer or planner can iterate on feel in the editor. As real art lands, hero elements graduate out of these variations into art-driven controls (see `godot-ui-tscn` → `references/styling.md`, "Two phases"); the taxonomy thins to the long tail but rarely disappears. Build it Theme-first regardless of how art-heavy the final game is.

### Labels (typography hierarchy)

| Variation | Size | Weight | Use |
|---|---|---|---|
| `TitleLabel` | 22 | 700 | App/page title in header |
| `HeadingLabel` | 18–19 | 700 | Section heading, modal title |
| `SubheadingLabel` | 16–17 | 700 | Card title, list-row primary text |
| `(default Label)` | 14–15 | 500 | Body, input text |
| `MutedLabel` | 13 | 400 | Secondary metadata (location/category) |
| `AccentLabel` | 13 | 500 | Inline highlight (status text, role badges) |
| `DangerLabel` | 13 | 500 | Inline error / overdue indicator |
| `TinyLabel` | 11 | 400 | Tertiary text (raw IDs, timestamps) |

### Buttons (action hierarchy)

| Variation | Filled? | Use |
|---|---|---|
| `PrimaryButton` | Filled brand color | The one main action per screen |
| `SuccessButton` | Filled green | Positive irreversible (confirm submit) |
| `DangerButton` | Filled red | Destructive (delete) — but see "Safe-delete pattern" below |
| `GhostButton` | Outlined / text-only brand color | Secondary action; cancel; "more" |
| `(default Button)` | Light grey neutral | Use sparingly; prefer Ghost or Primary |

### Surfaces & badges

| Variation | Base type | Use |
|---|---|---|
| `Card` | PanelContainer | List item / form group container with subtle shadow |
| `AppHeader` | PanelContainer | Top app bar (white bg, bottom border) |
| `BottomBar` | PanelContainer | Sticky footer / bottom nav |
| `Toast` | PanelContainer | Dark pill at screen bottom for transient feedback |
| `BadgeAvailable` | Label | Pill: green tint / green text |
| `BadgeBorrowed` | Label | Pill: amber tint / amber text |
| `BadgeMaintenance` | Label | Pill: red tint / red text (overdue / fault) |
| `BadgeRetired` / `BadgeLabel` | Label | Pill: neutral grey |

### Safe-delete pattern

Don't make destructive actions equal-weight to constructive ones in the same row. In a detail/edit overlay:
- `保存` = PrimaryButton (filled brand)
- `取消` = GhostButton
- `删除` = GhostButton in a separate "危险操作" section (visually quieter)
- On first tap of 删除: morph text to "再次点击以确认删除" + swap to DangerButton variation for 3 s
- On second tap within 3 s: fire the delete

This requires a `DangerButton` variation, but the *default state* of a delete should be ghost — not red.

### Why semantic names, not utility names

`PrimaryButton` survives a brand refresh (re-color the stylebox). `BlueButton` doesn't. Same logic for `DangerLabel` vs `RedLabel`. Variation names describe *intent*, the stylebox describes *appearance*.

## 3 — Variable fonts: the FourCC gotcha

Godot 4's `FontVariation` lets you reuse one variable font file (e.g. NotoSansSC-VariableFont_wght.ttf) at multiple weights by overriding `variation_opentype`. **The dictionary key must be the OpenType tag encoded as a 32-bit integer (FourCC), NOT the 4-character string.**

The official docs sometimes show string-key examples; in `.tres` serialization the string form is silently ignored — the font renders at default weight with no error, no warning, no log line.

### The right form

`wght` (weight) as FourCC = `(0x77 << 24) | (0x67 << 16) | (0x68 << 8) | 0x74` = `2003265652` = `0x77676874`.

```ini
[sub_resource type="FontVariation" id="FV_w700"]
base_font = ExtResource("1_font_cjk")
variation_opentype = {
2003265652: 700.0
}
```

Apply via theme variation:

```ini
TitleLabel/fonts/font = SubResource("FV_w700")
```

### Quick reference: common OT axis FourCCs

| Axis | String | Integer |
|---|---|---|
| Weight | `wght` | `2003265652` (0x77676874) |
| Width | `wdth` | `2003072104` (0x77647468) |
| Italic | `ital` | `1769234796` (0x6974616c) |
| Slant | `slnt` | `1936486004` (0x736c6e74) |
| Optical size | `opsz` | `1869640058` (0x6f70737a) |

Compute any tag:

```python
tag = 'wght'
fourcc = (ord(tag[0])<<24) | (ord(tag[1])<<16) | (ord(tag[2])<<8) | ord(tag[3])
print(fourcc)
```

Or at runtime in Godot: `TextServerManager.get_primary_interface().name_to_tag("wght")`.

### Diagnostic: "I set FontVariation but everything looks the same weight"

In order of likelihood:
1. **Wrong key type** — string `"wght"` instead of integer `2003265652`. Open `Theme_main.tres` and inspect `variation_opentype` — if the key is in quotes, that's the bug.
2. The font file isn't actually variable — check it has an `fvar` table (`python3 -c "print(b'fvar' in open(path,'rb').read(5000))"`).
3. CJK glyphs intrinsically have less visible weight contrast at small sizes (~13 px). Bump primary text from 16 → 17 px AND from weight 600 → 700 if you want unambiguous contrast.
4. You set `Label/fonts/font` globally and forgot — that overrides every variation. Remove the global, keep only `TitleLabel/fonts/font` etc.

### Base-font weight choice

If "底部 tab 字太细": likely the BottomTab variation uses default font (no override). Either give BottomTab its own `fonts/font = SubResource("FV_w500")`, or — simpler — change the resource-level default:

```ini
[resource]
default_font = SubResource("FV_w500")    ; was: ExtResource("1_font_cjk")
default_font_size = 15
```

This bumps everything-not-overridden from weight 400 → 500. CJK reads noticeably more solid at 500; titles still feel heavier because they're at 700.

## 4 — Minimum smell-test before authoring scenes

Before opening Main.tscn:

- [ ] `grep stretch project.godot` returns a `canvas_items` line (mobile/responsive) OR `stretch/aspect="ignore"` (desktop tool with RetinaManager)
- [ ] **For desktop tools**: RetinaManager autoload registered, `update_window_retina_mode` wired in main scene `_ready` + `window.dpi_changed` listener; no hardcoded `if OS == "macOS" return 1.0` short-circuit anywhere
- [ ] Theme.tres has at least: PrimaryButton, GhostButton, MutedLabel, SubheadingLabel
- [ ] Any FontVariation sub-resource uses integer keys in `variation_opentype`
- [ ] `default_font` in the theme [resource] block is set (either to ExtResource or to a FontVariation if you want a 500-weight default)

If any of these fail, fix here before writing scenes — every scene built against the wrong foundation will need touching up later.

## Validation

Author one screen with at least 3 different label variations + 2 button variations, run on the target device, and confirm:
- UI fills the screen (no top-left letterboxing) → stretch works
- Heading vs body have visibly different weight → variable font tags work
- Primary action and destructive action are visually distinct → variation taxonomy is doing its job

If any of those visually fail, run the diagnostics in the relevant section above before touching scene code.
