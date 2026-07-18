# Runtime rebinding

## Binding layers

Use `InputMap` for fixed default bindings. Add a runtime binding layer when the product supports
rebinding, cloud profiles, per-player layouts, or platform-owned controller configuration.

Two valid persistence models:

1. Mutate runtime `InputMap` events and serialize a typed copy of the changed bindings.
2. Keep physical actions fixed and translate them through a user binding dictionary to semantic
   actions.

Choose one model for a given device and semantic-action path. Do not leave the same physical input in
runtime `InputMap` while also translating it to the same semantic action; that produces duplicate
edges and ambiguous release ownership.

Do not edit `project.godot` at runtime. Do not assume runtime `InputMap` changes persist after exit.

## Keyboard identity

Choose identity by action type:

| Property | Use |
|---|---|
| `physical_keycode` | gameplay position such as WASD |
| `keycode` | layout-aware shortcut identity |
| `key_label` | localized prompt text |

Record modifier state and left/right location when relevant. Ignore `echo`. Reject or separately
route reserved system shortcuts and text-composition events.

## Gamepad identity

Store:

- button or axis type;
- button index or axis index;
- axis direction;
- actuation threshold;
- semantic action;
- optional device class, not a transient device ID.

Capture the press or threshold-crossing edge. Wait for neutral before accepting another binding.
Release or neutralize the old held source before applying the new map, then wait for the captured
control to return neutral. Do not hardcode controller device `0`.

## Conflicts

For swap behavior:

1. Read the rebinding action's old physical binding.
2. Find the action currently using the requested binding in the same context.
3. Assign that action the old binding.
4. Assign the requested binding to the rebinding action.
5. Save both changes atomically.

Keep UI-navigation escape bindings reachable. Require an explicit confirmation before removing the
last binding for confirm, cancel, or menu.

## Translation

```gdscript
var _injecting := false
var _digital_sources: Dictionary = {} # action -> {source_id: true}

func set_semantic_source(action: StringName, source_id: StringName, pressed: bool) -> void:
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
	_injecting = true
	var event := InputEventAction.new()
	event.action = action
	event.pressed = is_pressed
	event.strength = 1.0 if is_pressed else 0.0
	Input.parse_input_event(event)
	_injecting = false
```

- Give each physical or platform binding a stable source ID inside the translator.
- Emit release for every press. Releasing one source must not release an action still held by another.
- Keep an active physical-to-semantic table so disconnect and context changes can release held state.
- Do not translate an `InputEventAction` produced by the translator.
- Use a fresh event for every edge.
- Aggregate analog sources separately and define the ownership rule before preserving strength.

## Persistence

Persist typed data, not localized labels:

```json
{
  "version": 1,
  "keyboard": {
    "move_left": {"kind": "physical_key", "code": 65}
  },
  "gamepad": {
    "confirm": {"kind": "button", "button": 0}
  }
}
```

- Version the format.
- Merge new default actions during migration.
- Remove bindings for deleted actions.
- Validate values before applying.
- Keep a reset-to-default operation.
- Save after a complete swap, never halfway through it.

## Platform ownership

Disable in-game controller rebinding only while a platform input layer owns the active controller and
its action path is valid. Platform client initialization without an active input handle is not
ownership. Keyboard rebinding may remain game-owned while the platform owns controller bindings.

## Tests

- Physical-key versus layout-aware key behavior.
- Modifier and key-location capture.
- Button and signed-axis capture.
- Reserved binding rejection.
- Conflict swap and atomic persistence.
- Press/release symmetry.
- Two sources holding one action; releasing either source alone keeps the action held.
- Disconnect while a translated action is held.
- Rebind while the old control is held, followed by a neutral transition.
- Context switch while an axis is actuated.
- Save migration after adding and removing actions.
- Steam initialized with no owning handle retains native controller rebinding.
