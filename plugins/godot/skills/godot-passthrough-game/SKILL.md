---
name: godot-passthrough-game
author:cnzangtianpei@gmail.com
description: >-
  Guidance for building and debugging Godot 4 transparent desktop-widget games —
  "passthrough games" such as desktop pets, idle widgets, and screen-edge
  companions whose window is transparent and lets clicks fall through to the
  desktop where there is no game content. Use this whenever working on a Godot
  project that has a transparent, borderless, or always-on-top window, is a
  desktop pet / widget / overlay, or implements mouse click-through / passthrough
  — and especially when debugging its signature failure modes: clicks not
  registering, the whole window swallowing or passing every click through (often
  Windows-only), or a transparent window rendering as a solid black rectangle. It
  also covers the platform traps these projects always hit — DPI scaling, CJK
  text wrapping, window and addon setup. Consult it before writing or changing
  any transparent-window, click-through, or passthrough code in Godot: the
  engine's built-in passthrough is broken on Windows and the failure modes are
  non-obvious and platform-specific.
---

# Building Godot Passthrough Games

A **passthrough game** is a Godot 4 game that runs as a transparent window living
on the user's desktop — a desktop pet, an idle widget, a screen-edge companion
(think *Rusty's Retirement*, Tamagotchi-style desktop pets, 动物栏 / TinyPasture).
There is no opaque window background: the game art sits directly on the desktop,
and the mouse must land on the game where there is content but **pass through to
the desktop** (and other apps) everywhere the window is transparent.

That "pass through where empty" requirement is the defining hard problem of the
genre, and Godot 4 makes it deceptively painful: the engine's built-in
passthrough is broken on Windows, and a handful of platform gotchas (DPI, CJK
text, C# addons) bite every project. This skill captures what actually works so
you don't rediscover it the hard way — most of the cost here is Windows-only
debugging that a macOS/Linux developer cannot see.

## When to use this

Apply this guidance whenever a Godot 4 project:

- runs as a transparent / borderless / always-on-top window;
- is a desktop pet, widget, overlay, or screen-edge game;
- needs mouse clicks to pass through to the desktop or other apps;
- shows symptoms: clicks not registering (often Windows-only), the whole window
  swallowing or passing through every click, the game rendering tiny on a scaled
  Windows display, or text overflowing its container.

Read the relevant `references/` file before writing or changing code in these
areas. The failure modes are non-obvious and platform-specific, and guessing
burns a lot of time.

## The cardinal rule: don't trust Godot's built-in passthrough on Windows

Godot 4 offers `Window.mouse_passthrough_polygon` and
`DisplayServer.window_set_mouse_passthrough()`. **On Windows these are
unreliable.** They are implemented with `SetWindowRgn`, which conflicts with the
per-pixel-transparent layered window and breaks mouse input outright: clicks
either vanish entirely or the whole window becomes click-through, opaque UI
included. They do work on macOS and Linux/X11.

The approach that works on Windows is the Win32 `WS_EX_TRANSPARENT` window-style
toggle, flipped each frame by polling the cursor. **Before writing or debugging
any passthrough code, read `references/mouse-passthrough.md`** — it has the full
platform model and a drop-in implementation.

## Decide the window shape first

How hard passthrough is depends entirely on the window's shape. Choose one
deliberately, up front:

| Window shape | Passthrough needed? | Notes |
|---|---|---|
| **Content-sized, moving** | None | The window is exactly the pet's bounding box and moves around the desktop — the window *is* the pet. Simplest: there is no transparent dead zone to pass through. |
| **Filled strip / panel** | None | A fixed window region fully covered by opaque game art (e.g. a scene strip along the bottom of the screen). No transparent interior → nothing to pass through. |
| **Large transparent window** | Yes — the hard case | The window covers a big area; the content is a small part of it. This genuinely needs working passthrough. Pick it only when the design truly requires a large interactive surface. |

Most desktop pets succeed by *avoiding* the hard case — a content-sized moving
window, or a filled strip. Reach for the large-transparent-window design only
when the gameplay needs a big interactive surface, and then use the Win32
approach from the start rather than discovering Godot's built-in passthrough
fails after shipping.

→ `references/window-and-scaling.md` — window flags, sizing strategies, and
DPI-correct content scaling.

## Platform gotchas that bite every project

Skim `references/gotchas.md`. The headline ones:

- **The transparent window renders as a solid black rectangle.** Two unrelated
  Windows causes: running on the discrete GPU of a hybrid-GPU laptop, or sizing
  the window exactly to the screen. Both are engine bugs with code-side
  workarounds — see `references/gotchas.md`.
- **Scaling is wrong on Windows.** `DisplayServer.ScreenGetScale()` always
  returns `1.0` on Windows and ignores the system display-scaling setting —
  derive the real factor from `DisplayServer.ScreenGetDpi()` instead.
- **CJK text overflows.** A `Label` with `autowrap_mode = Word` never wraps
  Chinese / Japanese (no spaces between characters) — use `WordSmart`.
- **C# addons fail on a fresh clone** until the assembly is built — Godot reports
  "Unable to load addon script". Not a code error; a build-order issue.
- **Separate sub-windows hide behind a full-screen always-on-top main window**
  unless the sub-windows are also always-on-top.

## Testing

Mouse passthrough only behaves correctly on a **real exported build**. The Godot
editor's Play session commonly skips or mis-handles it (and is often guarded off
in code on purpose). When verifying passthrough or click-through, always test an
exported build on the target OS — Windows behavior in particular cannot be
trusted from a macOS or Linux editor run.

## Reference files

- `references/mouse-passthrough.md` — the platform model, why Godot's built-in
  fails on Windows, and a complete working Win32 implementation. Read this before
  any passthrough work.
- `references/window-and-scaling.md` — window flags, transparency setup,
  always-on-top, and DPI-correct scaling.
- `references/gotchas.md` — CJK autowrap, C# addon load failures, low-power mode,
  the macOS focus quirk, and testing notes.
