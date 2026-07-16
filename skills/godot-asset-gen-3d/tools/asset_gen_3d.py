#!/usr/bin/env python3
"""3D Asset Generator CLI — GLB models via Tripo3D or Meshy.

Subcommands:
  glb         Convert a PNG/JPEG to a static GLB
  rig         Convert a PNG/JPEG to a rigged biped GLB
  retarget    Apply a provider animation to a rigged GLB
  resume      Resume a timed-out provider job from its sidecar — no extra cost
  set_budget  Set the Tripo generation budget in cents (shared assets/budget.json)

Output: JSON to stdout. Progress to stderr.
"""

import argparse
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from meshy.client import (
    SubmissionUnknownError as MeshySubmissionUnknownError,
    consumed_credits as meshy_consumed_credits,
    create_animation_task as meshy_create_animation_task,
    create_image_to_3d_task as meshy_create_image_to_3d_task,
    create_rigging_task as meshy_create_rigging_task,
    download_model as meshy_download_model,
    poll_task as meshy_poll_task,
)
from tripo.client import (
    SubmissionUnknownError as TripoSubmissionUnknownError,
    create_image_to_model_task,
    create_prerigcheck_task,
    create_retarget_task,
    create_rig_task,
    download_model as tripo_download_model,
    poll_task as tripo_poll_task,
)

BUDGET_FILE = Path("assets/budget.json")

QUALITY_PRESETS = {
    "default": {
        "face_limit": 30000,
        "geometry_quality": "standard",
        "texture_quality": "standard",
        "cost_cents": 30,
    },
    "hd": {
        "face_limit": None,
        "geometry_quality": "detailed",
        "texture_quality": "detailed",
        "cost_cents": 60,
    },
}

RIG_COST_CENTS = 25
RETARGET_COST_CENTS = 10


def _load_budget():
    if not BUDGET_FILE.exists():
        return None
    return json.loads(BUDGET_FILE.read_text())


def _spent_total(budget):
    return sum(v for entry in budget.get("log", []) for v in entry.values())


def check_budget(cost_cents: int):
    budget = _load_budget()
    if budget is None:
        return
    spent = _spent_total(budget)
    remaining = budget.get("budget_cents", 0) - spent
    if cost_cents > remaining:
        result_json(False, error=f"Budget exceeded: need {cost_cents}¢ but only {remaining}¢ remaining ({spent}¢ of {budget['budget_cents']}¢ spent)")
        sys.exit(1)


def record_spend(cost_cents: int, service: str):
    budget = _load_budget()
    if budget is None:
        return
    budget.setdefault("log", []).append({service: cost_cents})
    BUDGET_FILE.write_text(json.dumps(budget, indent=2) + "\n")


def result_json(
    ok: bool,
    path: str | None = None,
    cost_cents: int = 0,
    credits: int = 0,
    provider: str | None = None,
    error: str | None = None,
):
    d = {"ok": ok, "cost_cents": cost_cents}
    if credits:
        d["credits"] = credits
    if provider:
        d["provider"] = provider
    if path:
        d["path"] = path
    if error:
        d["error"] = error
    print(json.dumps(d))


def _sidecar_path(output: Path, provider: str = "tripo") -> Path:
    return output.with_suffix(output.suffix + f".{provider}.json")


def _write_sidecar(output: Path, data: dict) -> None:
    provider = data.get("provider", "tripo")
    _sidecar_path(output, provider).write_text(json.dumps(data, indent=2) + "\n")


def _read_sidecar(path: Path, provider: str | None = None) -> dict:
    providers = [provider] if provider else ["meshy", "tripo"]
    matches = [_sidecar_path(path, name) for name in providers if _sidecar_path(path, name).exists()]
    if not matches:
        expected = ", ".join(str(_sidecar_path(path, name)) for name in providers)
        raise FileNotFoundError(f"Sidecar not found: {expected}")
    if len(matches) > 1:
        raise ValueError(
            f"Multiple sidecars found for {path}; pass --provider tripo or --provider meshy"
        )
    data = json.loads(matches[0].read_text())
    data.setdefault("provider", "tripo")
    return data


