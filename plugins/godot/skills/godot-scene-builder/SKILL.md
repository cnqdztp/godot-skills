---
name: godot-scene-builder
description: |
  Generate any Godot 4 .tscn scene file programmatically with a headless SceneTree builder script (C# / .NET or GDScript): build the node hierarchy in code, set the Owner chain, validate, and Pack/save. An agent has no Godot editor, so a builder script is the ONLY way to author or rebuild a scene — use this for EVERY scene type: 2D game scenes (Node2D, Sprite2D, AnimatedSprite2D, CharacterBody2D/Area2D + CollisionShape2D, Camera2D, TileMapLayer), 3D game scenes (Node3D, MeshInstance3D, physics bodies, Camera3D, GLB), and mixed scenes. For the Control/UI layer specifically, pair with godot-ui-tscn.
---

# Scene Generation

Scene builders are scripts that run headless in Godot 4 to produce `.tscn` files programmatically. They are NOT runtime scripts — they run once at build-time and exit.

## Choosing the node family (the #1 decision — get this right first)

Before building any scene, pick the node family by **RESPONSIBILITY**, not by "is it on screen". This is how shipped Godot games actually decide (verified across a C# card game and a GDScript point-and-click):

- **Control family** — `Control`, the `*Container` nodes, `Panel`, `TextureRect`, `NinePatchRect`, `Label`/`RichTextLabel`, `ColorRect`. Use for **anything that anchors/lays out, is read or clicked, or composes other nodes.** This is the default for ALL UI (menus, HUD, panels, popups, list rows), and in layout-driven 2D games even the board/card/entity *wrappers* are often Control. Static art *inside* a Control layout is **`TextureRect`** (never `Sprite2D`); stretchable frames are `NinePatchRect`; full-screen dimmers/shader rects are `ColorRect`.
- **Node2D family** — `Node2D`, `Sprite2D`, `AnimatedSprite2D`, `GPUParticles2D`, `Line2D`, `CanvasGroup` (batches/composites its 2D children for unified blending/shaders), `Marker2D`, plus `CharacterBody2D`/`Area2D`/`CollisionShape2D`, `Camera2D`, `TileMapLayer`. Use for **free-transform world content**: art you place/move/rotate in world space, skeletal animation (e.g. Spine), particle/VFX rigs, tile worlds, and 2D physics/movement. Use `Sprite2D` (not `TextureRect`) only when the art owns its own transform.
- **Node3D family** — `Node3D`, `MeshInstance3D`, `Camera3D`, the 3D physics/light nodes. Use when the game has a real 3D space.

**Decisive test:** does it hit-test / anchor / hold text? → **Control**. Is it transformed-animated art, particles, Spine, a tile world, or a moving/colliding body? → **Node2D**. Does it live in a 3D space? → **Node3D**.

**Split entities that need both.** When one on-screen thing needs layout/logic/HUD AND free-transform art (e.g. a combatant), build it as TWO nodes — a Control logic/hitbox/HUD node and a separate `Node2D` art node (Sprite/Spine) — joined at runtime and bridged by **`Marker2D`** anchor points the art scene exposes (real pattern: a Control `creature.tscn` + a `Node2D` `creature_visuals/*.tscn` exposing `CenterPos`/`IntentPos` markers).

**Quarantine the non-primary family in a `SubViewport`.** Do NOT parent 3D nodes under 2D/Control nodes or vice-versa. If a mostly-2D game needs a 3D flourish, render the 3D rig in a `SubViewport` and composite it back as a `Sprite2D`/`TextureRect`; if a 3D game needs a 2D mini-world (an in-game screen/map), render it in a `SubViewport`. **UI always sits on a `CanvasLayer` above the world** so it ignores the game camera.

**Root-node conventions (observed in shipped games):**

| Scene kind | Root |
|---|---|
| game world — free placement / physics / tiles | `Node2D` (2D) or `Node3D` (3D) |
| per-screen / per-mode manager in a UI-driven game | `Control` |
| HUD / menu / panel / popup / list row | `Control` (on a `CanvasLayer` overlay) |
| reusable art rig (sprite / Spine / VFX) | `Node2D` |
| app / bootstrap root | `Node`/`Control` (2D game) or `Node3D` (3D game) |

When in doubt for a **game world**, root it `Node2D`/`Node3D`; for **anything the player reads or clicks**, root it `Control`. A Control-heavy UI is correct — the mistake is putting *free-transform gameplay art* into Control containers (a `Container` overwrites its children's `position`/`scale` every relayout, so world objects can't be freely placed — see godot-quirks).

## Language: C# (.NET) or GDScript?

Detect the project's language before writing a builder:

- **C# (.NET)** if the project has a `.csproj`/`.sln` file, or `project.godot` contains a `[dotnet]` section. C# builders need `.NET 9+`.
- **GDScript** otherwise.

The technique is **identical** in both languages — build the hierarchy in code, set the owner chain on every descendant, then `Pack()` + save. Only the syntax and engine bindings differ. Throughout this skill, C#-specific material is labeled `[C# only]` or `(C# / .NET)`, and each has a matching `(GDScript)` block.

## Scene Output Requirements

Generate a single builder file that:
1. Subclasses `SceneTree` — `[C# only]` `public partial class BuildXxx : SceneTree` (must be `partial`); `(GDScript)` `extends SceneTree`
2. Implements the entry point — `[C# only]` `public override void _Initialize()`; `(GDScript)` `func _initialize()` (lowercase, no `override`)
3. Builds complete node hierarchy with all properties set
4. Sets `Owner` on ALL descendants for serialization
5. Attaches scripts from STRUCTURE.md — `[C# only]` `SetScript(GD.Load(...))`; `(GDScript)` `node.set_script(load(...))`
6. Saves scene using `PackedScene.Pack()` + `ResourceSaver.Save()` (`pack()` / `ResourceSaver.save()` in GDScript)
7. Calls `Quit()` (`quit()` in GDScript) when done

## Owner Chain (CRITICAL)

**MUST set the owner on every descendant ONCE at the end**, after all nodes are added.

**(C# / .NET)** — call `SetOwnerOnNewNodes(root, root)`:
```csharp
// At end of _Initialize(), AFTER all AddChild() calls:
SetOwnerOnNewNodes(root, root);

private void SetOwnerOnNewNodes(Node node, Node sceneOwner)
{
    foreach (var child in node.GetChildren())
    {
        child.Owner = sceneOwner;
        if (string.IsNullOrEmpty(child.SceneFilePath))
        {
            // Node created with new() — recurse into children
            SetOwnerOnNewNodes(child, sceneOwner);
        }
        // else: instantiated scene (GLB/TSCN) — don't recurse, keeps as reference
    }
}
```

**(GDScript)** — same logic, recurse only into nodes you built with `.new()`:
```gdscript
# At end of _initialize(), AFTER all add_child() calls:
_set_owner_on_new_nodes(root, root)

func _set_owner_on_new_nodes(node: Node, scene_owner: Node) -> void:
    for child in node.get_children():
        child.owner = scene_owner
        if child.scene_file_path.is_empty():
            # Node created with .new() — recurse into children
            _set_owner_on_new_nodes(child, scene_owner)
        # else: instantiated scene (GLB/TSCN) — don't recurse, keeps as reference
```

### Post-Pack Validation

Call after `packed.Pack(root)` to verify no nodes were silently dropped.

**(C# / .NET):**
```csharp
private bool ValidatePackedScene(PackedScene packed, int expectedCount, string scenePath)
{
    var testInstance = packed.Instantiate();
    int actual = CountNodes(testInstance);
    testInstance.Free();
    if (actual < expectedCount)
    {
        GD.PushError($"Pack validation failed for {scenePath}: expected {expectedCount} nodes, got {actual} — nodes were dropped during serialization");
        return false;
    }
    return true;
}
```

Use in the scene template between `packed.Pack(root)` and `ResourceSaver.Save()`. **Gate the save on the validation result:**
```csharp
    int count = CountNodes(root);
    var err = packed.Pack(root);
    if (err != Error.Ok)
    {
        GD.PushError($"Pack failed: {err}");
        Quit(1);
        return;
    }
    if (!ValidatePackedScene(packed, count, "res://{output_path}.tscn"))
    {
        Quit(1);
        return;
    }
```

**(GDScript):**
```gdscript
func _validate_packed_scene(packed: PackedScene, expected_count: int, scene_path: String) -> bool:
    var test_instance := packed.instantiate()
    var actual := _count_nodes(test_instance)
    test_instance.free()
    if actual < expected_count:
        push_error("Pack validation failed for %s: expected %d nodes, got %d — nodes were dropped during serialization" % [scene_path, expected_count, actual])
        return false
    return true
```

Use between `packed.pack(root)` and `ResourceSaver.save()`. **Gate the save on the validation result:**
```gdscript
    var count := _count_nodes(root)
    var err := packed.pack(root)
    if err != OK:
        push_error("Pack failed: %s" % err)
        quit(1)
        return
    if not _validate_packed_scene(packed, count, "res://{output_path}.tscn"):
        quit(1)
        return
```

**WRONG patterns** (cause missing nodes in saved .tscn):
```csharp
// WRONG: Setting owner only on direct children, forgetting grandchildren
terrain.Owner = root;  // Terrain's children (Mesh, Collision) have NO owner!

// WRONG: Calling helper on containers instead of root
SetOwnerOnNewNodes(trackContainer, root);  // trackContainer itself has NO owner!
```

**GLB OWNERSHIP BUG** — Never use unconditional recursion. If you recurse into instantiated GLB models, ALL internal mesh/material nodes get serialized inline as text, causing 100MB+ .tscn files.

## Common Node Compositions

**2D game world** — a `Node2D` root with a moving/colliding actor, a frame-animated prop, a trigger area, and an anchor. This is the copyable template for a 2D game scene; for the HUD over it, build a separate `Control` tree on a `CanvasLayer` (see godot-ui-tscn).

**(GDScript)**
```gdscript
var world := Node2D.new()
world.name = "World"

var player := CharacterBody2D.new()           # moving, colliding actor
player.name = "Player"
var sprite := Sprite2D.new()                  # art that owns its transform → Sprite2D, not TextureRect
sprite.texture = load("res://art/player.png")
player.add_child(sprite)
var col := CollisionShape2D.new()
var shape := RectangleShape2D.new(); shape.size = Vector2(24, 32)
col.shape = shape
player.add_child(col)
var cam := Camera2D.new()                      # child of the actor → follows it
cam.zoom = Vector2(2, 2)
player.add_child(cam)
world.add_child(player)

var coin := AnimatedSprite2D.new()             # frame animation
coin.sprite_frames = load("res://art/coin_frames.tres")
coin.position = Vector2(120, 0)
world.add_child(coin)

var trigger := Area2D.new()                    # clickable / overlap region
var tcol := CollisionShape2D.new()
var circle := CircleShape2D.new(); circle.radius = 16.0
tcol.shape = circle
trigger.add_child(tcol)
world.add_child(trigger)

var spawn := Marker2D.new()                    # anchor point (NOT the deprecated Position2D)
spawn.name = "SpawnPoint"
spawn.position = Vector2(0, -40)
world.add_child(spawn)
```

**(C# / .NET)** — same structure: `new Node2D()` root; `Sprite2D.Texture = GD.Load<Texture2D>(...)`; `CharacterBody2D` with a `CollisionShape2D` whose `Shape = new RectangleShape2D { Size = new Vector2(24,32) }`; `AnimatedSprite2D.SpriteFrames = GD.Load<SpriteFrames>(...)`; `Area2D` + `CircleShape2D`; `Camera2D` as a child of the actor; `Marker2D` anchors. Tile worlds use a `TileMapLayer` (Godot 4.3+) with a `TileSet`.

**3D Physics Object:**
```csharp
var body = new RigidBody3D();
var collision = new CollisionShape3D();
var mesh = new MeshInstance3D();
var shape = new BoxShape3D();
shape.Size = new Vector3(1, 1, 1);
collision.Shape = shape;
body.AddChild(collision);
body.AddChild(mesh);
```

**3D Camera Rig:**
```csharp
var pivot = new Node3D();
var camera = new Camera3D();
camera.Position = new Vector3(0, 0, 5);
pivot.AddChild(camera);
```

## Script Attachment (in Scenes)

**[C# only] `SetScript()` disposes the C# wrapper** — after calling `SetScript()`, the local variable is dead. Build the full hierarchy first, set scripts last. For the root node, use a temp parent to re-obtain the reference.

```csharp
// Set scripts AFTER building the full hierarchy — SetScript() invalidates the C# wrapper.
// For non-root nodes, just call it last (no further use of the variable needed):
playerNode.SetScript(GD.Load("res://scripts/PlayerController.cs"));

// For the root node, use a temp parent pattern (see Scene Template below).
```

**(GDScript)** — `set_script()` does NOT dispose anything; a script is just a resource reference, so the variable stays valid and the temp-parent dance is unnecessary. Attach scripts wherever convenient:

```gdscript
player_node.set_script(load("res://scripts/player_controller.gd"))
# player_node is still valid here — keep using it freely.
```

## Asset Loading

**3D models (GLB):**
```csharp
var modelScene = GD.Load<PackedScene>("res://assets/glb/car.glb");
var model = modelScene.Instantiate();
model.Name = "CarModel";

// Measure for scaling — find MeshInstance3D (GLB structure varies, may be nested)
var meshInst = FindMeshInstance(model);
var aabb = meshInst != null ? meshInst.GetAabb() : new Aabb(Vector3.Zero, Vector3.One);

// Scale to target size (e.g., car should be ~2 units long)
float targetLength = 2.0f;
float scaleFactor = targetLength / aabb.Size.X;
model.Set("scale", Vector3.One * scaleFactor);
((Node3D)model).Position = new Vector3(0, -aabb.Position.Y * scaleFactor, 0);

parentNode.AddChild(model);

private MeshInstance3D FindMeshInstance(Node node)
{
    if (node is MeshInstance3D mi)
        return mi;
    foreach (var child in node.GetChildren())
    {
        var found = FindMeshInstance(child);
        if (found != null)
            return found;
    }
    return null;
}
```

**GLB orientation:** Imported models often face the wrong axis. After instantiating, check the AABB: the longest dimension tells you which local axis the model faces. If a car's AABB is longest on Z but your game expects forward=negative Z, no rotation needed; if longest on X, rotate 90 degrees. For animals/characters, the forward-facing axis must align with the direction of movement — an animal moving sideways is a clear bug. Verify this in screenshots: if the bounding box or silhouette doesn't match the movement direction, fix the rotation.

**Collision shapes for 3D models:** Always use simple primitives (BoxShape3D, SphereShape3D, CapsuleShape3D). Never use `CreateConvexShape()` or `CreateTrimeshShape()` on imported GLB meshes — causes <1 FPS on high-poly models (100k+ triangles).

```csharp
// Box from AABB — use this for all imported models
var box = new BoxShape3D();
box.Size = aabb.Size * ((Node3D)model).Scale;
collisionShape.Shape = box;
```

**Textures (PNG):**
```csharp
var mat = new StandardMaterial3D();
mat.AlbedoTexture = GD.Load<Texture2D>("res://assets/img/grass.png");
meshInstance.SetSurfaceOverrideMaterial(0, mat);
```

**Texture UV tiling:** For large surfaces, scale UVs to avoid stretched textures:
```csharp
mat.Uv1Scale = new Vector3(10, 10, 1);  // Tile every 2m on a 20m floor
```

## Child Scene Instancing

```csharp
var carScene = GD.Load<PackedScene>("res://scenes/car.tscn");
var car = carScene.Instantiate<Node3D>();
car.Name = "PlayerCar";
car.Position = new Vector3(0, 0, 5);
root.AddChild(car);
car.Owner = root;  // Child internals already have owner — just set on instance root
```

## Shared Base Class

All scene builders inherit from a shared `SceneBuilderBase` instead of `SceneTree`. This eliminates 30+ lines of repeated boilerplate per builder. Create this file once during scaffold.

**(C# / .NET) — `scenes/SceneBuilderBase.cs`:**
```csharp
using Godot;

public partial class SceneBuilderBase : SceneTree
{
    protected void SetOwnerOnNewNodes(Node node, Node sceneOwner)
    {
        foreach (var child in node.GetChildren())
        {
            child.Owner = sceneOwner;
            if (string.IsNullOrEmpty(child.SceneFilePath))
                SetOwnerOnNewNodes(child, sceneOwner);
        }
    }

    protected int CountNodes(Node node)
    {
        int total = 1;
        foreach (var child in node.GetChildren())
            total += CountNodes(child);
        return total;
    }

    protected bool ValidatePackedScene(PackedScene packed, int expectedCount, string scenePath)
    {
        var testInstance = packed.Instantiate();
        int actual = CountNodes(testInstance);
        testInstance.Free();
        if (actual < expectedCount)
        {
            GD.PushError($"Pack validation failed for {scenePath}: expected {expectedCount} nodes, got {actual}");
            return false;
        }
        return true;
    }

    protected void PackAndSave(Node rootNode, string outputPath)
    {
        SetOwnerOnNewNodes(rootNode, rootNode);
        int count = CountNodes(rootNode);

        var packed = new PackedScene();
        var err = packed.Pack(rootNode);
        if (err != Error.Ok)
        {
            GD.PushError($"Pack failed: {err}");
            Quit(1);
            return;
        }
        if (!ValidatePackedScene(packed, count, outputPath))
        {
            Quit(1);
            return;
        }
        err = ResourceSaver.Save(packed, outputPath);
        if (err != Error.Ok)
        {
            GD.PushError($"Save failed: {err}");
            Quit(1);
            return;
        }
        GD.Print($"BUILT: {count} nodes → {outputPath}");
        Quit(0);
    }
}
```

**(GDScript) — `scenes/scene_builder_base.gd`:**
```gdscript
extends SceneTree
class_name SceneBuilderBase

func _set_owner_on_new_nodes(node: Node, scene_owner: Node) -> void:
    for child in node.get_children():
        child.owner = scene_owner
        if child.scene_file_path.is_empty():
            _set_owner_on_new_nodes(child, scene_owner)

func _count_nodes(node: Node) -> int:
    var total := 1
    for child in node.get_children():
        total += _count_nodes(child)
    return total

func _validate_packed_scene(packed: PackedScene, expected_count: int, scene_path: String) -> bool:
    var test_instance := packed.instantiate()
    var actual := _count_nodes(test_instance)
    test_instance.free()
    if actual < expected_count:
        push_error("Pack validation failed for %s: expected %d nodes, got %d" % [scene_path, expected_count, actual])
        return false
    return true

func _pack_and_save(root_node: Node, output_path: String) -> void:
    _set_owner_on_new_nodes(root_node, root_node)
    var count := _count_nodes(root_node)

    var packed := PackedScene.new()
    var err := packed.pack(root_node)
    if err != OK:
        push_error("Pack failed: %s" % err)
        quit(1)
        return
    if not _validate_packed_scene(packed, count, output_path):
        quit(1)
        return
    err = ResourceSaver.save(packed, output_path)
    if err != OK:
        push_error("Save failed: %s" % err)
        quit(1)
        return
    print("BUILT: %d nodes → %s" % [count, output_path])
    quit(0)
```

## Scene Template

**(C# / .NET):** the temp-parent dance below is needed because `SetScript()` on the root disposes its wrapper — see the `[C# only]` note in Script Attachment.
```csharp
using Godot;

public partial class Build{SceneName} : SceneBuilderBase
{
    public override void _Initialize()
    {
        GD.Print("Generating: {scene_name}");

        var temp = new Node();
        var root = new {RootNodeType}();
        root.Name = "{SceneName}";
        temp.AddChild(root);

        // ... build node hierarchy, AddChild(), set properties ...

        // Set scripts LAST (SetScript disposes C# wrapper — see the godot-quirks skill)
        // root.SetScript(GD.Load("res://scripts/{Script}.cs"));

        // Re-obtain root (old wrapper is disposed after SetScript)
        var rootNode = temp.GetChild(0);
        temp.RemoveChild(rootNode);
        temp.Free();

        PackAndSave(rootNode, "res://{output_path}.tscn");
    }
}
```

Concrete C# example — a `CharacterBody3D` root named "Player":
```csharp
using Godot;

public partial class BuildPlayer : SceneBuilderBase
{
    public override void _Initialize()
    {
        var temp = new Node();
        var root = new CharacterBody3D();
        root.Name = "Player";
        temp.AddChild(root);

        var mesh = new MeshInstance3D();
        mesh.Name = "Mesh";
        mesh.Mesh = new CapsuleMesh();
        root.AddChild(mesh);

        var collision = new CollisionShape3D();
        collision.Name = "Collision";
        collision.Shape = new CapsuleShape3D();
        root.AddChild(collision);

        // Set script LAST (SetScript disposes the C# wrapper):
        root.SetScript(GD.Load("res://scripts/player_controller.cs"));

        // Re-obtain root via the temp parent (old wrapper disposed):
        var rootNode = temp.GetChild(0);
        temp.RemoveChild(rootNode);
        temp.Free();

        PackAndSave(rootNode, "res://scenes/player.tscn");
    }
}
```

**(GDScript):** no temp-parent dance — `set_script()` keeps the variable valid, so attach scripts inline and build straight through. Same `CharacterBody3D` "Player" example:
```gdscript
extends SceneBuilderBase

func _initialize() -> void:
    print("Generating: player")

    var root := CharacterBody3D.new()
    root.name = "Player"

    var mesh := MeshInstance3D.new()
    mesh.name = "Mesh"
    mesh.mesh = CapsuleMesh.new()
    root.add_child(mesh)

    var collision := CollisionShape3D.new()
    collision.name = "Collision"
    collision.shape = CapsuleShape3D.new()
    root.add_child(collision)

    # set_script() does NOT dispose anything — root stays valid:
    root.set_script(load("res://scripts/player_controller.gd"))

    _pack_and_save(root, "res://scenes/player.tscn")
```

Concrete **2D** worked example — same flow, a `Node2D` world root with 2D nodes. **(GDScript):**
```gdscript
extends SceneBuilderBase

func _initialize() -> void:
    var root := Node2D.new()
    root.name = "Level"

    var player := CharacterBody2D.new()
    player.name = "Player"
    var sprite := Sprite2D.new()
    sprite.name = "Sprite"
    sprite.texture = load("res://art/player.png")
    player.add_child(sprite)
    var col := CollisionShape2D.new()
    col.name = "Collision"
    var shape := RectangleShape2D.new(); shape.size = Vector2(24, 32)
    col.shape = shape
    player.add_child(col)
    var cam := Camera2D.new()
    cam.name = "Camera"
    player.add_child(cam)
    root.add_child(player)

    # set_script() does NOT dispose anything — root stays valid:
    player.set_script(load("res://scripts/player.gd"))

    _pack_and_save(root, "res://scenes/level.tscn")
```
**(C# / .NET):** identical structure with the temp-parent dance for the root (`SetScript()` disposes the wrapper, exactly as the 3D Player example) but with `Node2D`/`CharacterBody2D`/`Sprite2D`/`CollisionShape2D`/`RectangleShape2D`/`Camera2D`.

> No `dotnet build` is needed for a GDScript builder — run it straight from source (see Build order below).

### CRITICAL: Build order

Scene builders run via `godot --headless --script res://builders/BuildXxx.cs` (C#) or `godot --headless --script res://builders/build_xxx.gd` (GDScript). Each builder must be self-contained. If scene A instances scene B, build B first. C# builders require a `dotnet build` first; GDScript builders run directly from source with no build step.

### What NOT to Include

Scene builders produce `.tscn` files only. They must NOT contain:
- Runtime logic (`_Ready()`, `_Process()`, `_PhysicsProcess()`, input handling)
- Signal connections (signals are wired in runtime scripts)
- Game state, scoring, win/lose conditions
- UI behavior or button callbacks

## Scene Constraints

- Do NOT use export annotations (`[Export]` in C#, `@export` in GDScript) or other scene-time annotations (this runs at build-time)
- Asset loading: `[C# only]` use `GD.Load<T>()` (no `preload()` equivalent in C#). `(GDScript)` use runtime `load()` — do NOT use `preload()`, which resolves at parse time and is unnecessary in a build-time script
- Do NOT connect signals at build-time — scripts aren't instantiated yet. Signal connections belong in runtime scripts' `_Ready()` method
- **No spatial methods in `_Initialize()`** — `LookAt()`, `ToGlobal()`, etc. fail because nodes aren't in the tree yet. Use `RotationDegrees` or compute transforms manually. In runtime scripts (`_Ready()`, `_Process()`), **always use `LookAt()` to orient cameras and objects toward targets** — it's the correct tool there. Manual rotation math is error-prone and unnecessary.
- **Don't directly mix 2D and 3D in one hierarchy** — never parent `Node3D` under `Node2D`/`Control` (or vice-versa). When a scene needs both, render the secondary family inside a `SubViewport` and composite it back: a `SubViewportContainer`/`TextureRect` to show 3D inside a 2D/UI scene, or a `Sprite2D`/`TextureRect` fed by the SubViewport's texture. UI always goes on a `CanvasLayer` above the world (see "Choosing the node family").

## Environment & Lighting (3D Scenes)

When building 3D scenes, set up environment and lighting programmatically:

```csharp
// WorldEnvironment
var worldEnv = new WorldEnvironment();
var env = new Godot.Environment();
env.BackgroundMode = Godot.Environment.BGMode.Sky;
env.TonemapMode = Godot.Environment.ToneMapper.Filmic;
env.AmbientLightColor = Colors.White;
env.AmbientLightSkyContribution = 0.5f;
var sky = new Sky();
sky.SkyMaterial = new ProceduralSkyMaterial();
env.Sky = sky;
worldEnv.Environment = env;
root.AddChild(worldEnv);

// Sun (DirectionalLight3D)
var sun = new DirectionalLight3D();
sun.ShadowEnabled = true;
sun.ShadowBias = 0.05f;
sun.ShadowBlur = 2.0f;
sun.DirectionalShadowMaxDistance = 30.0f;
sun.SkyMode = DirectionalLight3D.SkyModeEnum.LightAndSky;
sun.RotationDegrees = new Vector3(-45, -30, 0);
root.AddChild(sun);
```

## 2D world extras (the 2D peers of the 3D nodes above)

For a `Node2D` world, the lighting / particle / scroll equivalents:
- **Lighting & atmosphere:** `CanvasModulate` (global tint), `PointLight2D` / `DirectionalLight2D` + `LightOccluder2D`.
- **Particles & trails:** `GPUParticles2D` (or `CPUParticles2D`), `Line2D`.
- **Camera:** `Camera2D` with `Zoom`, `LimitLeft/Top/Right/Bottom`, and `PositionSmoothingEnabled` for follow.
- **Scrolling backdrops:** `Parallax2D` (Godot 4.3+) or `ParallaxBackground` + `ParallaxLayer`.
- **Tiles:** `TileMapLayer` + `TileSet` (one layer per node in 4.3+).

Keep these in the `Node2D` world tree, not in Control containers.

## CSG for Rapid Prototyping (3D)

CSG nodes generate collision automatically — no separate CollisionShape needed:

```csharp
var floor = new CsgBox3D();
floor.Size = new Vector3(20, 0.5f, 20);
floor.UseCollision = true;
floor.Material = groundMat;
root.AddChild(floor);

// Subtraction (carve holes): child CSG on parent CSG
var hole = new CsgCylinder3D();
hole.Operation = CsgShape3D.OperationEnum.Subtraction;
hole.Radius = 1.0f;
hole.Height = 1.0f;
floor.AddChild(hole);
```

## Noise/Procedural Textures

```csharp
var noise = new FastNoiseLite();
noise.NoiseType = FastNoiseLite.NoiseTypeEnum.Cellular;
noise.Frequency = 0.02f;
noise.FractalType = FastNoiseLite.FractalTypeEnum.Fbm;
noise.FractalOctaves = 5;

var tex = new NoiseTexture2D();
tex.Noise = noise;
tex.Width = 1024;
tex.Height = 1024;
tex.Seamless = true;       // tileable
tex.AsNormalMap = true;     // for normal maps
tex.BumpStrength = 2.0f;
```

## StandardMaterial3D Extended Properties

Beyond basic albedo, useful properties for richer materials:
- `NormalEnabled = true` + `NormalTexture` + `NormalScale = 2.0f`
- `RimEnabled = true` + `RimTint = 1.0f` — silhouette glow
- `EmissionEnabled = true` + `EmissionTexture` — self-illumination
- `TextureFilter = BaseMaterial3D.TextureFilterEnum.LinearWithMipmapsAnisotropic`
