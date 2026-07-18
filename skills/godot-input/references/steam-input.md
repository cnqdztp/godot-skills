# Steam Input ownership and fallback

## Required product assets

- One product action manifest with digital actions, analog actions, and action sets.
- A default controller configuration published through Steamworks.
- Manifest and configuration files included in the shipped depot.
- Cached action-set, digital-action, and analog-action handles.
- Action-origin-to-glyph mapping.
- A complete Godot-native controller path.

SDK examples and toolchain sample VDF files are not product manifests.

## Ownership state

Track these values separately:

- Steam client initialized.
- Steam Input initialized.
- Controller handle valid.
- Action set active.
- Steam Input currently owns semantic action emission.

Steam client initialization alone never disables the native path or in-game rebinding. Steam Input
owns actions only while all required handles are valid and polling is healthy.

```gdscript
func fall_back_to_native() -> void:
	release_all_steam_sources()
	clear_steam_handles()
	set_steam_ownership(false)
	process_native_gamepads([])

func process_controller_input() -> void:
	if not steam_client_ready:
		fall_back_to_native()
		return
	if not steam_input_ready:
		fall_back_to_native()
		return
	if not refresh_or_validate_controller_handle():
		fall_back_to_native()
		return
	var result: Dictionary = read_all_steam_actions()
	if not result.get("ok", false):
		fall_back_to_native()
		return
	commit_steam_snapshot(result.get("state", {}))
	set_steam_ownership(true)
	process_native_gamepads(steam_owned_native_ids)
```

The native path initializes unconditionally. `process_native_gamepads()` accepts the native device IDs
to suppress; an empty list processes every native controller. It handles actions, prompts, remapping,
connect and disconnect, and haptics without Steam.

Read all required digital and analog values into a temporary snapshot. Commit semantic edges and
ownership only after the full read succeeds. On any partial failure, release every Steam-owned source,
clear ownership, and run native fallback in the same frame; never commit half a frame.

## SDK update mode

Use one update model:

- Automatic SDK update through the platform callback pump; or
- Explicit Steam Input frame update before action reads.

Do not initialize automatic update mode and also require a manual input frame call. Verify the exact
method names and initialization flags against the installed binding. GodotSteam and Steamworks.NET
do not expose identical APIs.

## Connection lifecycle

- Refresh controller enumeration on a timer and on connection callbacks.
- Do not enumerate every rendered frame.
- Clear the active handle after any failed action read.
- Reactivate the action set after reconnect.
- Emit releases for every semantic action that was held when ownership is lost.
- Stop platform and native vibration on disconnect.
- Allow a remaining native controller to become the candidate immediately.
- While Steam owns a physical controller, suppress that controller's matching Godot-native action
  events at the adapter boundary, but keep unrelated native controllers available. Correlate devices
  with verified binding metadata such as `Input.get_joy_info()` Steam input indices when present;
  do not suppress every native pad merely because one Steam handle is active.

## Digital actions

For every Steam digital action:

1. Cache its action handle.
2. Read current down state for the active controller handle.
3. Compare with the previous state.
4. Inject one semantic press on the rising edge.
5. Inject one semantic release on the falling edge.
6. Allocate a new `InputEventAction` for each edge.

Do not emit the same physical controller through Steam and the native reader simultaneously. Clear
the suppression only after Steam-held sources and ownership have been released.

## Analog actions

- Read analog values after the SDK update step.
- Normalize axis orientation once at the adapter boundary.
- Apply an explicit deadzone.
- Preserve analog strength for gameplay.
- Generate digital navigation edges only at threshold crossings.
- Generate matching releases when an axis returns inside the threshold.
- Keep GUI repeat separate from the initial physical edge.

## Action sets

- Keep menu and gameplay actions in one set when the game already owns context routing.
- Use separate sets or layers only when platform-side context gating is required.
- Activate the intended set after every valid-handle change.
- Release actions from the previous set before switching.

## Glyphs

1. Query the active Steam action origin.
2. Map the origin to a semantic physical control.
3. Resolve a bundled Xbox, PlayStation, Nintendo, or Steam Deck texture.
4. Use an SDK-rendered glyph only when no bundled mapping exists.
5. Refresh on controller-handle, controller-type, binding, and action-set changes.

When no Steam handle is valid, use the native active pad ID and native glyph set.

## Rebinding ownership

- Steam path actively owns actions: direct the user to Steam's configuration surface.
- Steam initialized without a valid owning handle: keep native in-game rebinding enabled.
- Native store or offline run: keep native in-game rebinding enabled.
- Persist keyboard bindings independently from Steam controller bindings.

## Steam Deck profile

Use the platform SDK's Steam Deck profile query. Do not infer Steam Deck from resolution, Linux,
controller name, or environment variables. Keep this platform profile separate from:

- native touch capability;
- current input device;
- Steam Input controller ownership;
- controller glyph brand.

## Shutdown

- Emit semantic releases for held Steam actions.
- Stop vibration.
- Clear controller and action handles.
- Shut down Steam Input if initialization succeeded.
- Continue running the native input manager until application teardown.

## Verification matrix

- Steam unavailable.
- Steam client available, Steam Input unavailable.
- Steam Input initialized, no controller handle.
- Valid controller and action set.
- Controller disconnect while an action is held.
- Controller reconnect with a different type.
- Action-set switch while analog input is actuated.
- SDK read failure followed by native fallback in the same frame.
- Partial SDK read failure commits no digital or analog edges.
- Steam path and native path never emit duplicate semantic edges.
- Steam ownership suppresses only the correlated native controller, not unrelated pads.
- In-game rebinding remains enabled whenever Steam Input does not own the live path.
