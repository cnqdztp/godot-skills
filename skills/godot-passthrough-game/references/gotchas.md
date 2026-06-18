# Gotchas for Godot 4 passthrough games

Non-obvious failure modes that bite desktop-widget projects. Each is something a
macOS/Linux developer can easily miss until a Windows user reports it.

## A transparent window renders as a solid black rectangle

Symptom: instead of the desktop showing through, the whole window is an opaque
black rectangle. There are **two unrelated causes** on Windows — diagnose which
one you have, because the fixes are completely different. Both are engine-level
bugs Godot has not fixed; the game has to work around them.

### Cause 1 — the game is running on the discrete GPU (hybrid-GPU laptops)

Most Windows laptops have two GPUs (Intel integrated + NVIDIA/AMD discrete —
"NVIDIA Optimus" / AMD switchable). When the game runs on the **discrete** GPU,
its swapchain only reports `VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR` — it cannot
composite the window's alpha with the desktop — so the transparent background
renders opaque black. The integrated GPU can composite; the discrete one cannot.
Godot bug #76167, confirmed and unfixed; it affects both the Vulkan and the
GLES3 (Compatibility) backends. This is the dominant cause of "some users see
black" — single-GPU desktops never hit it.

The documented fix `--gpu-index` **does not work with the GL Compatibility
renderer** (OpenGL offers no GPU selection — Godot #87763). The workaround that
does work on any renderer: pin the executable to the integrated GPU through the
**Windows per-app GPU preference** (the registry behind Settings → Graphics).
It is an OS-level decision made at process start, so it applies to OpenGL too,
and writing it needs no admin rights (`HKCU`). The GPU is bound when the process
starts, so after writing the preference the game must relaunch itself once:

```csharp
// Call as the very first line of _Ready(); if it returns true, return immediately.
private bool TryRelaunchOnIntegratedGpu()
{
    if (OS.GetName() != "Windows" || OS.HasFeature("editor")) return false;
    // The relaunched instance carries this user arg → hard stop, never loop
    // (protects against an infinite relaunch if `reg` ever fails).
    foreach (var a in OS.GetCmdlineUserArgs())
        if (a == "gpu-relaunched") return false;

    string adapter = RenderingServer.GetVideoAdapterName() ?? "";
    bool discrete = adapter.Contains("NVIDIA") || adapter.Contains("GeForce")
                 || adapter.Contains("RTX") || adapter.Contains("GTX")
                 || adapter.Contains("Radeon") || adapter.Contains("AMD");
    if (!discrete) return false;            // already on the iGPU / single-GPU

    string exe = OS.GetExecutablePath();
    const string key = @"HKCU\Software\Microsoft\DirectX\UserGpuPreferences";

    // Preference already written → don't relaunch (a single-discrete-GPU
    // desktop would otherwise relaunch on every startup).
    var q = new Godot.Collections.Array();
    OS.Execute("reg", new string[] { "query", key, "/v", exe }, q);
    foreach (var line in q)
        if (line.ToString().Contains("GpuPreference=1")) return false;

    OS.Execute("reg", new string[] {
        "add", key, "/v", exe, "/t", "REG_SZ", "/d", "GpuPreference=1;", "/f" });
    OS.CreateProcess(exe, new string[] { "--", "gpu-relaunched" });
    GetTree().Quit();
    return true;
}
```

`GpuPreference=1;` = power-saving (integrated) GPU; `2` = high-performance. The
two guards matter: the `gpu-relaunched` user arg is a hard anti-loop stop, and
the `reg query` check stops a single-discrete-GPU desktop from relaunching on
every launch. Caveat: this assumes the per-app preference overrides the
`NvOptimusEnablement` symbol that Godot bakes into exports — true on Windows 10
1803+, but verify on a real hybrid laptop, as you cannot reproduce it elsewhere.

### Cause 2 — the window is sized exactly to the screen

A borderless transparent window whose size is **exactly the display dimensions**
makes Windows apply "fullscreen optimization": it promotes the window to a fast
fullscreen path that **bypasses the DWM compositor** while focused. DWM
compositing is what blends the window's alpha with the desktop — bypass it and
the transparent areas render black. The tell is focus-dependent: black when
focused, transparent when not. Godot #107582.

Fix: make the window **one pixel smaller** than the screen so Windows never
treats it as fullscreen. One pixel is imperceptible.

```csharp
w.Size = usableRect.Size - new Vector2I(1, 1);
```

This only matters for a window that actually spans the whole display — a
content-sized or strip window is never screen-sized and cannot trigger it.

### If neither fix lands

Ship an opaque-background fallback (a "disable transparency" option that draws a
normal solid background) so a user whose machine still shows black is not stuck
with an unusable black rectangle.

## CJK text overflows its box

A `Label` (or `RichTextLabel`) with `autowrap_mode = Word` **never wraps Chinese
or Japanese text**. "Word" wrapping only breaks at spaces, and CJK text has none —
so a whole CJK sentence is treated as one unbreakable word and runs straight off
the edge of its container.

`TextServer.AutowrapMode` values:

- `0` Off
- `1` Arbitrary — break at any character
- `2` Word — break only at spaces (**fails for CJK**)
- `3` WordSmart — break at word boundaries, but also break long runs / CJK

For any CJK or mixed UI, use **`WordSmart` (3)** (or `Arbitrary`). In `.tscn`
files this is `autowrap_mode = 3`; in code, `AutowrapMode =
TextServer.AutowrapMode.WordSmart`. Make `WordSmart` the default in label
templates so a stray `2` never ships.

## C# addons fail to load on a fresh clone

On a freshly cloned C# Godot project, opening the editor before the C# assembly
is built produces:

> Unable to load addon script from path: '.../SomePlugin.cs'. This might be due
> to a code error in that script. Disabling the addon...

This is **not** a code error. Godot tries to instantiate the addon's
`[Tool] EditorPlugin` at editor startup, but the C# assembly has not been built
yet, so the type cannot be resolved. Build the C# project first (the editor does
it, or run `dotnet build`; requires the .NET SDK), then reopen.

