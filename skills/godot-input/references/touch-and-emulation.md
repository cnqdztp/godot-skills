# Touch, compatibility events, and virtual keyboard

## Project settings

```ini
[input_devices]

pointing/emulate_mouse_from_touch=true
pointing/emulate_touch_from_mouse=false
```

Enable Android pan and magnify gestures only when the product uses them:

```ini
[input_devices]

pointing/android/enable_pan_and_scale_gestures=true
```

`InputEventPanGesture` represents two-finger pan. `InputEventMagnifyGesture` represents pinch scale.
They do not replace one-finger `InputEventScreenTouch` and `InputEventScreenDrag` handling. Desktop
touchpads may also report gesture events; do not use their presence alone as touchscreen capability.

## Physical and emulated events

Godot may produce both a physical touch event and an emulated mouse event for the same contact.
Emulated pointing events use `InputEvent.DEVICE_ID_EMULATION`.

The compatibility mouse event can arrive before the original screen-touch event. An emulated event
must therefore never acquire device ownership, even when no physical touch has been observed yet.
An ordinary `Button` may complete its compatibility callback before global state changes to `TOUCH`;
do not require the callback itself to observe `TOUCH`.

At the global input manager:

- Ignore emulated mouse and touch events for device-family ownership.
- Ignore them for the canonical pointer signal stream.
- Return without marking them handled so ordinary Controls can receive compatibility mouse input.

At a custom control that handles native touch:

- Process physical `ScreenTouch` and `ScreenDrag`.
- Ignore the emulated mouse twin for the same gesture.
- Do not let both paths call the action callback.

At an ordinary `Button`, `Slider`, or other built-in Control:

- Compatibility mouse input may provide the complete touch path.
- Keep a negative test with compatibility disabled so every native-touch dependency remains known.

## Owning touch index

```gdscript
var _touch_index := -1

func handle_touch(event: InputEventScreenTouch) -> void:
	if event.device == InputEvent.DEVICE_ID_EMULATION:
		return
	if event.canceled:
		if event.index == _touch_index:
			end_drag(event.position)
			_touch_index = -1
		return
	if event.pressed and _touch_index < 0:
		_touch_index = event.index
		begin_drag(event.position)
	elif event.index == _touch_index and not event.pressed:
		end_drag(event.position)
		_touch_index = -1

func handle_drag(event: InputEventScreenDrag) -> void:
	if event.device != InputEvent.DEVICE_ID_EMULATION and event.index == _touch_index:
		update_drag(event.position, event.relative)
```

For multi-touch, store state by `index`. Do not reuse the single-pointer helper for pinch, rotation,
or simultaneous controls. Cancel owned touches on window focus loss, node hide or exit, modal
replacement, and pointer-owner changes.

## Coordinate units

| Property | Unit | Use |
|---|---|---|
| `position` | viewport-local in `_input`; receiving-Control-local in `_gui_input` | hit testing and transforms |
| `relative` | content-scaled coordinates | UI content movement |
| `velocity` | content-scaled coordinates per second | UI kinetic scrolling |
| `screen_relative` | unscaled screen pixels | physical thresholds and aiming |
| `screen_velocity` | unscaled screen pixels per second | physical gesture velocity |

Do not compare a scaled value with a threshold authored in screen pixels.

## Touch capability

Build capability from trusted signals:

1. `DisplayServer.is_touchscreen_available()` at startup.
2. Any physical `InputEventScreenTouch` or `InputEventScreenDrag` at runtime.
3. A trusted platform profile only when the product explicitly enables and physically verifies
   native touch pass-through.

A physical event is authoritative when the startup probe reports false. Treat capability as
monotonic unless hot-plug removal is a supported product feature. If capability can fall, update
touch-only UI, active gestures, and virtual-keyboard state together.

Use the platform SDK's explicit Steam Deck query. Do not use screen resolution, operating system,
controller name, or environment variables. A Steam Deck profile identifies the environment; it does
not prove that native touch events reach the viewport.

