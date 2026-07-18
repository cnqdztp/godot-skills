---
name: godot-input
description: >-
  Godot 4.7 multi-device input architecture for touchscreen, mouse, keyboard,
  gamepad, and optional Steam Input. Covers device-family and interaction-mode
  state, native touch plus compatibility-event isolation, semantic actions,
  modal focus routing, navigation repeat, active-controller tracking, runtime
  rebinding, prompt glyphs, virtual keyboards, haptics, and regression tests
  for GDScript projects.
---

# Godot 4.7 multi-device input

## Core contract

- One input manager owns global device detection and the normalized pointer stream. Controls still
  read local raw events in `_gui_input` when their interaction requires it.
- Gameplay and UI use semantic actions and normalized pointer signals.
- Default bindings live in `InputMap`.
- UI edges are event-driven. Poll only held and analog state.
- Device detection never consumes the event that caused a mode switch.
- Physical and compatibility events remain distinguishable by event device. SDK, rebinding, replay,
  automation, and test adapters retain their source IDs before aggregate semantic injection.
- Native Godot gamepad input remains complete when a platform SDK is unavailable.
- The input manager and pause-menu router use `PROCESS_MODE_ALWAYS` when input must work while paused.

## Independent state

Keep these values separate:

| State | Values | Consumers |
|---|---|---|
| Device family | `KBM`, `TOUCH`, `PAD` | glyphs, cursor, active controller, haptics |
| Interaction mode | `POINTER`, `NAVIGATION` | hover, focus visuals, focus repair |
| Capabilities | touch available, virtual keyboard, Steam Deck profile, Steam Input ownership | feature visibility and platform paths |

`KBM` includes two interaction modes. Mouse movement selects `POINTER`; keyboard navigation actions
select `NAVIGATION`. Ordinary text entry keeps the current interaction mode.

Touch capability does not imply that touch is the active device. A physical touch event does not
imply a Steam Deck environment. Steam Deck detection does not imply that Steam Input owns actions.

```gdscript
enum Device { KBM, TOUCH, PAD }
enum InteractionMode { POINTER, NAVIGATION }

signal device_changed(device: int)
signal interaction_mode_changed(mode: int)
signal ui_navigation_intent
signal pointer_pressed(position: Vector2, touch_index: int)
signal pointer_moved(position: Vector2, relative: Vector2, touch_index: int)
signal pointer_released(position: Vector2, touch_index: int)
signal native_touch_available

var active_device := Device.KBM
var interaction_mode := InteractionMode.POINTER
var active_pad_id := -1
var last_pointer_device := Device.KBM
var supports_touch := false
```

## Event stages

Godot propagates a viewport event in this order:

1. `Node._input`
2. `Control._gui_input`
3. `Node._shortcut_input`
4. `Node._unhandled_key_input`
5. `Node._unhandled_input`

Use each stage for one responsibility:

| Stage | Responsibility |
|---|---|
| `_input` | physical device detection, interaction-mode changes, native pointer normalization, synchronous focus preparation |
| `_gui_input` | control-local clicks, drags, accepts, and `accept_event()` |
| `_shortcut_input` | global shortcuts after GUI has had first refusal |
| `_unhandled_key_input` | gameplay keys that text controls did not consume |
| `_unhandled_input` | remaining semantic edges and synthetic-action fallback |

`Viewport.set_input_as_handled()` and `Control.accept_event()` change propagation only. They do not
change `Input.is_action_pressed()` state. Call them only after a control or router owns the action.

## Device and interaction detection