Related: Godot's plugin contract requires `plugin.cfg` to point at an
`EditorPlugin` script, so many addons ship an **empty** `EditorPlugin` stub that
does nothing. If you vendor such an addon only for its runtime classes, you can
delete the empty stub and its `plugin.cfg`, and drop the entry from
`project.godot`'s `[editor_plugins]`. The runtime `.cs` files still compile via
the project's `addons/` source glob, and you lose the fresh-clone load error.

Keep build output (`.godot/`, `bin/`, `obj/`, `.mono/`) out of git so every
machine builds its own assembly.

## Run at low power — it is a background widget

A desktop pet is on screen all day. Do not let it render flat-out and pin a CPU
core. In `_Ready()`:

```csharp
OS.LowProcessorUsageMode = true;   // only redraw when something changes
Engine.MaxFps = 30;                // a pet does not need 60
```

This is the difference between a friendly companion and a laptop-fan complaint.

## macOS: transparent always-on-top windows do not auto-focus

On macOS a transparent + borderless + always-on-top window often does **not**
become the key window on launch — until it has focus, `Area2D` input and
`_UnhandledInput` may not receive mouse events. Grab focus yourself in `_Ready()`:

```csharp
var win = GetWindow();
win.GrabFocus();
DisplayServer.WindowMoveToForeground(win.GetWindowId());
```

On Windows/Linux these calls are harmless no-ops.

## macOS: the window can land in the wrong spot on first launch

After you set `Window.Size`, the macOS window manager processes the resize
asynchronously and may re-anchor the window, eating your `Position`. If the
window appears in the wrong corner on first run, wait two frames for the WM to
settle, then re-apply size + position:

```csharp
await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
ApplyWindow();   // size + position again
```

## Test passthrough on an exported build, not editor Play

Mouse passthrough (`WS_EX_TRANSPARENT`, `MousePassthroughPolygon`) only behaves
on a real OS window. Editor Play sessions are commonly guarded off
(`OS.HasFeature("editor")`), and "embed game in editor" mode has no separate
window at all. Always verify click-through on an **exported build on the target
OS**. Windows behavior especially cannot be inferred from a macOS/Linux editor
run — that is exactly where this whole class of bugs hides.
