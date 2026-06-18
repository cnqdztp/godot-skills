---
name: godot-mobile-web
metadata:
  author: cnzangtianpei@gmail.com
description: >-
  GDScript conventions and gotchas for shipping a Godot 4 2D game to Web (HTML5)
  and mobile — especially a portrait-locked character / desktop-pet app. Covers
  web-export traps that bite only after deploy (audio won't autoplay until a user
  gesture; the on-screen keyboard needs an export flag; real streaming needs
  JavaScriptBridge fetch, not HTTPRequest); a landscape screen inside a
  portrait-locked viewport (rotate the subtree, don't gate on aspect ratio);
  scene-transition discipline (cover→hold→reveal); cel-style 2D rendering
  (seamless scroll via one wrapped quad + texture_repeat; shadow grounded at the
  sprite's opaque-pixel feet); GDScript coroutine fire-and-forget to overlap a
  download with an animation; and downloadable character/asset packs (res:// vs
  user://). Use when a Godot 4 GDScript project targets web or mobile, is
  portrait-locked, or is a 2D pet/widget, or shows symptoms like silent audio, an
  un-typeable field on mobile web, a background seam, or a shadow off the pet.
---

# Godot 4 — GDScript for Web & Mobile (portrait pets)

Field notes for a **GDScript** Godot 4 game that exports to **Web (HTML5)** and
**mobile**, typically a **portrait-locked 2D character / desktop-pet** app. These
are the things that pass every desktop test and then break only on the deployed
web/phone build, plus the rendering and async patterns that the genre keeps
needing. This complements the C#-leaning Godot skills (`godot-quirks`,
`godot-ui-tscn`, `godot-ui-foundation`, `godot-automatic-ui-qa`); read those for
engine quirks, UI-as-`.tscn`, viewport/DPI, and the headless screenshot loop.

## When to use this

- The project has a **Web export** target, or runs on a phone.
- `project.godot` has `window/handheld/orientation` set (portrait-locked).
- It's a **2D pet / widget / character** app with a scrolling backdrop, a walking
  sprite, idle "breathing", or a downloadable-character/gacha system.
- Symptoms on web/mobile: **no sound**, a **text field you can't type into** on
  mobile web, a **seam** in the panning background, a **shadow detached** from the
  character, or an **animation/transition that gets skipped** behind a network
  call.

Treat each section below as a checklist before writing code in that area — every
item here cost real deploy-debug time.

---

## 1. Web (HTML5) export traps

These do not reproduce on desktop. Test them on the actual web build.

- **Audio will not autoplay until a real user gesture.** Browsers keep the audio
  context suspended until the page receives a click/tap/key. `AudioStreamPlayer.play()`
  *succeeds* in Godot's view, but nothing is heard. So **start BGM/SFX on the first
  genuine user gesture** — the "tap to enter" button handler — not on `_ready`, not
  when auth/network resolves. Symptom: music is silent on web, fine on desktop.

- **`LineEdit`/`TextEdit` have no on-screen keyboard on mobile web unless you opt
  in.** Set `html/experimental_virtual_keyboard=true` in the **Web export preset**.
  Then call `grab_focus()` **synchronously inside the tap gesture** that opens the
  field (a deferred/async focus won't raise the keyboard), and read
  `DisplayServer.virtual_keyboard_get_height()` to lift the field above it. With the
  flag off, the field focuses but the user simply cannot type. Symptom: can't reply
  / can't enter text on a phone, works with a hardware keyboard.

- **`export_presets.cfg` is usually git-ignored.** That means the two settings
  above (and the whole Web preset) silently revert on a fresh clone / CI. Pin them
  in your deploy/CI config or commit a checked-in copy — don't assume the local file
  persists.

- **`HTTPRequest`/`HTTPClient` don't stream on web.** For true token-by-token
  streaming (LLM chat, SSE), use `JavaScriptBridge` to call the browser `fetch()` and
  read its `ReadableStream`; pump chunks back into GDScript via a JS callback. The
  native HTTP classes buffer the whole response on the HTML5 platform.

- **Branch with `OS.has_feature("web")`** for these paths; keep the desktop path
  unchanged so editor iteration stays fast.

---

## 2. A landscape screen inside a portrait-locked app

When `window/handheld/orientation=1` (portrait) and the viewport is a fixed
portrait size (e.g. 414×896), the device viewport **never** becomes landscape — so
you **cannot** detect "should I show the landscape UI?" from the aspect ratio (that
gate is always false on device).

Instead, **rotate the content subtree 90° to fill the portrait viewport**. A small
`LandscapeStage extends Control` that, on `_ready` and on
`get_viewport().size_changed`, sets:

```gdscript
rotation = PI / 2.0
size = Vector2(vp.y, vp.x)      # swapped: lay out children in landscape space
position = Vector2(vp.x, 0.0)
pivot_offset = Vector2.ZERO
```

Children then use normal anchors/containers inside the stage's local landscape
rect. The player turns the phone (e.g. counter-clockwise) and the content reads
upright. Use the same rotated layout for a "please rotate your phone" prompt — when
held portrait it appears sideways, which *is* the hint. Caveat: native dialogs
(`FileDialog` with `use_native_dialog`) are separate OS windows and are **not**
rotated; they follow the device's real orientation, which is fine.

---

## 3. Scene-transition discipline

- **Never cut straight from scene A to scene B.** Every scene change goes
  cover → hold → reveal: an iris/loading overlay closes over A, *holds a beat with
  the cover fully opaque*, the underlying scene is swapped, then the iris opens on
  B. Route **all** `change_scene_to_*` through one `TransitionManager` so the
  discipline is enforced in a single place.

- **A full-screen, self-contained step is its own scene, not an overlay** on the
  lobby/main scene. (E.g. a daily-draw / gacha-summon flow is a dedicated `.tscn`
  the transition routes to, not a panel floated over the main scene.) This keeps
  input, layering, and lifecycle clean.

---

## 4. Cel-style 2D rendering (background + pet)

- **Seamless horizontal scroll = ONE wrapped quad, not N tiles.** Drawing the
  backdrop as several adjacent `draw_texture_rect` copies produces a faint vertical
  **seam** at every tile boundary: with linear filtering and clamp-to-edge, each
  quad's edge samples its own clamped border instead of wrapping. Fix: enable
  `texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED` on the node and draw a
  **single** rect that the GPU wraps. To scale-to-height *and* tile, apply the scale
  with `draw_set_transform` and draw one tiled rect in texture-native space:

  ```gdscript
  var sc := size.y / tex.get_size().y
  var tile_w := tex.get_size().x * sc
  var off := fposmod(_scroll, tile_w) / sc
  var cols := ceilf(size.x / tile_w) + 1.0
  draw_set_transform(Vector2.ZERO, 0.0, Vector2(sc, sc))
  draw_texture_rect(tex, Rect2(-off, 0.0, cols * tex.get_size().x, tex.get_size().y), true)
  draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
  ```

  Author the image so its left/right columns match (check the edge pixel-diff). One
  draw call, no clamp seam, endless pan.

- **Ground the shadow at the sprite's real feet, not the anchor.** A pack's `anchor`
  (squish/breathing pivot) often sits well above the visual feet and varies with how
  much transparent footroom the art carries — drawing the shadow ellipse at
  `anchor.y` floats it into the body or makes it vanish. Instead measure the opaque
  bottom of the first frame once on load and place the shadow there:

  ```gdscript
  var used := frame_image.get_used_rect()   # opaque-pixel bbox in texture px
  _feet_ratio = Vector2(
      (used.position.x + used.size.x * 0.5) / ts.x,   # centre x
      float(used.position.y + used.size.y) / ts.y)    # bottom y
  # in _draw: place the ellipse at _feet_ratio within the letterboxed display rect.
  ```

  `get_image()` works for both `load()`-ed (`CompressedTexture2D`) and raw
  `ImageTexture` frames. Verify by rendering several packs (see §7) — a shadow bug is
  invisible until you actually look.

- **Idle "breathing" (squish) is pack-driven, pivoted at the feet** — scaleY up /
  scaleX down about the `anchor`, volume-preserving, a no-op when the pack disables
  it. Keep it data-driven so a static pack stays perfectly still.

---

## 5. GDScript async: fire-and-forget to overlap work

A coroutine (a `func` containing `await`) **called WITHOUT `await` runs in the
background**: it executes up to its first internal `await`, yields, and resumes on
its own when that await resolves. Use this to **overlap a network download with an
animation** instead of serializing them (which makes the animation look "skipped"
on slow links — the download ran in front of it):

```gdscript
func _on_summon() -> void:
    _ready_flag = PackManager.has_pack(id)
    if not _ready_flag:
        _download(id)            # NOT awaited → runs concurrently
    await _play_ride()           # cosmetic animation, uses already-bundled assets
    while not _ready_flag:       # join before the part that needs the download
        await get_tree().process_frame
    _reveal()

func _download(id: String) -> void:
    _ok = await PackManager.ensure(id)
    _ready_flag = true
```

Join by polling a flag (or a signal). The cosmetic step should depend only on
already-bundled assets so it can start immediately.

---

## 6. Downloadable character / asset packs

- **Pipeline:** a build script zips each `assets/characters/official_*` into
  `<id>.zip` (manifest `character.json` at the zip root + `sprites/`, raw PNGs, no
  `.import`), uploaded to a server; the client downloads + unzips into `user://` on
  demand. **Ship a tiny avatar thumbnail in the build** for every character so
  locked/undrawn entries still show a face before the heavy pack arrives (and so a
  cosmetic reveal/ride can run before the download — see §5).

- **`user://` shadows `res://`.** Once a pack is downloaded to `user://`, the loader
  prefers it over the bundled copy. Consequence: **the cloud pack IS whatever your
  build script last packaged** — when you change bundled art, you must rebuild AND
  re-upload the zip, or downloaded clients keep the old art. During development,
  stale `user://` packs silently shadow freshly-updated bundled art; clear
  `user://characters/<id>` to test bundled changes. This is a *packaging/sync*
  concern, not a reason to invert the precedence.

---

## 7. Close the visual-QA loop yourself (headless)

- **Smoke-validate every scene:** a `SceneTree` script that walks `src/`, loads and
  instantiates each UI `.tscn`, and prints OK/FAIL catches parse, script-binding, and
  `%UniqueName` errors in seconds. Skip the entry scenes (they boot the whole game);
  cover those with the capture flow below.
  `godot --headless --path . --script tools/validate_scenes.gd`

- **Render real scenes to PNG and look at them.** A capture harness instantiates the
  actual scenes and saves screenshots you (or the agent) read back — far better than
  asking the user for a screenshot. **Caveat: `--headless` does NOT render the
  viewport texture** (`get_viewport().get_texture().get_image()` comes back blank);
  run with a real rendering context (a normal windowed run on macOS/Linux/CI with a
  display). See `godot-automatic-ui-qa` / `godot-capture` for the full loop.

- **Use the project's pinned Godot binary** for validation/QA (e.g. the exact 4.7
  RC), not whatever `godot` is on PATH — engine point releases change behavior.

---

## 8. GDScript house style (cross-references)

- **Animate container children with the 4.7 `offset_transform_*`**, not by tweening
  their `scale`/`position` (a Container stomps those on relayout). See the
  offset-transform entry in `godot-quirks`.
- **Build UI as `.tscn` + a thin script** (GetNode/`%` refs, signal wiring, data
  binding); don't assemble layout with `Control.new()` in code. See `godot-ui-tscn`.
- **Don't invent helper classes for two-line conventions.** If a list is just a
  list (mock rows in the scene, cleared and refilled at runtime by the panel's own
  populate code), keep it a convention — no `MockList.gd`, no new concept name.