```gdscript
const STICK_DEADZONE := 0.4
const TRIGGER_DEVICE_THRESHOLD := 0.3
const MOUSE_RECLAIM_DISTANCE := 10.0

var _mouse_travel := 0.0

func _input(event: InputEvent) -> void:
	if _is_emulated_pointing_event(event):
		return # do not consume; ordinary Controls still need the compatibility event

	var navigation_intent := false
	if event is InputEventScreenTouch:
		_set_touch_capability()
		_set_device(Device.TOUCH)
		_set_interaction_mode(InteractionMode.POINTER)
		_route_screen_touch(event)
	elif event is InputEventScreenDrag:
		_set_touch_capability()
		_set_device(Device.TOUCH)
		_set_interaction_mode(InteractionMode.POINTER)
		_route_screen_drag(event)
	elif event is InputEventMouseButton:
		if event.pressed:
			_set_device(Device.KBM)
			_set_interaction_mode(InteractionMode.POINTER)
			_mouse_travel = 0.0
		_route_mouse_button(event)
	elif event is InputEventMouseMotion:
		if not event.screen_relative.is_zero_approx():
			if active_device == Device.KBM:
				_mouse_travel = 0.0
				_set_interaction_mode(InteractionMode.POINTER)
			else:
				_mouse_travel += event.screen_relative.length()
				if _mouse_travel >= MOUSE_RECLAIM_DISTANCE:
					_mouse_travel = 0.0
					_set_device(Device.KBM)
					_set_interaction_mode(InteractionMode.POINTER)
		if active_device == Device.KBM:
			_route_mouse_motion(event)
	elif event is InputEventKey and event.pressed and not event.echo:
		_set_device(Device.KBM)
		if _is_keyboard_navigation(event):
			_set_interaction_mode(InteractionMode.NAVIGATION)
			navigation_intent = true
	elif event is InputEventJoypadButton and event.pressed:
		_set_active_pad(event.device)
		_set_device(Device.PAD)
		if _is_ui_navigation_event(event):
			_set_interaction_mode(InteractionMode.NAVIGATION)
			navigation_intent = true
	elif event is InputEventJoypadMotion \
			and _is_pad_motion_actuated(event as InputEventJoypadMotion):
		_set_active_pad(event.device)
		_set_device(Device.PAD)
		if _is_ui_navigation_event(event):
			_set_interaction_mode(InteractionMode.NAVIGATION)
			navigation_intent = true

	if navigation_intent:
		ui_navigation_intent.emit() # synchronous; do not mark the event handled

func _is_emulated_pointing_event(event: InputEvent) -> bool:
	return event.device == InputEvent.DEVICE_ID_EMULATION and (
		event is InputEventMouseButton
		or event is InputEventMouseMotion
		or event is InputEventScreenTouch
		or event is InputEventScreenDrag
	)

func _is_pad_motion_actuated(event: InputEventJoypadMotion) -> bool:
	if event.axis in [JOY_AXIS_TRIGGER_LEFT, JOY_AXIS_TRIGGER_RIGHT]:
		return event.axis_value > TRIGGER_DEVICE_THRESHOLD
	return absf(event.axis_value) > STICK_DEADZONE

func _is_ui_navigation_event(event: InputEvent) -> bool:
	for action in [&"ui_up", &"ui_down", &"ui_left", &"ui_right", &"ui_accept", &"ui_cancel"]:
		if event.is_action_pressed(action):
			return true
	return false
```

Mouse presses and wheel input reclaim pointer ownership immediately. A release that closes an
already-owned mouse gesture does not reclaim ownership. Mouse motion uses accumulated unscaled travel;
a per-event velocity threshold misses slow deliberate motion. Ignore zero-screen-relative motion because
Godot and the operating system may emit it without physical movement.

Do not move the operating-system cursor during device changes. Publish cursor intent to one cursor
policy arbiter: UI mode requests `Input.MOUSE_MODE_VISIBLE` for `KBM` and `MOUSE_MODE_HIDDEN` for
touch or pad; gameplay and cutscene requests for captured, confined, or hidden cursor states take
priority. Resolve stale hover in UI feedback state, not with `warp_mouse()`.

## Pointer normalization

- Set `active_device` before emitting the first touch pointer signal.
- Track an owning touch `index` for single-finger interactions.
- Treat `InputEventScreenTouch.canceled` as release.
- Clear an owning touch on window focus loss, node hide or exit, modal replacement, and pointer-owner
  changes.
- In `_input`, pointer `position` is viewport-local. In `_gui_input`, it is local to the receiving
  `Control`.
- Use `relative` for movement in content-scaled UI coordinates.
- Use `screen_relative` and `screen_velocity` for physical thresholds, aiming, and sensitivity.
- Store per-index state for multi-touch and gestures.
- Do not merge every finger into one `pointer_pressed` boolean.

