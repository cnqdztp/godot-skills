# Focus, modal routing, and navigation repeat

## Modal stack

Each blocking screen exposes:

- root `Control`;
- default focus `Control`;
- cancel callback;
- blocking state.

When the stack changes:

1. Save the current focus owner as a `WeakRef` for the newly opened screen.
2. Set the top screen root to `FOCUS_BEHAVIOR_ENABLED`.
3. Set lower blocking roots to `FOCUS_BEHAVIOR_DISABLED`.
4. Leave descendant `focus_mode` values unchanged.
5. In navigation mode, focus the saved valid control or the screen default.
6. On close, restore the saved lower-screen focus when it is still valid.

Validate with:

```gdscript
func is_focus_candidate(control: Control, root: Control) -> bool:
	return control != null \
		and is_instance_valid(control) \
		and control != root \
		and root.is_ancestor_of(control) \
		and control.is_visible_in_tree() \
		and control.get_focus_mode_with_override() == Control.FOCUS_ALL
```

## First navigation event

The first keyboard or gamepad direction must both establish navigation mode and perform navigation.

1. Detect navigation intent in `_input`.
2. Repair top-screen focus synchronously.
3. Do not mark the event handled.
4. Let the same `ui_*` event continue to native GUI focus traversal.

Emit navigation intent on every qualifying physical event, even when device and mode did not change.
This repairs focus lost after a hidden control, freed node, scene mutation, or foreign `grab_focus()`.

Deferred focus remains appropriate when a screen or control is not visible in the tree yet. It is
not appropriate for the already-dispatching first navigation event.

## Navigation graph

- Set `focus_neighbor_top/bottom/left/right` for authored controls.
- Rebuild paths after dynamic rows or grid cells are created or removed.
- Loop or clamp list ends explicitly.
- Use deterministic tie-breaking for diagonal stick input.
- In `ScrollContainer`, observe focus changes and call `ensure_control_visible()`.
- Wait one process frame before ensuring a control that was added during the current frame.
- Do not implement a virtual cursor for ordinary menus.

## Repeat

Native input supplies the first direction edge. Custom repeat starts after a delay.

```gdscript
const REPEAT_DELAY := 0.5
const REPEAT_INTERVAL := 0.1

func push_ui_repeat(action: StringName) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = true
	event.strength = 1.0
	get_viewport().push_input(event)
```

- Do not synthesize the original first edge.
- Emit at most one repeat step per rendered frame.
- Reset elapsed repeat on release, direction change, device change, interaction-mode change, modal
  change, focus repair, pause transition, and disconnect.
- Use `Viewport.push_input()` for GUI-only repeat.
- Use press/release pairs when injecting global action state.
- Do not rely on operating-system keyboard echo timing.

## Confirm routing

A physical confirm may match both `ui_accept` and a gameplay `confirm` action. Compute one boolean
edge before emitting custom signals.

Focused custom controls inside complex containers may not receive the expected `_gui_input` accept
after native focus handling. In that case:

1. Emit one pre-GUI semantic confirm signal from the input manager.
2. Let the current modal or list owner verify that the focus owner is its descendant.
3. Activate once.
4. Mark the event handled only after activation.
5. Keep ordinary buttons on native `pressed` or `_gui_input` paths.

Do not broadcast a second confirm to every focused control.

## Cancel and menu

When one physical key maps to both cancel and menu, use one ordered router:

1. GUI controls receive the event first.
2. Report/help route may consume it.
3. Top modal cancel route may consume it.
4. Menu route runs only when no modal consumed cancel.
5. Call `set_input_as_handled()` after a route returns consumed.

Use the same routing function from `_shortcut_input` and from the synthetic-event fallback path.
Ignore key echo for discrete actions. Do not poll `is_action_just_pressed()` in several screens.

## Visual ownership

Keep raw state separate from rendered state:

```gdscript
var visual_highlight := hovered if interaction_mode == InteractionMode.POINTER else has_focus()
```

- Mouse hover renders only in pointer mode.
- Keyboard and pad focus render only in navigation mode.
- Touch press may render pressed feedback but no retained hover.
- Changing ownership clears transient hover and pressed state.
- Logical focus may remain while pointer mode hides its visual treatment.
- Do not move the OS cursor to clear hover.

## Tests

- First direction changes mode and moves focus once.
- Repeated direction with unchanged mode repairs missing focus.
- Pointer mode never auto-grabs menu focus.
- Top modal is the only focusable modal subtree.
- Nested modal close restores the exact lower control.
- Hidden or freed focus falls back to a visible valid control.
- Repeat delay and interval are exact and a stalled frame moves only once.
- Pointer, keyboard navigation, and pad navigation never render simultaneous hover and focus.
- Cancel and menu cannot both activate from one event.
- A focused custom row receives one confirm, not zero or two.