def _resolve_preset(name: str) -> dict:
    if name not in QUALITY_PRESETS:
        result_json(False, error=f"Unknown quality: {name}. Use: {', '.join(QUALITY_PRESETS)}")
        sys.exit(1)
    return QUALITY_PRESETS[name]


def _resume_hint(output: Path) -> str:
    return f"Task is still processing on the server. Resume (no extra cost) with: asset_gen_3d.py resume -o {output}"


def _refuse_unknown_submission(output: Path, provider: str) -> None:
    sidecar_path = _sidecar_path(output, provider)
    if not sidecar_path.exists():
        return
    sidecar = json.loads(sidecar_path.read_text())
    if sidecar.get("status") == "manual_check_required":
        result_json(
            False,
            provider=provider,
            error=(
                f"Previous billable submission has unknown outcome ({sidecar.get('stage')}). "
                "Check the provider dashboard before resubmitting; the CLI will not overwrite "
                f"{sidecar_path}."
            ),
        )
        sys.exit(1)


def _mark_unknown_submission(output: Path, sidecar: dict, stage: str, error: Exception) -> None:
    sidecar["stage"] = stage
    sidecar["status"] = "manual_check_required"
    sidecar["submission_error"] = str(error)
    _write_sidecar(output, sidecar)
    result_json(
        False,
        provider=sidecar.get("provider"),
        error=(
            f"{error}. The server may have accepted this billable task. Check the provider "
            "dashboard before resuming or resubmitting."
        ),
    )
    sys.exit(1)


def _meshy_quality(args) -> dict:
    if args.quality == "default":
        if not 100 <= args.face_limit <= 300000:
            raise ValueError("Meshy --face-limit must be between 100 and 300000")
        return {
            "model_type": "standard",
            "should_remesh": True,
            "target_polycount": args.face_limit,
            "hd_texture": False,
        }
    if args.quality == "hd":
        return {
            "model_type": "standard",
            "should_remesh": False,
            "target_polycount": None,
            "hd_texture": True,
        }
    if args.quality == "lowpoly":
        return {
            "model_type": "lowpoly",
            "should_remesh": False,
            "target_polycount": None,
            "hd_texture": False,
        }
    raise ValueError(f"Unknown Meshy quality: {args.quality}")


def _cmd_glb_meshy(args, image_path: Path, output: Path):
    _refuse_unknown_submission(output, "meshy")
    try:
        quality = _meshy_quality(args)
    except ValueError as e:
        result_json(False, provider="meshy", error=str(e))
        sys.exit(1)
    print(
        f"Generating GLB via Meshy (quality={args.quality}, pbr={args.pbr}, "
        f"face_limit={quality['target_polycount']})...",
        file=sys.stderr,
    )
    sidecar = {
        "provider": "meshy",
        "kind": "mesh",
        "preset": args.quality,
        "pbr": args.pbr,
        "status": "pending",
    }
    try:
        task_id = meshy_create_image_to_3d_task(
            image_path,
            pbr=args.pbr,
            **quality,
        )
        print(f"  image-to-3d: {task_id}", file=sys.stderr)
        sidecar["image_to_3d_task_id"] = task_id
        _write_sidecar(output, sidecar)
        result = meshy_poll_task(task_id, "image-to-3d")
        credits = meshy_consumed_credits(result)
        sidecar["credits"] = credits
        meshy_download_model(result, output, "image-to-3d")
    except MeshySubmissionUnknownError as e:
        _mark_unknown_submission(output, sidecar, "image_to_3d_submit_unknown", e)
    except TimeoutError as e:
        result_json(
            False,
            provider="meshy",
            error=f"{e}. {_resume_hint(output)}",
        )
        sys.exit(1)
    except Exception as e:
        result_json(False, provider="meshy", error=str(e))
        sys.exit(1)

    sidecar["status"] = "complete"
    _write_sidecar(output, sidecar)
    print(f"Saved: {output}", file=sys.stderr)
    result_json(True, path=str(output), credits=credits, provider="meshy")