Keep `input_devices/pointing/emulate_mouse_from_touch=true` for ordinary Godot controls. Filter its
`DEVICE_ID_EMULATION` mouse twin from device ownership and from any custom control that already
processed native touch. Keep `emulate_touch_from_mouse=false` in production.

Detailed touch, OSK, and touch-only UI rules: `references/touch-and-emulation.md`.

## Semantic actions

Define stable actions such as:

- `ui_up`, `ui_down`, `ui_left`, `ui_right`, `ui_accept`, `ui_cancel`
- `confirm`, `cancel`, `menu`, `report_bug`
- `shoulder_left`, `shoulder_right`, `trigger_left`, `trigger_right`

Give core navigation, confirm, cancel, and menu actions a keyboard fallback unless the action is
intentionally device-exclusive.

Use native `ui_*` actions for `Control` focus navigation. Keep gameplay action names separate where
one physical input has different routing semantics. A physical A/Enter event may match both
`ui_accept` and `confirm`; collapse it to one logical confirm edge before emitting a custom signal.

For external SDK, runtime-rebinding, replay, automation, or test translation, aggregate held state by
source before injecting global semantic edges:

```gdscript
var _digital_sources: Dictionary = {} # action -> {source_id: true}
var _injecting := false

func set_action_source(action: StringName, source_id: StringName, pressed: bool) -> void:
	if _injecting:
		return
	var sources: Dictionary = _digital_sources.get(action, {})
	var was_pressed := not sources.is_empty()
	if pressed:
		sources[source_id] = true
	else:
		sources.erase(source_id)
	_digital_sources[action] = sources

	var is_pressed := not sources.is_empty()
	if was_pressed == is_pressed:
		return
	var event := InputEventAction.new()
	event.action = action
	event.pressed = is_pressed
	event.strength = 1.0 if is_pressed else 0.0
	_injecting = true
	Input.parse_input_event(event)
	_injecting = false
```

- Give every physical or platform source a stable ID within its adapter.
- Remove that source from every held action on disconnect, context change, or adapter failure.
- Aggregate analog sources explicitly; define whether strongest magnitude, most recent source, or a
  domain-specific combination owns the semantic value.
- Allocate a new event for each edge.
- Emit release for every injected press that enters global action state.
- Guard against translating an injected event a second time.
- `Input.action_press()` changes polled state but does not call `_input`.
- `Viewport.push_input()` is suitable for GUI-only repeat that must not pollute global held state.

Runtime rebinding rules: `references/rebinding.md`.

## UI focus and modal routing

- Use native `focus_neighbor_*` and `focus_mode` for directional navigation.
- Build neighbors after dynamic lists and grids are populated.
- Register each modal root with a default focus control.
- Set the top modal root to `FOCUS_BEHAVIOR_ENABLED` and background modal roots to
  `FOCUS_BEHAVIOR_DISABLED` through `focus_behavior_recursive`.
- Validate candidates with `get_focus_mode_with_override()`, visibility, and ancestry.
- Preserve the exact previous focus with a `WeakRef` and restore it when a nested modal closes.
- Repair missing, hidden, freed, or escaped focus only in `NAVIGATION` mode.
- Repair focus synchronously on every navigation intent, including repeated intent while the device
  and mode remain unchanged.
- Let the same physical event continue to native `ui_*` handling after focus repair.
- In `ScrollContainer`, call `ensure_control_visible()` when focus changes.

Render hover only in `POINTER` mode and logical focus only in `NAVIGATION` mode. Clear transient
pressed and hover state on ownership changes. Touch has press state but no persistent hover.

Detailed modal, repeat, confirm, and cancel routing: `references/focus-routing.md`.

## Gamepad state

- Record `event.device` from the pad event that actually actuated input.
- Do not assume device ID `0`; connected-pad order is not stable across restarts.
- Use `Input.get_connected_joypads()` only to seed a candidate before the first pad event.
- Listen to `Input.joy_connection_changed`.
- On active-pad disconnect: stop vibration, select a remaining candidate, clear held/repeat state,
  and restore the most recent valid pointer family when no pad remains.
- Use `Input.get_action_raw_strength()` for trigger business thresholds. Action deadzones otherwise
  remap the physical travel before the business threshold is applied.
- Track stick deadzone, trigger device-ownership threshold, and trigger activation threshold as
  separate values.