## Touch-only UI

Critical actions need a visible path without Esc, function keys, hover, or right-click. Provide:

- visible back and settings controls;
- a visible report/help path when supported;
- safe-area-aware placement;
- a persistent fallback when a scene has no local entry;
- automatic suppression of the fallback when a visible scene-owned entry exists.

When a touch-only subtree is hidden without changing layout, suppress all input paths:

- release focus from descendants;
- `mouse_filter = MOUSE_FILTER_IGNORE`;
- `mouse_behavior_recursive = MOUSE_BEHAVIOR_DISABLED`;
- `focus_mode = FOCUS_NONE`;
- `focus_behavior_recursive = FOCUS_BEHAVIOR_DISABLED`;
- disable `_input`, `_shortcut_input`, `_unhandled_key_input`, and `_unhandled_input` processing.

Snapshot and restore the authored state. Suppress dynamically added descendants after `_ready`, and
restore a detached descendant before it enters another parent.

## Virtual keyboard

```gdscript
static func _control_screen_rect(control: Control) -> Rect2:
	var xform := control.get_screen_transform()
	var points := PackedVector2Array([
		xform * Vector2.ZERO,
		xform * Vector2(control.size.x, 0.0),
		xform * control.size,
		xform * Vector2(0.0, control.size.y),
	])
	var rect := Rect2(points[0], Vector2.ZERO)
	for point in points:
		rect = rect.expand(point)
	return rect

static func show_native_for(control: Control) -> bool:
	var text := ""
	if control is LineEdit:
		var line_edit := control as LineEdit
		line_edit.virtual_keyboard_show_on_focus = false
		text = line_edit.text
	elif control is TextEdit:
		var text_edit := control as TextEdit
		text_edit.virtual_keyboard_show_on_focus = false
		text = text_edit.text
	else:
		return false
	if not DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD):
		return false
	DisplayServer.virtual_keyboard_show(
		text,
		_control_screen_rect(control),
		DisplayServer.KEYBOARD_TYPE_DEFAULT
	)
	return true
```

- When a helper owns showing and hiding, set the target `LineEdit` or `TextEdit`
  `virtual_keyboard_show_on_focus` to `false` so the built-in path cannot open a second keyboard.
- Bind `focus_entered` to show.
- Bind `focus_exited` and `LineEdit.text_submitted` to hide.
- Do not open the OSK for active physical keyboard/mouse typing.
- Select an appropriate keyboard type for email, numeric, password, or URL fields.
- Preserve selection and caret where the platform API supports it.
- Lift the focused field using `virtual_keyboard_get_height()` and safe-area data.
- If `show_native_for()` returns `false`, route through a platform floating-keyboard adapter
  or a product on-screen keyboard. This is required on targets where the display server has no native
  OSK even though the device is touch-reachable.
- On mobile web, enable the export preset's virtual-keyboard option and acquire focus synchronously
  inside the user gesture.

`LineEdit.virtual_keyboard_show_on_focus` and `TextEdit.virtual_keyboard_show_on_focus` may provide
the native default. Use a helper when device gating, keyboard type, control rectangle, safe-area
movement, or explicit hide behavior differs from that default.

## Physical-device checks

- Windows touchscreen native tap and drag.
- Steam Deck SteamOS native tap, drag, and platform profile.
- Compatibility mouse arriving before the original screen-touch event.
- Native touch with mouse emulation disabled.
- One physical contact produces one action.
- Touch drag is not reclaimed by an emulated mouse event.
- Second finger cannot end the first finger's drag.
- Window focus loss, node hide, and modal replacement end the owning touch.
- OSK opens, does not cover the field, and closes on submit or focus exit.
- OSK screen rectangle is correct under stretch, window offsets, and scaled controls.
- Platform or product OSK fallback works when the display-server feature is absent.
- Hardware keyboard attached to a touch device does not force the OSK.
