---
name: godot-test-harness
description: |
  Write a SceneTree test script — C# (test/TestXxx.cs) or GDScript (test/test_xxx.gd) — that loads a scene under test and verifies a goal, for use with the capture/movie-writer flow. Use when you need automated visual verification of a scene or feature.
---

# Test Harness & Visual Verification

Write a SceneTree test script that loads the scene under test and verifies the task's goal. C#: `test/TestXxx.cs` (e.g., `test/TestT3.cs`); GDScript: `test/test_xxx.gd` (e.g., `test/test_t3.gd`). Do NOT call `Quit()` — the movie writer handles exit.

## Language: C# (.NET) or GDScript?

Detect the project language before writing the test. A `.csproj`/`.sln` file, or a `[dotnet]` section in `project.godot`, means the project is **C# (.NET)**; otherwise it is **GDScript**. The test logic is identical across both languages — load the scene, advance frames, assert, let the movie writer exit — only the syntax and the build prerequisite differ. Pick the path that matches the project and follow the language-labeled notes below.

## SceneTree Script Contract

Tests must extend `SceneTree` (not Node). Key details shared by both languages:
- Setup goes in the initialize hook, **not** a `_ready` — `_Initialize()` (C#) / `_initialize()` (GDScript)
- The per-frame process hook returns `false` to keep running
- Camera needs `current = true` to activate (`_cam.Current = true` in C#)

**[C# only]**
- `_Process(double delta)` returns `bool` — return `false` to keep running
- Must be `public partial class`
- Must run `dotnet build` before capture

**(GDScript)**
- Use `func _initialize() -> void:` for setup
- Use `func _process(delta) -> bool:` returning `false` to keep running
- No `public partial class` — a plain script `extends SceneTree` is enough
- **No `dotnet build` step** — there is nothing to compile. Run the capture directly against the script:

```bash
godot --headless --script test/test_xxx.gd ...
```

## Console Assertions

The test harness stdout is captured alongside screenshots. Print `ASSERT PASS/FAIL: ...` lines to verify behavioral properties that are hard to judge visually (exact positions, velocities, state changes). After capture, check stdout for any `ASSERT FAIL` lines — these must be fixed before the task is complete.

**(C# / .NET)**

```csharp
GD.Print("ASSERT PASS/FAIL: ...");
```

**(GDScript)**

```gdscript
print("ASSERT PASS/FAIL: ...")
```

## Simulated Input

For tests needing player input, use a Timer to trigger actions. This works in both languages.

**(C# / .NET)**

```csharp
var timer = new Timer();
timer.WaitTime = 1.0;
timer.OneShot = true;
timer.Timeout += () => Input.ActionPress("move_forward");
Root.AddChild(timer);
timer.Start();
```

**(GDScript)**

```gdscript
var timer := Timer.new()
timer.wait_time = 1.0
timer.one_shot = true
timer.timeout.connect(func(): Input.action_press("move_forward"))
root.add_child(timer)
timer.start()
```

### Sustained movement — use closed-loop steering (default)

Open-loop input (timed press/release sequences) causes visible drift, edge-sticking, and tightening spirals as per-frame errors compound. **Default to closed-loop waypoint steering:** read the actual position each frame and steer toward the next waypoint. This applies to all tests with sustained movement, not just presentation scripts.