- Resolve glyph brand from `Input.get_joy_info(active_pad_id)` vendor, product, raw-name, and Steam
  index data when available; use `Input.get_joy_name(active_pad_id)` matching only as fallback.

## Prompt glyphs and haptics

Use semantic glyph IDs and device sets:

- keyboard/mouse
- touch
- Xbox
- PlayStation
- Nintendo

Missing glyphs are valid. Hide the corresponding prompt row instead of rendering an empty frame.
Emit `device_changed` when the active family changes and when the active pad brand changes.

Centralize vibration. Godot's argument order is weak motor, strong motor:

```gdscript
Input.start_joy_vibration(active_pad_id, weak, strong, duration)
```

Use explicit durations or call `stop_joy_vibration()`. Stop motors on disconnect, pause transitions,
and shutdown. Check `active_pad_id >= 0 and Input.has_joy_vibration(active_pad_id)` before exposing
haptic settings.

Steam Input lifecycle, ownership, action manifests, and native fallback:
`references/steam-input.md`.

## Touch-only controls and text entry

- Capability controls whether touch support exists.
- Active device controls current prompt and interaction ownership.
- Critical back, settings, and report actions need a visible touch path on every touch-reachable
  screen. A persistent fallback may yield to a visible scene-owned control.
- Alpha-only hiding does not disable hit testing, focus, or input callbacks.
- A suppressed subtree releases focus and disables mouse, focus, shortcut, handled, and unhandled
  input paths; restore the exact prior state when shown or detached.
- Suppress dynamic descendants after their `_ready` callback has established final input state.
- Show the native virtual keyboard only when the display server supports it and the active user is
  not typing with physical keyboard/mouse; otherwise use the platform or product OSK adapter.
- Hide the virtual keyboard on focus exit and submission; reposition content using the reported
  keyboard height and safe area.

## Failure matrix

| Symptom | Check |
|---|---|
| First pad direction only changes prompts | mode-switch event was consumed, or focus repair was deferred |
| One touch activates twice | native touch and emulated mouse both entered custom logic |
| First touch callback sees KBM | device state was updated after pointer signal emission |
| Slow mouse never reclaims pointer | per-event velocity threshold used instead of accumulated travel |
| Cursor disappears after pad disconnect | active pad and cursor state were not recovered |
| Hover and focus highlight appear together | device family used where interaction mode was required |
| Trigger activates too late | deadzone-adjusted strength used instead of raw strength |
| Navigation remains held | injected press has no release |
| Background modal accepts focus | child `focus_mode` was changed without recursive modal isolation |
| Touch-only control is invisible but clickable | only alpha or visibility presentation changed |
| Drag sensitivity changes with stretch scale | `relative` used for a physical-distance calculation |
| Steam client is running but controller is inert | SDK readiness was treated as an active input handle |

## Verification

Automated tests must cover:

- touch, mouse, keyboard, joy button, stick, trigger, emulated pointing, and injected action events;
- touch-to-mouse compatibility without duplicate canonical pointer signals;
- physical touch upgrading a false-negative touch capability probe;
- first touch ownership before callbacks;
- slow accumulated mouse reclaim and immediate mouse-click reclaim;
- keyboard navigation versus ordinary text keys within the `KBM` family;
- stick and trigger boundary values;
- first navigation event, same-mode focus repair, nested modal restore, and background focus blocking;
- GUI-only navigation repeat, one step per frame, reset on release/device/modal changes;
- cancel/menu arbitration and handled propagation;
- active pad IDs other than `0`, disconnect, reconnect, and brand changes;
- hidden touch subtree state, dynamically added children, and detached-child restoration;
- glyph presence and absence for every device set;
- SDK unavailable, initialized-without-handle, active, disconnected, and exception fallback states;
- window focus loss releases owned gestures and injected held actions, clears repeat, and stops haptics.

For the global action and device pipeline, inject with `Input.parse_input_event()`, call
`Input.flush_buffered_events()`, then await the relevant process frames. For GUI picking and viewport
coordinates, use `Viewport.push_input()` or a real window; flushing does not replace process frames or
GUI dispatch. Validate hover, OSK, safe areas, gamepad disconnect, and touch compatibility on windowed
builds and physical target devices.