def cmd_glb(args):
    image_path = Path(args.image)
    if not image_path.exists():
        result_json(False, error=f"Image not found: {image_path}")
        sys.exit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.provider == "meshy":
        _cmd_glb_meshy(args, image_path, output)
        return

    _refuse_unknown_submission(output, "tripo")
    if args.quality == "lowpoly":
        result_json(False, provider="tripo", error="lowpoly is available only with --provider meshy")
        sys.exit(1)
    preset = _resolve_preset(args.quality)
    check_budget(preset["cost_cents"])

    face_limit = args.face_limit if args.quality == "default" else preset["face_limit"]

    print(f"Generating GLB (quality={args.quality}, pbr={args.pbr}, face_limit={face_limit})...", file=sys.stderr)

    sidecar = {
        "provider": "tripo",
        "kind": "mesh",
        "preset": args.quality,
        "pbr": args.pbr,
        "status": "pending",
    }
    try:
        task_id = create_image_to_model_task(
            image_path,
            face_limit=face_limit,
            pbr=args.pbr,
            geometry_quality=preset["geometry_quality"],
            texture_quality=preset["texture_quality"],
        )
        print(f"  image_to_model: {task_id}", file=sys.stderr)
        record_spend(preset["cost_cents"], "tripo3d-glb")
        sidecar["image_to_model_task_id"] = task_id
        _write_sidecar(output, sidecar)

        result = tripo_poll_task(task_id)
        tripo_download_model(result, output)
    except TripoSubmissionUnknownError as e:
        _mark_unknown_submission(output, sidecar, "image_to_model_submit_unknown", e)
    except TimeoutError as e:
        result_json(False, error=f"{e}. {_resume_hint(output)}", cost_cents=preset["cost_cents"], provider="tripo")
        sys.exit(1)
    except Exception as e:
        result_json(False, error=str(e), provider="tripo")
        sys.exit(1)

    sidecar["status"] = "complete"
    _write_sidecar(output, sidecar)
    print(f"Saved: {output}", file=sys.stderr)
    result_json(True, path=str(output), cost_cents=preset["cost_cents"], provider="tripo")


def _cmd_rig_meshy(args, image_path: Path, output: Path):
    _refuse_unknown_submission(output, "meshy")
    try:
        quality = _meshy_quality(args)
        if args.height_meters <= 0:
            raise ValueError("Meshy --height-meters must be greater than zero")
    except ValueError as e:
        result_json(False, provider="meshy", error=str(e))
        sys.exit(1)
    print(
        f"Generating rigged GLB via Meshy (quality={args.quality}, "
        f"height={args.height_meters}m)...",
        file=sys.stderr,
    )
    sidecar = {
        "provider": "meshy",
        "kind": "rig",
        "preset": args.quality,
        "pbr": args.pbr,
        "height_meters": args.height_meters,
        "stage": "image_to_3d",
        "status": "pending",
    }
    try:
        gen_id = meshy_create_image_to_3d_task(
            image_path,
            pbr=args.pbr,
            pose_mode="a-pose",
            **quality,
        )
        print(f"  image-to-3d: {gen_id}", file=sys.stderr)
        sidecar["image_to_3d_task_id"] = gen_id
        _write_sidecar(output, sidecar)
        mesh_result = meshy_poll_task(gen_id, "image-to-3d")
        sidecar["mesh_credits"] = meshy_consumed_credits(mesh_result)
        _write_sidecar(output, sidecar)

        try:
            rig_id = meshy_create_rigging_task(
                gen_id,
                height_meters=args.height_meters,
            )
        except MeshySubmissionUnknownError as e:
            _mark_unknown_submission(output, sidecar, "rigging_submit_unknown", e)
        print(f"  rigging: {rig_id}", file=sys.stderr)
        sidecar["rigging_task_id"] = rig_id
        sidecar["stage"] = "rigging"
        _write_sidecar(output, sidecar)
        rig_result = meshy_poll_task(rig_id, "rigging")
        sidecar["rig_credits"] = meshy_consumed_credits(rig_result)
        meshy_download_model(rig_result, output, "rigging")
    except MeshySubmissionUnknownError as e:
        _mark_unknown_submission(output, sidecar, "image_to_3d_submit_unknown", e)
    except TimeoutError as e:
        result_json(
            False,
            provider="meshy",
            error=f"{e}. {_resume_hint(output)}",
        )
        sys.exit(1)
    except Exception as e:
        result_json(False, provider="meshy", error=str(e))
        sys.exit(1)

    credits = sidecar.get("mesh_credits", 0) + sidecar.get("rig_credits", 0)
    sidecar["credits"] = credits
    sidecar["status"] = "complete"
    _write_sidecar(output, sidecar)
    print(f"Saved: {output}", file=sys.stderr)
    result_json(True, path=str(output), credits=credits, provider="meshy")


