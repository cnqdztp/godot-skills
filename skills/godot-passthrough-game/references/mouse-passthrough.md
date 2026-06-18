# Mouse passthrough in Godot 4 desktop games

A transparent desktop game must route every click two ways: **hit the game**
where it draws content, **pass through to the desktop / other apps** where the
window is transparent. This file explains why that is hard in Godot 4, and gives
a working implementation.

## Contents

1. The platform model — three OSes, three behaviors
2. Why Godot's built-in passthrough breaks on Windows
3. The reliable approach: a per-frame `WS_EX_TRANSPARENT` toggle
4. Drop-in implementation (provider pattern)
5. Wiring it into the main scene
6. Two cursor-poll gotchas that will bite you
7. Sub-windows under a full-screen always-on-top window
8. The CXProject addon (a ready-made version)

## 1. The platform model

| Platform | Free per-pixel alpha hit-testing | Godot polygon passthrough |
|---|---|---|
| Windows  | the OS layered window has it, but Godot does not reliably expose it | **broken** — `SetWindowRgn` fights the layered window |
| macOS    | no | works |
| Linux X11 | no | works |

Godot's `Window.mouse_passthrough_polygon` takes a polygon: inside the polygon
the window receives clicks, outside it the clicks pass through. Conceptually
fine, and it genuinely works on macOS and Linux.

## 2. Why it breaks on Windows

A per-pixel-transparent Godot window on Windows is a **layered window**
(`WS_EX_LAYERED`). Godot implements the passthrough polygon on Windows with
`SetWindowRgn` (a window region). `SetWindowRgn` does not coexist well with a
layered window — the combination breaks mouse input. Observed failure modes:

- A non-empty polygon → the *whole* window passes clicks through, opaque UI
  included (clicks land on the desktop everywhere).
- An empty polygon → the whole window is dead (nothing is clickable).

This is not a code mistake in your game; it is the engine's Windows
implementation. Multiple shipped desktop-pet games and a community addon exist
specifically to work around it. Do not spend time tuning the polygon on
Windows — it cannot be made reliable.

## 3. The reliable approach: a per-frame WS_EX_TRANSPARENT toggle

On Windows the correct primitive is the `WS_EX_TRANSPARENT` extended window
style. A window with `WS_EX_LAYERED | WS_EX_TRANSPARENT` passes **all** mouse
input through to whatever is beneath it; remove `WS_EX_TRANSPARENT` and it
captures everything. It is a whole-window, binary switch — there is no "region".

So passthrough becomes a per-frame decision:

> Each frame, work out whether the cursor is currently over something the player
> should be able to click. If yes, remove `WS_EX_TRANSPARENT` (window captures).
> If no, add it (clicks fall through to the desktop).

The one-frame latency between the cursor crossing a content boundary and the
toggle flipping is imperceptible at 30–60 fps. This "cursor-poll + binary
toggle" is the model the whole genre uses.

macOS and Linux can use the *same* binary model through
`MousePassthroughPolygon`: a tiny degenerate polygon means "pass everything
through", `null` means "capture everything". Driving both platforms with one
binary `SetClickthrough(bool)` keeps the integration uniform.

## 4. Drop-in implementation (provider pattern)

A small platform-split behind one interface. `WindowsPassthroughProvider` is
guarded with `#if GODOT_WINDOWS` so it only compiles into Windows builds.

```csharp
// One interface, two implementations.
public interface IPassthroughProvider
{
    void Initialize(Window window);
    // true  = window passes all clicks through to the desktop
    // false = window captures clicks
    void SetClickthrough(bool clickthrough);
}
```

```csharp
#if GODOT_WINDOWS
using Godot;
using System.Runtime.InteropServices;

// Windows: toggle the WS_EX_TRANSPARENT extended window style via Win32.
public sealed class WindowsPassthroughProvider : IPassthroughProvider
{
    const int  GWL_EXSTYLE      = -20;
    const uint WS_EX_LAYERED    = 0x00080000;
    const uint WS_EX_TRANSPARENT= 0x00000020;

    [DllImport("user32.dll")] static extern int GetWindowLong(nint hWnd, int idx);
    [DllImport("user32.dll")] static extern int SetWindowLong(nint hWnd, int idx, uint val);

    nint _hWnd;

    public void Initialize(Window w)
    {
        _hWnd = (nint)DisplayServer.WindowGetNativeHandle(
            DisplayServer.HandleType.WindowHandle, w.GetWindowId());
        SetClickthrough(false);          // start solid
    }

    public void SetClickthrough(bool clickthrough)
    {
        if (_hWnd == 0) return;
        uint style = (uint)GetWindowLong(_hWnd, GWL_EXSTYLE) | WS_EX_LAYERED;
        style = clickthrough ? style |  WS_EX_TRANSPARENT
                             : style & ~WS_EX_TRANSPARENT;
        SetWindowLong(_hWnd, GWL_EXSTYLE, style);
    }
}
#endif
```

