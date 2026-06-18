# Convention 1 — `.tscn` + script pairs

Build UI structure in scene files; keep scripts thin. This file shows the
pairing concretely.

## Wrong vs right

### Wrong — the node tree is assembled in code

```csharp
public partial class StatStrip : Control
{
    private Label _coins, _floors;

    public override void _Ready()
    {
        var panel = new PanelContainer();
        AddChild(panel);
        var row = new HBoxContainer();
        panel.AddChild(row);
        _coins = new Label { Text = "0" };
        _coins.AddThemeFontSizeOverride("font_size", 14);
        row.AddChild(_coins);
        _floors = new Label { Text = "0" };
        row.AddChild(_floors);
        // ...30 more lines...
    }
}
```

The layout exists nowhere you can look at it; every spacing tweak is a
rebuild; the styling is welded into the structure code.

### Right — the tree is in a `.tscn`, the script references it

`stat_strip.tscn` (authored in the editor):

```
[node name="StatStrip" type="Control"]
[node name="Panel" type="PanelContainer" parent="."]
[node name="Row" type="HBoxContainer" parent="Panel"]
[node name="Coins" type="Label" parent="Panel/Row"]
unique_name_in_owner = true
text = "0"
[node name="Floors" type="Label" parent="Panel/Row"]
unique_name_in_owner = true
text = "0"
```

`StatStrip.cs`:

```csharp
public partial class StatStrip : Control
{
    private Label _coins = null!;
    private Label _floors = null!;

    public override void _Ready()
    {
        _coins  = GetNode<Label>("%Coins");
        _floors = GetNode<Label>("%Floors");
    }

    public void SetCounts(int coins, int floors)
    {
        _coins.Text  = coins.ToString();
        _floors.Text = floors.ToString();
    }
}
```

The script is now references + a data-binding method. The layout opens in the
editor.

## `unique_name_in_owner` and `%Name`

Mark every node the script needs to reach with **`unique_name_in_owner = true`**
in the scene. Then reference it with `GetNode<T>("%Name")` instead of a brittle
path like `GetNode<T>("Panel/Row/Coins")`. The `%Name` lookup keeps working when
you re-parent or reorder nodes in the editor — only the script's contract (the
set of unique names) has to stay stable.

## Using a component

Before building a UI component, check whether a `.tscn` for it already exists.

- It exists → load and instantiate it:
  ```csharp
  var strip = GD.Load<PackedScene>("res://.../stat_strip.tscn")
                .Instantiate<StatStrip>();
  parent.AddChild(strip);
  ```
  Or, even better, expose it as an `[Export] PackedScene` so the scene is wired
  in the editor and swappable.
- It does not exist, and the component is reusable (a cell, a row, a modal) →
  create a new `.tscn` + script pair for it.

## The runtime-list exception

Only the *count* of list items is decided in code — never the item's structure.

`customer_cell.tscn` is authored once (icon + name `Label` + a `Button`). The
parent scene declares a container for the cells **pre-filled with a few mock
instances of the cell scene** — like dropping prefab placeholders into a Unity
scene. The mocks make the list previewable and tunable in the editor without
running the game:

```
[node name="CellList" type="VBoxContainer" parent="Panel/Scroll"]
unique_name_in_owner = true
[node name="MockCell1" parent="Panel/Scroll/CellList" instance=ExtResource("cell")]
[node name="MockCell2" parent="Panel/Scroll/CellList" instance=ExtResource("cell")]
```

The script fills that container by instantiating the cell scene per data row.
The clear loop at the top deletes the mocks on the first fill — that's the whole
mock-cleanup mechanism; no helper class or special naming is needed, because
runtime list code already starts by clearing its container:

```csharp
var list = GetNode<VBoxContainer>("%CellList");
foreach (Node child in list.GetChildren()) child.QueueFree();
foreach (var customer in customers)
{
    var cell = _customerCellScene.Instantiate<CustomerCell>();
    cell.Bind(customer);
    list.AddChild(cell);
}
```

That is the *only* place `AddChild` is appropriate for UI: feeding a
scene-authored container with scene-authored items whose quantity is dynamic.
Fixed parts — the panel, the header, the scroll container, a Play button — stay
in the `.tscn`.

## Content nested inside an instanced wrapper → Editable Children

Sometimes you instance a reusable wrapper (a panel, a collapsible, a frame) and
need to drop caller-supplied content *into one of its inner nodes* from the
parent scene (e.g. a `Garments` selector inside a `Collapsible`'s `Content`).
Godot honours this ONLY if the instance is marked **Editable Children**. In the
editor: right-click the instance → *Editable Children*. In the `.tscn` it shows
as an `[editable path="..."]` marker at the bottom, the path being the instance's
node path from the scene root:

```
[node name="FoldA" parent="VBox" instance=ExtResource("collapsible")]
[node name="Garments" parent="VBox/FoldA/Content" instance=ExtResource("tags")]
unique_name_in_owner = true
...
[editable path="VBox/FoldA"]
```

**Without that marker the nested children are invalid** — and the failure is
nasty because it's silent and platform-split:

- the editor hides them (the instance won't expand to show them), and
- the **exported build drops them entirely**. It runs fine from the editor, then
  `%Name` / explicit paths return **null in the APK** (`Node not found` →
  `setup()` on a null instance). Explicit paths don't help — the node genuinely
  isn't in the exported tree.

With the marker, the child keeps `unique_name_in_owner` and is reached by `%Name`
as usual, the editor shows it as editable (artists can tweak it at the parent
level), and it exports intact. This is the shipped-game pattern — Slay the Spire
2 uses `[editable path=...]` ~77 times for exactly this (nested glow / health-bar
/ card content kept artist-tweakable from the parent scene).

Prefer keeping a runtime-filled *list* container as a DIRECT child of your screen
(previous section); reach for Editable Children only when the content genuinely
belongs inside an instanced wrapper.

## Checklist

- New scene → lay the full skeleton (all static nodes) in the `.tscn` first.
- Static node the script touches → give it `unique_name_in_owner = true`.
- Script → `GetNode` references, signal handlers, data-binding methods only.
- Reusable component → its own `.tscn` + script pair.
- `AddChild` for UI → only runtime-count list items into a declared container.
- Content nested under an instanced wrapper's inner node → mark the instance
  **Editable Children** (`[editable path=...]`), or the editor hides it and the
  export silently drops it (null at runtime in the APK).