def cmd_rig(args):
    image_path = Path(args.image)
    if not image_path.exists():
        result_json(False, error=f"Image not found: {image_path}")
        sys.exit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.provider == "meshy":
        _cmd_rig_meshy(args, image_path, output)
        return

    _refuse_unknown_submission(output, "tripo")
    if args.quality == "lowpoly":
        result_json(False, provider="tripo", error="lowpoly is available only with --provider meshy")
        sys.exit(1)
    preset = _resolve_preset(args.quality)
    total_cost = preset["cost_cents"] + RIG_COST_CENTS
    check_budget(total_cost)

    face_limit = args.face_limit if args.quality == "default" else preset["face_limit"]

    print(f"Generating rigged GLB (quality={args.quality}, face_limit={face_limit})...", file=sys.stderr)

    sidecar = {
        "provider": "tripo",
        "kind": "rig",
        "preset": args.quality,
        "pbr": args.pbr,
        "rig_type": "biped",
        "status": "pending",
    }
    try:
        gen_id = create_image_to_model_task(
            image_path,
            face_limit=face_limit,
            pbr=args.pbr,
            geometry_quality=preset["geometry_quality"],
            texture_quality=preset["texture_quality"],
        )
        print(f"  image_to_model: {gen_id}", file=sys.stderr)
        record_spend(preset["cost_cents"], "tripo3d-glb")
        sidecar["image_to_model_task_id"] = gen_id
        sidecar["stage"] = "image_to_model"
        _write_sidecar(output, sidecar)
        tripo_poll_task(gen_id)

        check_id = create_prerigcheck_task(gen_id)
        print(f"  animate_prerigcheck: {check_id}", file=sys.stderr)
        sidecar["prerigcheck_task_id"] = check_id
        sidecar["stage"] = "prerigcheck"
        _write_sidecar(output, sidecar)
        check_result = tripo_poll_task(check_id)
        check_out = check_result.get("output", {})
        rig_type = check_out.get("rig_type")
        if rig_type != "biped":
            result_json(False, error=(
                f"Rig pipeline is biped-only; prerigcheck reported rig_type={rig_type!r}. "
                f"Use `glb` for non-biped characters."
            ), cost_cents=preset["cost_cents"])
            sys.exit(1)

        rig_id = create_rig_task(gen_id, rig_type="biped")
        print(f"  animate_rig: {rig_id}", file=sys.stderr)
        record_spend(RIG_COST_CENTS, "tripo3d-rig")
        sidecar["animate_rig_task_id"] = rig_id
        sidecar["stage"] = "animate_rig"
        _write_sidecar(output, sidecar)
        rig_result = tripo_poll_task(rig_id)
        tripo_download_model(rig_result, output)
    except TripoSubmissionUnknownError as e:
        unknown_stage = {
            "image_to_model": "prerigcheck_submit_unknown",
            "prerigcheck": "animate_rig_submit_unknown",
        }.get(sidecar.get("stage"), "image_to_model_submit_unknown")
        _mark_unknown_submission(output, sidecar, unknown_stage, e)
    except TimeoutError as e:
        result_json(False, error=f"{e}. {_resume_hint(output)}", cost_cents=0, provider="tripo")
        sys.exit(1)
    except Exception as e:
        result_json(False, error=str(e), provider="tripo")
        sys.exit(1)

    sidecar["status"] = "complete"
    _write_sidecar(output, sidecar)
    print(f"Saved: {output}", file=sys.stderr)
    result_json(True, path=str(output), cost_cents=total_cost, provider="tripo")


