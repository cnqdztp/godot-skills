---
name: godot-input
metadata:
  author: cnzangtianpei@gmail.com
description: >-
  Architecture for Godot 4 input when a game must support gamepad AND
  mouse/keyboard at the same time — and optionally Steam Input — without the
  three paths fighting each other: a semantic-action "normalization bus" that turns
  every raw device event into one set of gameplay actions via
  Input.ParseInputEvent; decoupling an optional platform SDK (Steam Input) from
  the engine-native gamepad reader with a strategy + always-present fallback so
  the game is fully playable WITHOUT Steam; mouse↔controller device-mode
  switching driven by a single source-of-truth flag (warp/hide cursor, grab UI
  focus) with anti-thrash detectors; controller menu navigation built on Godot's
  native focus system (FocusNeighbor*, GrabFocus); runtime key/button rebinding
  that NEVER mutates Godot's InputMap (keep your own dictionary, swap-on-conflict,
  persist to your own save file); per-controller button-prompt glyphs; and where
  the touch seam is if you ever need it. Use this whenever you add controller /
  gamepad support, must support multiple input devices simultaneously, integrate
  Steam Input, implement input remapping / rebinding UI, switch between mouse and
  gamepad, show platform-correct button-prompt icons, or wire up controller UI
  focus navigation in Godot 4 — in C# or GDScript. Consult it BEFORE designing an
  input layer so the device paths are decoupled from the start.
---

# Godot 4 Input Architecture (multi-device, SDK-optional)