```csharp
using Godot;

// macOS / Linux: the polygon API works here. Use it as a binary toggle —
// a degenerate (zero-area) polygon passes everything through; null captures.
public sealed class DefaultPassthroughProvider : IPassthroughProvider
{
    static readonly Vector2[] PassEverything = { new(0,0), new(0,0), new(0,0) };
    Window _w;
    public void Initialize(Window w) => _w = w;
    public void SetClickthrough(bool clickthrough)
        => _w.MousePassthroughPolygon = clickthrough ? PassEverything : null;
}
```

## 5. Wiring it into the main scene

```csharp
private IPassthroughProvider _passthrough;
private bool? _lastClickthrough;          // diff: only call on a real change

private void InitPassthrough()
{
    // Wayland / Web genuinely don't support this — leave _passthrough null.
    if (OS.HasFeature("web") || OS.HasFeature("wayland")) return;
#if GODOT_WINDOWS
    _passthrough = new WindowsPassthroughProvider();
#else
    _passthrough = new DefaultPassthroughProvider();
#endif
    _passthrough.Initialize(GetWindow());
}

public override void _Process(double delta)
{
    if (_passthrough == null) return;

    bool clickthrough = !CursorOverContent();
    if (_lastClickthrough == clickthrough) return;   // skip redundant Win32 calls
    _lastClickthrough = clickthrough;
    _passthrough.SetClickthrough(clickthrough);
}

// Your hit test. Return true when the cursor is over something clickable —
// the pet sprite, a HUD panel, an open in-window modal, etc. Build it from
// whatever your game already knows: bounding rects, a hit-test registry, the
// solid region of a docked panel.
private bool CursorOverContent()
{
    Vector2I m = DisplayServer.MouseGetPosition() - GetWindow().Position;
    // ... compare m against your content rects (window-local physical pixels)
}
```

Call `InitPassthrough()` once in `_Ready()` (after the window is sized). The
per-frame `_Process` poll then handles every state — including modals: when a
modal/overlay is open, just make `CursorOverContent()` return `true`
unconditionally so the window captures everything.

## 6. Two cursor-poll gotchas that will bite you

**Use `DisplayServer.MouseGetPosition()`, not `GetViewport().GetMousePosition()`.**
Once the window is click-through (`WS_EX_TRANSPARENT`), it stops receiving
mouse-move events — so `GetViewport().GetMousePosition()` freezes at its last
value and the window can get **stuck transparent forever** (it never detects the
cursor returning over content). `DisplayServer.MouseGetPosition()` is a global OS
poll, always fresh. Subtract `GetWindow().Position` to get window-local physical
pixels; compare against content rects in the same physical-pixel space.

**Pick the modal behavior on purpose.** When a separate window or a full-screen
in-window modal opens, decide whether the main window should capture everything
(block click-through) or step fully aside. Don't leave it implicit.

## 7. Sub-windows under a full-screen always-on-top window

If the main window is full-screen + always-on-top, any separate `Window` you open
with `AlwaysOnTop = false` renders **behind** the main window and is unclickable —
the main window covers it. This is a common "my dialog/shop/intro can't be
clicked" bug.

Fix: give sub-windows `AlwaysOnTop = true` so they sit **above** the main window
and receive input directly. This is robust because it does not depend on the
main window's passthrough state at all. (Making the main window go click-through
while a sub-window is open also works, but it is more fragile.)

## 8. The CXProject addon (ready-made)

`godot-mousePassThrough` — Godot Asset Library #5154, "Mouse Passthrough
Manager", MIT, Godot 4.6 .NET — implements exactly the pattern above:
`WindowsPassthroughProvider` (Win32) + `DefaultPassthroughProvider` behind an
`IPassthroughProvider`, plus an optional `PassthroughManager` autoload with a
QuadTree of clickable shapes.

If you vendor it into `addons/`:

- You can use the provider classes directly (as in §4–5) and ignore the
  `PassthroughManager`/QuadTree layer — that layer is only worth it if you want
  shape-node registration instead of your own hit test.
- **Delete its `plugin.cfg` and the empty `pass_through.cs` EditorPlugin stub.**
  They serve no purpose for you (the runtime classes compile via the project's
  `addons/` glob) and the C# `[Tool]` stub triggers a fresh-clone load error —
  see `gotchas.md`.

## Verifying

`WS_EX_TRANSPARENT` and `MousePassthroughPolygon` only behave on a real OS
window. Editor Play sessions are commonly guarded off (`OS.HasFeature("editor")`)
and embedded-game mode has no real window handle. Always verify passthrough on an
**exported build**, on the actual target OS.
