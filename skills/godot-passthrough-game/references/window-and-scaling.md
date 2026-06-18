# Window setup and scaling

How to configure a Godot 4 window so it behaves as a transparent desktop widget,
and how to scale its content correctly across platforms.

## Project settings (`project.godot`)

A transparent desktop game needs these under `[display]` / `[rendering]`:

```ini
[display]
window/size/borderless=true
window/size/transparent=true
window/per_pixel_transparency/allowed=true
window/subwindows/embed_subwindows=false   ; sub-windows = real OS windows

[rendering]
viewport/transparent_background=true
```

`embed_subwindows=false` matters: any `Window` node you create at runtime becomes
a real, independent OS window rather than being drawn inside the main viewport.
That is what you want for popups / dialogs — but see the always-on-top rule in
`mouse-passthrough.md` §7.

## Window flags at runtime

Set these on `GetWindow()` in `_Ready()` (after computing size/position):

- `Borderless` — no title bar / frame.
- `AlwaysOnTop` — the widget floats above normal windows.
- Size + Position — see "Sizing strategies" below.

### always-on-top: set it the simple way

To toggle always-on-top at runtime, just assign the `Window` property:

```csharp
GetWindow().AlwaysOnTop = on;
```

`Window.AlwaysOnTop` already forwards to the display server internally. **Do not**
also call `DisplayServer.WindowSetFlag(WindowFlags.AlwaysOnTop, ...)` — the extra
call has been tried as a fix for "can't turn always-on-top off" and does not
help; it only adds confusion. One assignment is the whole job.

## DPI-correct content scaling

The widget should render at the same visual size as native apps. Godot does
**not** auto-apply the OS display scale — you multiply it into
`Window.ContentScaleFactor` yourself.

The trap: `DisplayServer.ScreenGetScale()` is **not** consistent across
platforms.

| Platform | `ScreenGetScale()` returns | Use for the scale factor |
|---|---|---|
| macOS | the real backing scale (`2.0` on retina) | `ScreenGetScale()` |
| Windows | **always `1.0`** — ignores the system display-scaling setting | `ScreenGetDpi() / 96.0` |
| Linux | usually `1.0` | `ScreenGetScale()`, fall back to DPI if needed |

On Windows, a user at 150% display scaling still gets `ScreenGetScale() == 1.0`,
so a naive `ContentScaleFactor = ScreenGetScale()` renders the whole game at
about two-thirds size. Derive the real factor from DPI instead — 96 dpi = 100%,
144 = 150%, 192 = 200%:

```csharp
int screen = DisplayServer.GetPrimaryScreen();
float screenScale = DisplayServer.ScreenGetScale(screen);
if (screenScale < 1.0f) screenScale = 1.0f;
if (OS.GetName() == "Windows")
{
    int dpi = DisplayServer.ScreenGetDpi(screen);
    if (dpi > 0) screenScale = dpi / 96.0f;
}
// optionally fold in a user-facing UI-scale slider:
float effectiveZoom = screenScale * userUiScale;
GetWindow().ContentScaleFactor = effectiveZoom;
```

Note: a 4K monitor at Windows 100% scaling reports 96 dpi → factor `1.0` → the
game is small, but so is every other app — that is "honor the system setting"
working correctly. If you want it bigger anyway, expose a separate user-facing
UI-scale knob; don't fight the system DPI.

## Sizing strategies

Pick the window shape deliberately (see SKILL.md for the trade-off table):

- **Content-sized, moving** — `Window.Size` = the pet's bounding box; move the
  `Window.Position` around the desktop so the pet "walks". The camera follows
  the window position. No transparent dead zone → no passthrough needed.

- **Filled strip / panel** — a fixed window region (e.g. full screen width ×
  a short height, docked to the bottom of the usable area) fully covered by
  opaque game art. No transparent interior → no passthrough needed.

- **Large transparent window** — `Window.Size` covers a big area; content is a
  small fraction of it. Needs the passthrough from `mouse-passthrough.md`.

For docked windows, size and place against the **usable** rect
(`DisplayServer.ScreenGetUsableRect`) so the widget sits above the taskbar /
menu bar rather than under it.

## Sub-windows inherit nothing

A `Window` you `new` at runtime does not inherit the main window's transparency,
always-on-top, or content scale. If a popup must scale with the rest of the game,
set its `ContentScaleFactor` (and size it accordingly) explicitly. If it must be
clickable above a full-screen always-on-top main window, set its `AlwaysOnTop`
explicitly — see `mouse-passthrough.md` §7.