Most Godot input tutorials stop at "make an action in the Input Map, call `Input.is_action_pressed`". That falls apart the moment a real game needs **gamepad and mouse/keyboard live at the same time**, **platform-correct button glyphs**, **runtime rebinding**, and an **optional platform SDK** (Steam Input) that may or may not be present. This skill shows how to solve all five in Godot 4 (C#), and what to copy vs. avoid.

Examples are C#; each pattern has a **GDScript callout**. The five patterns are independent — read the one you need.

The mental model: **one bus, many sources.**

```
keyboard ─┐
mouse  ───┤                                   ┌─ UI / gameplay (only ever
gamepad ──┤── normalize to SEMANTIC actions ──┤   call IsActionPressed
Steam ────┘   via Input.ParseInputEvent       └─ Godot focus nav (ui_* actions)
```

Downstream code never asks "which device?" — it asks "did the *attack* action fire?". Device identity lives in exactly one place (a device-mode flag) and only drives UX (cursor, focus), never gameplay logic.

---

## Pattern 1 — The normalization bus (do this first)

**Problem:** if each screen reads raw `InputEventKey` / `InputEventJoypadButton` / SDK polling, you get N×M branching and rebinding is impossible.

**Solution:** translate every raw input into a **semantic action** (`attack`, `accept`, `cancel`, …) and re-inject it with `Input.ParseInputEvent`. The whole game listens only to semantic actions.

```csharp
// Capture raw input in _UnhandledKeyInput / _UnhandledInput, NOT _Input —
// so a focused LineEdit / text field consumes the key first.
public override void _UnhandledKeyInput(InputEvent e)
{
    if (e is not InputEventKey k || k.IsEcho()) return;
    foreach (var (action, key) in _keyboardMap)           // action -> Key
        if (k.Keycode == key)
            // ALLOCATE A FRESH EVENT EVERY TIME — see footgun below.
            Input.ParseInputEvent(new InputEventAction { Action = action, Pressed = e.IsPressed() });
}
```

**Make your nav actions the engine's built-in `ui_*` actions.** Define `accept = "ui_accept"`, `up = "ui_up"`, `cancel = "ui_cancel"`, etc. Then Godot's *built-in* focus navigation rides the same bus for free (Pattern 4) — you don't reimplement directional menu movement.

**Two-layer remapping, kept separate.** Don't bake the semantic mapping into each device reader. Use two hops:
1. **raw → raw** normalization inside a device reader (e.g. left-stick → d-pad, so stick and d-pad share one code path).
2. **raw → semantic** in one central place (`_UnhandledInput`), driven by the user-rebindable dictionary.

The re-injected raw event from step 1 re-enters `_UnhandledInput` and becomes a semantic action in step 2. One mapping table, not one per device.

> ### ⚠️ Footgun: never reuse a mutable `InputEvent` instance
> It's tempting to cache one `InputEventAction`/`InputEventJoypadMotion` and mutate `.Pressed`/`.AxisValue` before each `ParseInputEvent` to save allocations. **Don't.** Godot queues/forwards the *reference*; a later mutation (the matching release, or next frame) can corrupt what a consumer reads, because the pipeline does not deep-copy. Allocate a fresh `new InputEventAction { … }` per injection — do the per-event allocation in your one input-manager node, not inside each device strategy.

> **GDScript:** `func _unhandled_key_input(e):` → `Input.parse_input_event(InputEventAction.new())` after setting `.action` / `.pressed`. Same rule: build a *new* `InputEventAction.new()` each time; don't keep one around and mutate it.

---

## Pattern 2 — Gamepad WITHOUT Steam: strategy + always-present fallback

**Problem:** you want Steam Input (great remapping, glyphs, Deck support) but the game must run identically with **no Steam at all** — other stores, dev runs, Steam offline, no controller. Steam must be *decoupled*, not load-bearing.

**Solution:** a strategy interface with two implementations, where the SDK strategy **composes** the engine-native one as a private fallback and **re-checks availability every frame**.

```csharp
interface IControllerInputStrategy
{
    Task Init();
    void ProcessInput();                 // called once per frame
    bool ShouldAllowControllerRebinding { get; }
    Texture2D GetHotkeyIcon(string action);
    // ...config / default-map accessors
}

// Engine-native: ALWAYS works, zero SDK dependency. The safety net.
class GodotControllerStrategy : IControllerInputStrategy
{
    public bool ShouldAllowControllerRebinding => true;       // we own remapping
    public void ProcessInput()
    {
        // read pads purely through the Godot Input Map, and synthesize
        // stick -> dpad so navigation has ONE path (Pattern 1, layer 1):
        foreach (var (stick, dpad) in _stickToDpad)
            if (Input.IsActionJustPressed(stick))
                Input.ParseInputEvent(new InputEventAction { Action = dpad, Pressed = true });
    }
    // pad type via Input.GetJoyName(0).Contains("DualSense"/"Xbox"/...) -> per-platform config
}

// SDK-rich: delegates the ENTIRE frame to the fallback when Steam is down.
class SteamControllerStrategy : IControllerInputStrategy
{
    readonly IControllerInputStrategy _fallback = new GodotControllerStrategy();
    InputHandle? _device;

    public async Task Init()
    {
        if (Steam.Initialized) { /* SteamInput.Init(); cache action handles */ }
        await _fallback.Init();                 // ALWAYS init the fallback, unconditionally
    }

    public void ProcessInput()
    {
        if (!Steam.Initialized) { _fallback.ProcessInput(); return; }   // gate 1
        RefreshDeviceEverySecond();
        if (_device is null) { _fallback.ProcessInput(); return; }      // gate 2
        try { SteamInput.RunFrame(); PollDigital(); PollAnalog(); }
        catch (InvalidOperationException) { _device = null; _fallback.ProcessInput(); } // gate 3
    }

    public bool ShouldAllowControllerRebinding =>
        Steam.Initialized ? false : _fallback.ShouldAllowControllerRebinding;  // Steam owns remap
}
```

Key rules, each load-bearing:
- **Construct only the SDK strategy.** The manager never picks between them; the native reader is reached *only* through the fallback. One wiring, no branching at the call site.
- **Re-evaluate availability every frame**, not once at boot. Controllers disconnect; SDK calls throw. Three gates: SDK not initialized → no live device → exception (and clear the handle so next frame retries cleanly).
- **`Init()` awaits the fallback unconditionally** so the engine-native reader is ready even when Steam never comes up.
- **The fallback must be a complete, standalone reader** (full Godot Input Map path). If it's a stub, "no Steam" means "broken game".
- **Delegate the whole interface**, not just `ProcessInput` — rebinding capability, glyph lookup, configs all fall back too.

The manager exposes capabilities with null-coalescing defaults so UI never branches on the platform:
```csharp
public bool ShouldAllowControllerRebinding => _strategy?.ShouldAllowControllerRebinding ?? true;
```

> **GDScript:** no interfaces, but the same shape works with duck typing: two scripts (`godot_controller_strategy.gd`, `steam_controller_strategy.gd`) exposing `process_input()`, `init()`, `should_allow_controller_rebinding()`; the Steam one holds `var _fallback = GodotControllerStrategy.new()` and calls `_fallback.process_input()` under the same three gates. Steam Input itself needs GDExtension (e.g. GodotSteam) — the decoupling pattern is identical.

Concrete Steam Input wiring (action sets, digital/analog polling, origins → glyphs, when exactly to fall back) lives in **`references/steam-input.md`** — read it only when you actually integrate Steam.

---

## Pattern 3 — Mouse/keyboard AND gamepad at the same time

**Problem:** both devices are always plugged in. You need the cursor to disappear and UI focus to appear the instant the player touches the stick, and the cursor to come back the instant they wiggle the mouse — without the two fighting (thrash).

**Solution:** one authoritative bool `IsUsingController`, and **exactly one detector running per frame**, chosen by the current mode. The *active* device can't re-trigger its own switch, so you need no timers or debouncing.

```csharp
public bool IsUsingController { get; private set; }

public override void _Input(InputEvent e)
{
    if (IsUsingController) DetectMouse(e);     // only watch for the OTHER device
    else                   DetectController(e);
}

void DetectController(InputEvent e)
{
    if (!_allControllerActions.Any(a => e.IsActionPressed(a))) return;
    IsUsingController = true;
    _stashedMouse = DisplayServer.MouseGetPosition() - DisplayServer.WindowGetPosition();
    GetViewport().WarpMouse(Vector2.One * -1000f);     // hide cursor offscreen
    ActiveScreen.FocusOnDefaultControl();              // give the stick something to land on
    EmitSignal(SignalName.ControllerDetected);
    GetViewport().SetInputAsHandled();                 // controller edge only
}

void DetectMouse(InputEvent e)
{
    bool moved = e is InputEventMouseMotion m && m.Velocity.LengthSquared() > 100f; // squared vs squared, no sqrt
    if (e is not InputEventMouseButton && !moved) return;
    IsUsingController = false;
    Input.WarpMouse(_stashedMouse);                    // restore where the cursor was
    GetViewport().GuiReleaseFocus();
    EmitSignal(SignalName.MouseDetected);
}
```

Why it works and what to copy:
- **Single source of truth.** Everything else (cursor visibility, focus grabbing, glyph vs. no-glyph) reads `IsUsingController`; nothing else stores device state.
- **Velocity threshold** on mouse motion (compare `LengthSquared()` to a squared constant) so a tiny bump/drift doesn't yank focus away from a controller user.
- **Stash-and-restore the cursor** using window-relative coords (`MouseGetPosition() - WindowGetPosition()`) so it survives HiDPI / windowed offsets.
- **Gameplay pipelines stay device-agnostic.** `_UnhandledInput` / `_UnhandledKeyInput` run regardless of the flag — keyboard shortcuts always fire even in "controller mode". The flag governs **cursor + focus UX only**, never whether an action is accepted. This is what makes the two truly simultaneous.

A separate cursor manager toggles visibility off the signals, **AND-ed with any other reason to hide** (e.g. a cutscene):
```csharp
Input.MouseMode = (!IsUsingController && _shouldShowCursor)
    ? Input.MouseModeEnum.Visible : Input.MouseModeEnum.Hidden;
```

> **GDScript:** `func _input(e):` with `if is_using_controller: _detect_mouse(e) else: _detect_controller(e)`. Use `get_viewport().warp_mouse()`, `get_viewport().gui_release_focus()`, `get_viewport().set_input_as_handled()`, `Input.mouse_mode = Input.MOUSE_MODE_HIDDEN`. Emit `controller_detected` / `mouse_detected` signals for the cursor node.

---

## Pattern 4 — Controller menu navigation = Godot's native focus system

**Don't build a custom navigation graph.** Because nav actions ARE `ui_up/ui_down/ui_left/ui_right/ui_accept/ui_cancel` (Pattern 1), Godot's engine focus traversal already moves the highlight for you. You only:

1. **Wire the focus graph at layout time** — set each control's `FocusNeighborTop/Bottom/Left/Right` (NodePaths) and `FocusMode`. For grids, compute neighbors in code; self-point left/right on a vertical list so the stick can't fall off the edge.
2. **Grab initial focus — but only in controller mode**, and defer if the control isn't in the tree yet:
   ```csharp
   public static void TryGrabFocus(this Control c)
   {
       if (!Manager.IsUsingController) return;            // mouse users aren't focus-locked
       if (c.IsVisibleInTree()) c.GrabFocus();
       else Callable.From(c.GrabFocus).CallDeferred();
   }
   ```
3. **React to focus** via the `FocusEntered` / `FocusExited` signals for highlight (same handlers can serve mouse `MouseEntered` / `MouseExited`, unifying hover and focus into one "is highlighted" state).
4. **Restrict navigation** for modal selections (e.g. "pick a target"): set `FocusMode = All` only on valid controls, `None` on the rest, and loop the neighbors so the stick stays inside the valid set; restore afterward.

On screen change: re-grab the default control's focus *deferred* in controller mode; re-warp the cursor in mouse mode. Keep both coherent across transitions.

> **GDScript:** `control.focus_neighbor_top = ^"../Other"`, `control.focus_mode = Control.FOCUS_ALL`, `control.grab_focus()`, `control.focus_entered.connect(...)`. Gate `grab_focus()` on your `is_using_controller` flag; defer with `control.grab_focus.call_deferred()` when not yet visible.

---

## Pattern 5 — Rebinding WITHOUT mutating Godot's InputMap

**Problem:** `InputMap.action_add_event` / `action_erase_events` mutate global engine state, are awkward to serialize, and make non-destructive "swap" UX hard.

**Solution — an indirection layer with zero `InputMap` mutation anywhere:**

1. **In `project.godot`**, define your real gameplay actions with **empty event arrays** (`mega_attack={"events":[]}`). Define a separate set of **fully-bound physical actions** for hardware you don't remap (`controller_face_button_south` → its joypad button). The physical actions stay bound because the translator matches on them; the gameplay actions stay empty because they're filled at runtime.
2. **Keep two C# dictionaries**: `action → Key` (keyboard) and `gameAction → physicalActionName` (controller).
3. **Resolve conflicts by SWAP, not reject** — the action currently holding the requested key inherits the rebinder's *old* key. No dead-ends, no error dialogs.
   ```csharp
   public void Rebind(StringName action, Key key)
   {
       var clash = _keyboardMap.FirstOrDefault(kv => kv.Value == key && _remappable.Contains(kv.Key));
       if (clash.Key != null) _keyboardMap[clash.Key] = _keyboardMap[action];  // swap
       _keyboardMap[action] = key;
       Save();
   }
   ```
4. **Apply purely through the bus** (Pattern 1): `_UnhandledKeyInput` reads the dict and re-injects the gameplay action. Nothing edits `InputMap`.
5. **Persist as plain `string → string` in your own save file** (JSON), never `project.godot`. It travels with the player profile / cloud save and survives game updates. Keyboard values are `Key` enum names (`"E"`); controller values are physical action names (`"controller_face_button_south"`).

**Capture the new binding** from the settings screen: while a row is "listening", grab the next `InputEventKey` (`_UnhandledKeyInput`) or the next *released* physical controller action (`_Input` scanning your physical-action list), call `Rebind`, `SetInputAsHandled()`.

**Gate controller rebinding on the capability flag.** Keyboard is always rebindable. Controller rebinding is allowed only when *you* own remapping — if Steam Input is active it owns remap, so disable the in-game rebinder, show a "Steam Input detected — configure in the Steam overlay" note, and fade the affected icon (`Modulate` alpha ~0.15). Read `Manager.ShouldAllowControllerRebinding` (Pattern 2), not the platform directly.

> **GDScript:** dictionaries are native; `Input.parse_input_event(...)`; persist with `FileAccess`/`JSON` or a `ConfigFile`. `OS`/store detection drives the controller-rebind gate. Same rule: never call `InputMap.action_add_event` for user rebinds — keep it in your dict.

---

## Button-prompt glyphs (A/✕, LT/L2, …)

Keep glyph art as **bundled resources keyed by an abstract button** (e.g. `face_button_south → res://.../xbox/a.tres`). Pick the atlas by **controller type**:
- **No SDK:** detect via `Input.GetJoyName(0)` substring (`"DualSense"`, `"Xbox"`, `"Switch"`, …) → per-platform config object that supplies `FolderPath` + a button→texture map. Swap A/B and X/Y for Nintendo; route "view map" to the touchpad for PlayStation; etc.
- **With Steam:** Steam reports the *origin* of each action (`TranslateActionOrigin`); map that origin to your abstract button and still load the **same bundled `.tres`**. Only fall back to Steam's own rendered glyph (`GetGlyphSVGForActionOrigin`) for origins you have no art for.

So glyphs don't hard-depend on Steam either — Steam just gives a more accurate *source of truth* for which physical button is bound. Refetch on a `ControllerTypeChanged` signal so the UI re-renders when the player swaps a pad.

---

## Touch is a separate modality — and the seam to add it

None of the above gives you touchscreen — a desktop/console input stack like this has **zero** native touch handling. Watch for false positives: `InputEventPanGesture` is the desktop **trackpad/wheel scroll** gesture (usually branched next to `InputEventMouseButton.WheelUp/Down`), and "touchpad" means the **DualShock touchpad button**, not a screen.

If a touch device is present, Godot's default `emulate_mouse_from_touch=true` turns taps into synthetic mouse clicks, so buttons/hover already work — but there's no native multi-touch, drag, or pinch.

To add real touch, **extend the one canonical scroll/drag helper** rather than building a new subsystem — every screen that routes through it gains touch at once:
```csharp
public static float GetDragForScrollEvent(InputEvent e)
{
    if (e is InputEventMouseButton { ButtonIndex: var b }) return b == MouseButton.WheelUp ? 40f : b == MouseButton.WheelDown ? -40f : 0f;
    if (e is InputEventPanGesture pan)  return -pan.Delta.Y * 50f;
    if (e is InputEventScreenDrag drag) return drag.Relative.Y;        // 1-finger kinetic pan
    return 0f;
}
// pinch-zoom: handle InputEventMagnifyGesture (e.Factor) in the zoom screen
// tap: leave emulate_mouse_from_touch on; only parse raw InputEventScreenTouch where you need gesture semantics
```
Rules: keep one helper (don't scatter touch parsing); feed the same `_targetPosition` lerp the mouse path already drives (reuse smoothing, don't invent momentum); gate touch-only UI behind `DisplayServer.IsTouchscreenAvailable()` (not a build flag) so desktop is unaffected; do **not** ship `emulate_touch_from_mouse` — it's a dev aid that fights the mouse/controller paths.

> **GDScript:** `DisplayServer.is_touchscreen_available()`; classes are `InputEventScreenTouch` (`.pressed`, `.position`), `InputEventScreenDrag` (`.relative`, `.velocity`), `InputEventMagnifyGesture` (`.factor`), `InputEventPanGesture` (`.delta`).

---

## Suggested node layout

Three focused nodes, not one god-object — split responsibilities deliberately:
- **InputManager** — owns `_UnhandledKeyInput` (keyboard → semantic) and `_UnhandledInput` (controller raw → semantic); holds the rebind dictionaries; emits `InputRebound`.
- **ControllerManager** — owns `_Input` (device-mode detection) and `_Process` (poll the active strategy); holds `IsUsingController` + the strategy; emits `ControllerDetected` / `MouseDetected` / `ControllerTypeChanged`.
- **CursorManager** — listens to those signals; toggles `Input.MouseMode` and the custom cursor.

They can be autoloads or `%`-unique children of your root scene. (`_Process` polling is required for SDK strategies because Steam Input is poll-based, not event-based.)

## Checklist when adding input to a Godot 4 game

- [ ] Gameplay actions defined with **empty events**; physical/hardware actions defined **fully bound**.
- [ ] Nav actions aliased to engine `ui_*` so focus nav is free.
- [ ] All raw input normalized to semantic actions via `Input.ParseInputEvent`, captured in `_UnhandledInput`/`_UnhandledKeyInput`. **Fresh event per injection.**
- [ ] Gamepad reader works with **no SDK**; SDK strategy composes it as a per-frame fallback; only the SDK strategy is constructed.
- [ ] One `IsUsingController` flag; mutually-exclusive detectors; cursor/focus driven off it; gameplay pipelines NOT gated by it.
- [ ] Controller focus graph wired (`FocusNeighbor*`, `FocusMode`); `GrabFocus` gated on controller mode + deferred.
- [ ] Rebinding via a dictionary (swap-on-conflict) persisted to your own save; **no `InputMap` mutation**; controller-rebind gated on the "do we own remap?" flag.
- [ ] Glyphs are bundled resources keyed by abstract button, atlas chosen by controller type.
- [ ] Decided explicitly whether touch is in scope; if so, extended the single scroll/drag helper and gated on `IsTouchscreenAvailable()`.