def _meshy_action_id(animation: str) -> int:
    value = animation.rsplit(":", 1)[-1]
    try:
        action_id = int(value)
    except ValueError as exc:
        raise ValueError(
            "Meshy animation must be an integer action_id, e.g. --animation 92"
        ) from exc
    if action_id < 0:
        raise ValueError("Meshy action_id must be non-negative")
    return action_id


def cmd_retarget(args):
    rigged = Path(args.rigged)
    if not rigged.exists():
        result_json(False, error=f"Rigged GLB not found: {rigged}")
        sys.exit(1)

    try:
        requested_provider = None if args.provider == "auto" else args.provider
        rigged_sidecar = _read_sidecar(rigged, requested_provider)
    except (FileNotFoundError, ValueError) as e:
        result_json(False, error=str(e))
        sys.exit(1)

    provider = rigged_sidecar.get("provider", "tripo")
    if provider == "meshy":
        _cmd_retarget_meshy(args, rigged_sidecar)
        return

    rig_task_id = rigged_sidecar.get("animate_rig_task_id")
    if not rig_task_id or rigged_sidecar.get("kind") != "rig":
        result_json(False, error=f"Sidecar for {rigged} is not a rig output")
        sys.exit(1)

    check_budget(RETARGET_COST_CENTS)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    _refuse_unknown_submission(output, "tripo")

    print(f"Retargeting ({args.animation})...", file=sys.stderr)

    sidecar = {
        "provider": "tripo",
        "kind": "anim",
        "animate_rig_task_id": rig_task_id,
        "animation": args.animation,
        "status": "pending",
    }
    try:
        task_id = create_retarget_task(rig_task_id, args.animation)
        print(f"  animate_retarget: {task_id}", file=sys.stderr)
        record_spend(RETARGET_COST_CENTS, "tripo3d-retarget")
        sidecar["animate_retarget_task_id"] = task_id
        _write_sidecar(output, sidecar)
        result = tripo_poll_task(task_id)
        tripo_download_model(result, output)
    except TripoSubmissionUnknownError as e:
        _mark_unknown_submission(output, sidecar, "animate_retarget_submit_unknown", e)
    except TimeoutError as e:
        result_json(False, error=f"{e}. {_resume_hint(output)}", cost_cents=RETARGET_COST_CENTS, provider="tripo")
        sys.exit(1)
    except Exception as e:
        result_json(False, error=str(e), provider="tripo")
        sys.exit(1)

    sidecar["status"] = "complete"
    _write_sidecar(output, sidecar)
    print(f"Saved: {output}", file=sys.stderr)
    result_json(True, path=str(output), cost_cents=RETARGET_COST_CENTS, provider="tripo")


