# Steam Input integration (Godot 4)

Read this only when you actually wire Steam Input. The decoupling pattern (strategy + always-present Godot fallback) is in `SKILL.md` Pattern 2 — this file is the concrete SDK wiring for **Steamworks.NET** (the common C# Steam binding). In GDScript you'd use a GDExtension binding (e.g. GodotSteam); the API shapes and the rules below are the same.

Steam Input is worth it for: player remapping via the Steam overlay (you stop owning rebind UI), accurate per-device button glyphs, Steam Deck / Steam Controller support, and broad pad compatibility. The cost is a poll-based API and a hard dependency you must keep optional.

## Lifecycle

- **Init (async, once):** if the Steam client is up (`SteamAPI` initialized), call `SteamInput.Init(bExplicitlyCallRunFrame: false)`, enumerate controllers, cache action-set + action handles, then apply your default controller mapping. **Always `await fallback.Init()` afterward, unconditionally**, so the Godot-native reader is ready even if Steam never initialized.
- **Callbacks:** pump `SteamAPI.RunCallbacks()` once per frame from your Steam bootstrap (separate from input polling).
- **Native lib:** the native `steam_api`/`steam_api64` must resolve. In C#, an in-editor `NativeLibrary.SetDllImportResolver` pointing at your `steam/` redistributables handles dev runs.

## Per-frame polling (this is a polling API, not events)

Call once per frame from your manager's `_Process`:

```
ProcessInput():
    if !Steam.Initialized:        fallback.ProcessInput(); return        # gate 1
    every ~1s: RefreshControllers()                                      # cheap reconnect poll
    if currentHandle is null:     fallback.ProcessInput(); return        # gate 2
    try:
        SteamInput.RunFrame()
        PollDigital()
        PollAnalog()
    catch InvalidOperationException:
        currentHandle = null;     fallback.ProcessInput()                # gate 3: clear + degrade
```

- **`SteamInput.RunFrame()`** must be called each frame before reading action data (you pass `bExplicitlyCallRunFrame:false`, but still call it explicitly here).
- **Connected controllers:** `GetConnectedControllers(InputHandle_t[16])`; for a single-player game use **`array[0]` only** (no local multiplayer / multi-pad). Enumerate if you need more.
- **Clear the handle on any exception** so the next frame cleanly retries enumeration instead of hammering a dead handle.

### Digital actions

For each `(steamActionName → semanticActionName)` in your config:
```
data = SteamInput.GetDigitalActionData(handle, cachedDigitalHandle[name])
isDown = data.bState == 1
on rising/falling edge (diff vs your own pressed-set):
    Input.ParseInputEvent(new InputEventAction { Action = semanticActionName, Pressed = isDown })
```
Cache the `InputDigitalActionHandle_t` per action name once (in your "update input map" step), not every frame.

### Analog actions (sticks)

```
v = SteamInput.GetAnalogActionData(handle, joystickActionHandle).<x,y>   # Vector2
if moved beyond ~0.05 from last:
    emit InputEventJoypadMotion for LeftX = v.X and LeftY = -v.Y          # note the Y flip
# also synthesize discrete Up/Down/Left/Right InputEventActions at ±0.5 thresholds
# so menu navigation works off the stick without reading axes everywhere
```

## Action sets

- Get the set once: `GetActionSetHandle("Controls")`; **re-activate it** with `ActivateActionSet(handle, set)` on every reconnect check (cheap, and survives controller swaps).
- Prefer a **single action set** with **no action-set layers** — handle screen context (combat vs. menu) in game code rather than by switching Steam action sets. Layers (`ActivateActionSetLayer`) exist if you want Steam to gate inputs per screen, but you usually don't need them; a single set keeps the model simple.

## Glyphs (button prompts)

`GetHotkeyIcon(action)`:
1. If Steam not up or no live handle → **fallback** glyph (bundled atlas via `Input.GetJoyName`-selected config). See `SKILL.md` "Button-prompt glyphs".
2. Else `GetDigitalActionOrigins(...)` → take origin[0] → `TranslateActionOrigin(inputType, origin)` → map that origin to your abstract button → load the **same bundled `.tres`** art.
3. Only if the origin isn't in your map: `GetGlyphSVGForActionOrigin(origin, 0)` returns a file path; `Image.LoadFromFile` it and cache. This is the **last resort**, not the primary path.

So even with Steam, your bundled art is the primary glyph source; Steam just tells you *which* button is bound. Refetch on controller-type change.

## Capability gates without Steam

- `ShouldAllowControllerRebinding`: **false when Steam is initialized** (Steam owns remapping via the overlay; disable your in-game controller rebinder, show a "configure in Steam" note, fade the icon). When Steam is down, delegate to the fallback (which returns **true** — your own rebinder works).
- Default controller map, config, and glyphs all delegate to the fallback under the same gates. Delegate the **whole interface**, not just `ProcessInput`.

## What you can usually skip

- **Rumble / haptics / LED / trigger effects** (`TriggerVibration`, `SetLEDColor`, …) — not needed for input itself; add if you want them.
- **Action-set layers** — skip unless you need Steam to gate inputs per screen.
- **Multi-controller** — skip for single-player; `GetConnectedControllers` already enumerates if you later need it.

These are scope cuts, not requirements — don't assume the pattern needs them.

## Gotchas

- **Don't reuse mutable `InputEvent` instances.** Caching and mutating one `InputEventAction`/`InputEventJoypadMotion` before each `ParseInputEvent` is a latent bug (see `SKILL.md` Pattern 1 footgun). Allocate fresh.
- **Poll-based:** if you forget `RunFrame()` or stop calling `ProcessInput()` each frame, input silently dies — there are no events to fall back on.
- **Y axis flip** between Steam analog data and Godot's `InputEventJoypadMotion` Y.
- **Reconnect cost:** enumerate controllers on a timer (~1s), not every frame.