def _cmd_retarget_meshy(args, rigged_sidecar: dict):
    rig_task_id = rigged_sidecar.get("rigging_task_id")
    if not rig_task_id or rigged_sidecar.get("kind") != "rig":
        result_json(False, provider="meshy", error="Meshy sidecar is not a rig output")
        sys.exit(1)
    try:
        action_id = _meshy_action_id(args.animation)
    except ValueError as e:
        result_json(False, provider="meshy", error=str(e))
        sys.exit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    _refuse_unknown_submission(output, "meshy")
    print(f"Animating via Meshy (action_id={action_id})...", file=sys.stderr)
    sidecar = {
        "provider": "meshy",
        "kind": "anim",
        "rigging_task_id": rig_task_id,
        "animation": action_id,
        "status": "pending",
    }
    try:
        task_id = meshy_create_animation_task(rig_task_id, action_id)
        print(f"  animation: {task_id}", file=sys.stderr)
        sidecar["animation_task_id"] = task_id
        _write_sidecar(output, sidecar)
        result = meshy_poll_task(task_id, "animation")
        credits = meshy_consumed_credits(result)
        sidecar["credits"] = credits
        meshy_download_model(result, output, "animation")
    except MeshySubmissionUnknownError as e:
        _mark_unknown_submission(output, sidecar, "animation_submit_unknown", e)
    except TimeoutError as e:
        result_json(
            False,
            provider="meshy",
            error=f"{e}. {_resume_hint(output)}",
        )
        sys.exit(1)
    except Exception as e:
        result_json(False, provider="meshy", error=str(e))
        sys.exit(1)

    sidecar["status"] = "complete"
    _write_sidecar(output, sidecar)
    print(f"Saved: {output}", file=sys.stderr)
    result_json(True, path=str(output), credits=credits, provider="meshy")


def cmd_resume(args):
    output = Path(args.output)
    try:
        requested_provider = None if args.provider == "auto" else args.provider
        sidecar = _read_sidecar(output, requested_provider)
    except (FileNotFoundError, ValueError) as e:
        result_json(False, error=str(e))
        sys.exit(1)

    provider = sidecar.get("provider", "tripo")
    if sidecar.get("status") == "manual_check_required":
        _refuse_unknown_submission(output, provider)
    if sidecar.get("status") == "complete":
        print(f"Already complete: {output}", file=sys.stderr)
        result_json(True, path=str(output), cost_cents=0, provider=provider)
        return

    if provider == "meshy":
        _cmd_resume_meshy(output, sidecar)
        return

    kind = sidecar.get("kind")
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        if kind == "mesh":
            task_id = sidecar["image_to_model_task_id"]
            print(f"  resuming image_to_model: {task_id}", file=sys.stderr)
            result = tripo_poll_task(task_id)
            tripo_download_model(result, output)

        elif kind == "rig":
            stage = sidecar.get("stage")
            gen_id: str = sidecar["image_to_model_task_id"]

            if stage == "image_to_model":
                print(f"  resuming image_to_model: {gen_id}", file=sys.stderr)
                tripo_poll_task(gen_id)
                try:
                    check_id = create_prerigcheck_task(gen_id)
                except TripoSubmissionUnknownError as e:
                    _mark_unknown_submission(output, sidecar, "prerigcheck_submit_unknown", e)
                print(f"  animate_prerigcheck: {check_id}", file=sys.stderr)
                sidecar["prerigcheck_task_id"] = check_id
                sidecar["stage"] = "prerigcheck"
                _write_sidecar(output, sidecar)
                stage = "prerigcheck"

            if stage == "prerigcheck":
                check_id = sidecar["prerigcheck_task_id"]
                print(f"  resuming animate_prerigcheck: {check_id}", file=sys.stderr)
                check_result = tripo_poll_task(check_id)
                rt = check_result.get("output", {}).get("rig_type")
                if rt != "biped":
                    result_json(False, error=f"prerigcheck: rig_type={rt!r}; rig pipeline is biped-only")
                    sys.exit(1)
                try:
                    rig_id = create_rig_task(gen_id, rig_type="biped")
                except TripoSubmissionUnknownError as e:
                    _mark_unknown_submission(output, sidecar, "animate_rig_submit_unknown", e)
                print(f"  animate_rig: {rig_id}", file=sys.stderr)
                record_spend(RIG_COST_CENTS, "tripo3d-rig")
                sidecar["animate_rig_task_id"] = rig_id
                sidecar["stage"] = "animate_rig"
                _write_sidecar(output, sidecar)
                stage = "animate_rig"

            if stage == "animate_rig":
                rig_id = sidecar["animate_rig_task_id"]
                print(f"  resuming animate_rig: {rig_id}", file=sys.stderr)
                rig_result = tripo_poll_task(rig_id)
                tripo_download_model(rig_result, output)
            else:
                result_json(False, error=f"Unknown rig stage: {stage}")
                sys.exit(1)

        elif kind == "anim":
            task_id = sidecar["animate_retarget_task_id"]
            print(f"  resuming animate_retarget: {task_id}", file=sys.stderr)
            result = tripo_poll_task(task_id)
            tripo_download_model(result, output)

        else:
            result_json(False, error=f"Unknown sidecar kind: {kind!r}")
            sys.exit(1)

    except TimeoutError as e:
        result_json(False, error=f"{e}. Task still processing; retry resume.", cost_cents=0, provider="tripo")
        sys.exit(1)
    except Exception as e:
        result_json(False, error=str(e), provider="tripo")
        sys.exit(1)

    sidecar["status"] = "complete"
    _write_sidecar(output, sidecar)
    print(f"Saved: {output}", file=sys.stderr)
    result_json(True, path=str(output), cost_cents=0, provider="tripo")


def _cmd_resume_meshy(output: Path, sidecar: dict):
    kind = sidecar.get("kind")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if kind == "mesh":
            task_id = sidecar["image_to_3d_task_id"]
            print(f"  resuming Meshy image-to-3d: {task_id}", file=sys.stderr)
            result = meshy_poll_task(task_id, "image-to-3d")
            sidecar["credits"] = meshy_consumed_credits(result)
            meshy_download_model(result, output, "image-to-3d")

        elif kind == "rig":
            stage = sidecar.get("stage")
            gen_id = sidecar["image_to_3d_task_id"]
            if stage == "image_to_3d":
                print(f"  resuming Meshy image-to-3d: {gen_id}", file=sys.stderr)
                mesh_result = meshy_poll_task(gen_id, "image-to-3d")
                sidecar["mesh_credits"] = meshy_consumed_credits(mesh_result)
                try:
                    rig_id = meshy_create_rigging_task(
                        gen_id,
                        height_meters=float(sidecar.get("height_meters", 1.7)),
                    )
                except MeshySubmissionUnknownError as e:
                    _mark_unknown_submission(output, sidecar, "rigging_submit_unknown", e)
                print(f"  rigging: {rig_id}", file=sys.stderr)
                sidecar["rigging_task_id"] = rig_id
                sidecar["stage"] = "rigging"
                _write_sidecar(output, sidecar)
                stage = "rigging"

            if stage == "rigging":
                rig_id = sidecar["rigging_task_id"]
                print(f"  resuming Meshy rigging: {rig_id}", file=sys.stderr)
                rig_result = meshy_poll_task(rig_id, "rigging")
                sidecar["rig_credits"] = meshy_consumed_credits(rig_result)
                sidecar["credits"] = sidecar.get("mesh_credits", 0) + sidecar.get("rig_credits", 0)
                meshy_download_model(rig_result, output, "rigging")
            else:
                raise ValueError(f"Unknown Meshy rig stage: {stage}")

        elif kind == "anim":
            task_id = sidecar["animation_task_id"]
            print(f"  resuming Meshy animation: {task_id}", file=sys.stderr)
            result = meshy_poll_task(task_id, "animation")
            sidecar["credits"] = meshy_consumed_credits(result)
            meshy_download_model(result, output, "animation")

        else:
            raise ValueError(f"Unknown Meshy sidecar kind: {kind!r}")

    except TimeoutError as e:
        result_json(
            False,
            provider="meshy",
            error=f"{e}. Task still processing; retry resume.",
        )
        sys.exit(1)
    except Exception as e:
        result_json(False, provider="meshy", error=str(e))
        sys.exit(1)

    sidecar["status"] = "complete"
    _write_sidecar(output, sidecar)
    print(f"Saved: {output}", file=sys.stderr)
    result_json(True, path=str(output), provider="meshy")


def cmd_set_budget(args):
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    budget = {"budget_cents": args.cents, "log": []}
    if BUDGET_FILE.exists():
        old = json.loads(BUDGET_FILE.read_text())
        budget["log"] = old.get("log", [])
    BUDGET_FILE.write_text(json.dumps(budget, indent=2) + "\n")
    spent = _spent_total(budget)
    print(json.dumps({"ok": True, "budget_cents": args.cents, "spent_cents": spent, "remaining_cents": args.cents - spent}))


def main():
    parser = argparse.ArgumentParser(description="3D Asset Generator — GLB models via Tripo3D or Meshy")
    sub = parser.add_subparsers(dest="command", required=True)

    p_glb = sub.add_parser("glb", help="Convert PNG/JPEG to static GLB")
    p_glb.add_argument("--provider", default="tripo", choices=["tripo", "meshy"],
                       help="Generation backend. Default: tripo")
    p_glb.add_argument("--image", required=True, help="Input PNG/JPEG path")
    p_glb.add_argument("--quality", default="default", choices=["default", "hd", "lowpoly"],
                       help="default or hd for both providers; lowpoly is Meshy-only")
    p_glb.add_argument("--no-pbr", dest="pbr", action="store_false", default=True,
                       help="Disable PBR (use if PBR output looks wrong)")
    p_glb.add_argument("--face-limit", type=int, default=30000,
                       help="Face cap for default quality, 10000-50000. Ignored when --quality hd. Default: 30000")
    p_glb.add_argument("-o", "--output", required=True, help="Output GLB path")
    p_glb.set_defaults(func=cmd_glb)

    p_rig = sub.add_parser("rig", help="Convert PNG/JPEG to rigged biped GLB. Biped only.")
    p_rig.add_argument("--provider", default="tripo", choices=["tripo", "meshy"],
                       help="Generation backend. Default: tripo")
    p_rig.add_argument("--image", required=True, help="Input PNG/JPEG path (biped character)")
    p_rig.add_argument("--quality", default="default", choices=["default", "hd", "lowpoly"],
                       help="default or hd for both providers; lowpoly is Meshy-only")
    p_rig.add_argument("--no-pbr", dest="pbr", action="store_false", default=True,
                       help="Disable PBR")
    p_rig.add_argument("--face-limit", type=int, default=30000,
                       help="Face cap for default quality. Ignored when --quality hd. Default: 30000")
    p_rig.add_argument("--height-meters", type=float, default=1.7,
                       help="Approximate humanoid height for Meshy rigging. Default: 1.7")
    p_rig.add_argument("-o", "--output", required=True, help="Output rigged GLB path")
    p_rig.set_defaults(func=cmd_rig)

    p_rt = sub.add_parser("retarget", help="Apply a provider animation to a rigged GLB")
    p_rt.add_argument("--provider", default="auto", choices=["auto", "tripo", "meshy"],
                      help="Detect from the rig sidecar by default")
    p_rt.add_argument("--rigged", required=True, help="Rigged GLB produced by `rig`")
    p_rt.add_argument("--animation", required=True,
                      help="Tripo preset (preset:biped:walk) or Meshy action_id (92)")
    p_rt.add_argument("-o", "--output", required=True, help="Output animated GLB path")
    p_rt.set_defaults(func=cmd_retarget)

    p_res = sub.add_parser("resume", help="Resume a timed-out provider job from its sidecar")
    p_res.add_argument("--provider", default="auto", choices=["auto", "tripo", "meshy"],
                       help="Detect from .tripo.json/.meshy.json by default")
    p_res.add_argument("-o", "--output", required=True, help="Output path whose provider sidecar holds pending task ids")
    p_res.set_defaults(func=cmd_resume)

    p_budget = sub.add_parser("set_budget", help="Set the Tripo asset generation budget in cents")
    p_budget.add_argument("cents", type=int, help="Budget in cents")
    p_budget.set_defaults(func=cmd_set_budget)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
