#!/usr/bin/env python3
"""2D Asset Generator CLI — PNG images and MP4 video via Google AI Studio,
OpenAI, and WaveSpeedAI.

Subcommands:
  image       Generate/edit a PNG from a prompt (Gemini x4 / gpt-image-2 / Wan 2.7)
  video       Generate MP4 from prompt + start image (WaveSpeed Wan 2.7 i2v)
  set_budget  Set the generation budget in cents

Providers:
  official   — Google AI Studio (GOOGLE_API_KEY) / OpenAI (OPENAI_API_KEY)
  wavespeed  — WaveSpeedAI (WAVESPEED_API_KEY); also the ONLY route for the
               alibaba/wan-2.7 family (uncensored generation/edit)
  auto       — official when the vendor key is set, else wavespeed (default)

Output: JSON to stdout. Progress to stderr.
NOTE: costs are ESTIMATES (cents) — adjust PRICING below to match your bills.
"""

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

TOOLS_DIR = Path(__file__).parent
BUDGET_FILE = Path("assets/budget.json")

WAVESPEED_BASE = "https://api.wavespeed.ai/api/v3"
OPENAI_BASE = "https://api.openai.com/v1"

# ---------------------------------------------------------------------------
# Model registry
#   vendor:    google | openai | alibaba
#   official:  model id on the vendor's own API (None = wavespeed-only)
#   ws_t2i:    wavespeed slug for text-to-image (None = no t2i)
#   ws_edit:   wavespeed slug for image edit (None = t2i slug accepts images)
#   sizes:     allowed --size values -> cost cents (ESTIMATES)
# ---------------------------------------------------------------------------
MODELS = {
    "gemini-3.1-flash-lite-image": {
        "vendor": "google",
        "official": "gemini-3.1-flash-lite-image",
        "ws_t2i": "google/gemini-3.1-flash-lite-image/text-to-image",
        "ws_edit": "google/gemini-3.1-flash-lite-image/edit",
        "sizes": {"512": 2, "1K": 3, "2K": 5, "4K": 8},
    },
    "gemini-3.1-flash-image": {
        "vendor": "google",
        "official": "gemini-3.1-flash-image",
        "ws_t2i": "google/gemini-3.1-flash-image/text-to-image",
        "ws_edit": "google/gemini-3.1-flash-image/edit",
        "sizes": {"512": 5, "1K": 7, "2K": 10, "4K": 15},
    },
    "gemini-3-pro-image": {
        "vendor": "google",
        "official": "gemini-3-pro-image",
        "ws_t2i": "google/gemini-3-pro-image/text-to-image",
        "ws_edit": "google/gemini-3-pro-image/edit",
        "sizes": {"1K": 15, "2K": 20, "4K": 30},
    },
    "gemini-2.5-flash-image": {
        "vendor": "google",
        "official": "gemini-2.5-flash-image",
        "ws_t2i": "google/gemini-2.5-flash-image/text-to-image",
        "ws_edit": "google/gemini-2.5-flash-image/edit",
        "sizes": {"1K": 4},
    },
    "gpt-image-2": {
        "vendor": "openai",
        "official": "gpt-image-2-2026-04-21",
        "ws_t2i": "openai/gpt-image-2/text-to-image",
        "ws_edit": "openai/gpt-image-2/edit",
        "sizes": {"1K": 10, "2K": 15},  # 2K maps to 1536px on OpenAI
    },
    # --- Wan 2.7 family: wavespeed-only; permissive content policy (spicy/nudity
    #     game art that other providers refuse). t2i slugs reject reference images;
    #     edit slugs REQUIRE at least one --image.
    "wan-2.7-t2i": {
        "vendor": "alibaba",
        "official": None,
        "ws_t2i": "alibaba/wan-2.7/text-to-image",
        "ws_edit": None,
        "sizes": {"1K": 2, "2K": 4},
    },
    "wan-2.7-t2i-pro": {
        "vendor": "alibaba",
        "official": None,
        "ws_t2i": "alibaba/wan-2.7/text-to-image-pro",
        "ws_edit": None,
        "sizes": {"1K": 5, "2K": 8, "4K": 12},
    },
    "wan-2.7-edit": {
        "vendor": "alibaba",
        "official": None,
        "ws_t2i": None,
        "ws_edit": "alibaba/wan-2.7/image-edit",
        "sizes": {"1K": 3, "2K": 6},
    },
    "wan-2.7-edit-pro": {
        "vendor": "alibaba",
        "official": None,
        "ws_t2i": None,
        "ws_edit": "alibaba/wan-2.7/image-edit-pro",
        "sizes": {"1K": 6, "2K": 10, "4K": 15},
    },
}

DEFAULT_MODEL = "gemini-3.1-flash-image"

# ---------------------------------------------------------------------------
# Video models
#   ark       — Volcano Engine Ark (直链, ARK_API_KEY). model = inference endpoint
#               id (ep-...), overridable per-model via env. Prices from the
#               seedmaker developers page (¢/second).
#   wavespeed — alibaba wan-2.7 i2v (WAVESPEED_API_KEY), content-permissive.
# ---------------------------------------------------------------------------
ARK_BASE = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"

VIDEO_MODELS = {
    "seedance-2.0": {
        "backend": "ark",
        "ep_env": "SEEDANCE_2_0_EP",
        "ep_default": "ep-20260327143137-pwdn2",
        "cents_per_sec": 1.0,
        "resolutions": ["480p", "720p", "1080p"],
    },
    "seedance-2.0-fast": {
        "backend": "ark",
        "ep_env": "SEEDANCE_2_0_FAST_EP",
        "ep_default": "ep-20260327143210-qtvxd",
        "cents_per_sec": 0.8,
        "resolutions": ["480p", "720p"],
    },
    "seedance-2.0-mini": {
        "backend": "ark",
        "ep_env": "SEEDANCE_2_0_MINI_EP",
        "ep_default": "ep-20260625152338-rbbxj",
        "cents_per_sec": 0.6,
        "resolutions": ["480p", "720p"],
    },
    "wan-2.7": {
        "backend": "wavespeed",
        "slug": "alibaba/wan-2.7/image-to-video",
        "cents_per_sec": 5.0,  # ESTIMATE
        "resolutions": ["480p", "720p"],
    },
}

DEFAULT_VIDEO_MODEL = "seedance-2.0-fast"

VENDOR_KEYS = {"google": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY"}

ASPECT_RATIOS = [
    "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
    "9:16", "16:9", "21:9", "1:4", "4:1",
]

SIZE_PX = {"512": 512, "1K": 1024, "2K": 2048, "4K": 4096}


# --- budget -----------------------------------------------------------------

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


def result_json(ok: bool, path: str | None = None, cost_cents: int = 0, error: str | None = None):
    d = {"ok": ok, "cost_cents": cost_cents}
    if path:
        d["path"] = path
    if error:
        d["error"] = error
    print(json.dumps(d))


# --- shared helpers ----------------------------------------------------------

def _mime_for_image(path: Path) -> str:
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/png")


def _image_data_uri(image_path: Path) -> str:
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    return f"data:{_mime_for_image(image_path)};base64,{b64}"


def _save_png(data: bytes, output: Path):
    img = Image.open(io.BytesIO(data))
    img.save(output, format="PNG")


def _check_refs(paths):
    out = []
    for p in paths or []:
        rp = Path(p)
        if not rp.exists():
            result_json(False, error=f"Reference image not found: {rp}")
            sys.exit(1)
        out.append(rp)
    return out


def _resolve_provider(spec: dict, requested: str) -> str:
    """official | wavespeed, honoring availability of API keys."""
    vendor = spec["vendor"]
    if spec["official"] is None:
        if requested == "official":
            result_json(False, error=f"{vendor} model has no official route; it is wavespeed-only")
            sys.exit(1)
        return "wavespeed"
    if requested == "official":
        return "official"
    if requested == "wavespeed":
        return "wavespeed"
    # auto: prefer the vendor's own API when its key is present
    if os.environ.get(VENDOR_KEYS.get(vendor, ""), ""):
        return "official"
    if os.environ.get("WAVESPEED_API_KEY", ""):
        return "wavespeed"
    result_json(False, error=f"No API key found: set {VENDOR_KEYS.get(vendor)} (official) or WAVESPEED_API_KEY (wavespeed)")
    sys.exit(1)


# --- backend: Google AI Studio (official) ------------------------------------

def _gen_google_official(model_id: str, args, refs, output: Path):
    from google import genai
    from google.genai import types

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(
            image_size=args.size,
            aspect_ratio=args.aspect_ratio,
        ),
    )
    contents = []
    for rp in refs:
        contents.append(types.Part.from_bytes(data=rp.read_bytes(), mime_type=_mime_for_image(rp)))
    contents.append(args.prompt)

    client = genai.Client()
    response = client.models.generate_content(model=model_id, contents=contents, config=config)

    if response.parts is None:
        reason = "unknown"
        if response.candidates and response.candidates[0].finish_reason:
            reason = response.candidates[0].finish_reason
        raise RuntimeError(f"Generation blocked (reason: {reason})")

    for part in response.parts:
        if part.inline_data is not None:
            _save_png(part.inline_data.data, output)
            return
    raise RuntimeError("No image returned")


# --- backend: OpenAI (official) ----------------------------------------------

def _openai_size(size: str, aspect_ratio: str) -> str:
    """gpt-image sizes: 1024x1024 / 1536x1024 / 1024x1536 / auto."""
    landscape = aspect_ratio in ("3:2", "16:9", "4:3", "5:4", "21:9", "4:1")
    portrait = aspect_ratio in ("2:3", "9:16", "3:4", "4:5", "1:4")
    if size == "2K" or landscape or portrait:
        if landscape:
            return "1536x1024"
        if portrait:
            return "1024x1536"
    return "1024x1024"


def _gen_openai_official(model_id: str, args, refs, output: Path):
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    headers = {"Authorization": f"Bearer {key}"}
    size = _openai_size(args.size, args.aspect_ratio)

    if refs:
        files = [("image[]", (rp.name, rp.read_bytes(), _mime_for_image(rp))) for rp in refs]
        data = {"model": model_id, "prompt": args.prompt, "size": size}
        r = requests.post(f"{OPENAI_BASE}/images/edits", headers=headers, data=data, files=files, timeout=300)
    else:
        payload = {"model": model_id, "prompt": args.prompt, "size": size}
        r = requests.post(f"{OPENAI_BASE}/images/generations", headers=headers, json=payload, timeout=300)
    r.raise_for_status()
    out = r.json()
    b64 = out["data"][0].get("b64_json")
    if not b64:
        url = out["data"][0].get("url")
        if not url:
            raise RuntimeError(f"No image in response: {out}")
        dl = requests.get(url, timeout=120)
        dl.raise_for_status()
        _save_png(dl.content, output)
        return
    _save_png(base64.b64decode(b64), output)


# --- backend: WaveSpeedAI -----------------------------------------------------

def _ws_headers():
    key = os.environ.get("WAVESPEED_API_KEY", "")
    if not key:
        raise RuntimeError("WAVESPEED_API_KEY not set")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _ws_submit_and_poll(slug: str, payload: dict, timeout_s: int = 600) -> bytes:
    """POST /api/v3/{slug} then poll /predictions/{id}/result until completed."""
    r = requests.post(f"{WAVESPEED_BASE}/{slug}", headers=_ws_headers(), json=payload, timeout=120)
    r.raise_for_status()
    data = r.json().get("data", {})
    req_id = data.get("id")
    if not req_id:
        raise RuntimeError(f"WaveSpeed submit failed: {r.text[:400]}")
    print(f"  wavespeed task: {req_id}", file=sys.stderr)

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        pr = requests.get(f"{WAVESPEED_BASE}/predictions/{req_id}/result",
                          headers=_ws_headers(), timeout=60)
        pr.raise_for_status()
        pd = pr.json().get("data", {})
        status = pd.get("status")
        if status == "completed":
            outputs = pd.get("outputs") or []
            if not outputs:
                raise RuntimeError("WaveSpeed completed but returned no outputs")
            dl = requests.get(outputs[0], timeout=300)
            dl.raise_for_status()
            return dl.content
        if status == "failed":
            raise RuntimeError(f"WaveSpeed task failed: {pd.get('error')}")
        time.sleep(2)
    raise TimeoutError(f"WaveSpeed task {req_id} still processing after {timeout_s}s")


def _gen_wavespeed_image(spec: dict, args, refs, output: Path):
    if refs:
        slug = spec["ws_edit"] or spec["ws_t2i"]
        if spec["ws_edit"] is None and spec["ws_t2i"] is None:
            raise RuntimeError("Model has no wavespeed route")
        if spec["ws_edit"] is None:
            raise RuntimeError(f"{args.model} has no edit route; use wan-2.7-edit / a gemini model for edits")
    else:
        slug = spec["ws_t2i"]
        if slug is None:
            raise RuntimeError(f"{args.model} is edit-only; pass --image (the picture to edit)")

    px = SIZE_PX.get(args.size, 1024)
    w, h = px, px
    try:  # scale by aspect ratio, longest side = px
        aw, ah = (float(x) for x in args.aspect_ratio.split(":"))
        if aw >= ah:
            w, h = px, max(64, int(px * ah / aw))
        else:
            w, h = max(64, int(px * aw / ah)), px
    except ValueError:
        pass

    payload = {
        "prompt": args.prompt,
        "size": f"{w}*{h}",
        "enable_sync_mode": False,
    }
    if refs:
        payload["images"] = [_image_data_uri(rp) for rp in refs]
    content = _ws_submit_and_poll(slug, payload)
    _save_png(content, output)


# --- commands -----------------------------------------------------------------

def cmd_image(args):
    spec = MODELS[args.model]
    if args.size not in spec["sizes"]:
        result_json(False, error=f"{args.model} supports sizes: {', '.join(spec['sizes'])} (got {args.size})")
        sys.exit(1)
    cost = spec["sizes"][args.size]
    provider = _resolve_provider(spec, args.provider)

    refs = _check_refs(args.image)
    if spec["ws_t2i"] is None and not refs:  # edit-only wan models
        result_json(False, error=f"{args.model} is an EDIT model — pass --image (the picture to edit)")
        sys.exit(1)

    check_budget(cost)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    label = f"{args.model} via {provider} {args.size} {args.aspect_ratio}"
    if refs:
        label += f" ({len(refs)} ref image{'s' if len(refs) > 1 else ''})"
    print(f"Generating image ({label})...", file=sys.stderr)

    try:
        if provider == "official":
            if spec["vendor"] == "google":
                _gen_google_official(spec["official"], args, refs, output)
            elif spec["vendor"] == "openai":
                _gen_openai_official(spec["official"], args, refs, output)
            else:
                raise RuntimeError(f"No official backend for vendor {spec['vendor']}")
        else:
            _gen_wavespeed_image(spec, args, refs, output)
    except Exception as e:
        result_json(False, error=str(e))
        sys.exit(1)

    print(f"Saved: {output}", file=sys.stderr)
    record_spend(cost, f"{provider}:{args.model}")
    result_json(True, path=str(output), cost_cents=cost)


# --- backend: Volcano Engine Ark (Seedance, 直链) ------------------------------

def _ark_headers():
    key = os.environ.get("ARK_API_KEY", "")
    if not key:
        raise RuntimeError("ARK_API_KEY not set (Volcano Engine Ark)")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _gen_ark_video(spec: dict, args, image_path: Path, output: Path):
    model_ep = os.environ.get(spec["ep_env"], "") or spec["ep_default"]
    content = [{"type": "text", "text": args.prompt}]
    content.append({
        "type": "image_url",
        "image_url": {"url": _image_data_uri(image_path)},
        "role": "first_frame",
    })
    payload = {
        "model": model_ep,
        "content": content,
        "resolution": args.resolution,
        "ratio": args.ratio,
        "duration": args.duration,
        "generate_audio": False,
        "watermark": False,
    }
    r = requests.post(ARK_BASE, headers=_ark_headers(), json=payload, timeout=120)
    if not r.ok:
        raise RuntimeError(f"Ark submit failed ({r.status_code}): {r.text[:400]}")
    task_id = r.json().get("id")
    if not task_id:
        raise RuntimeError(f"Ark submit returned no task id: {r.text[:400]}")
    print(f"  ark task: {task_id}", file=sys.stderr)

    deadline = time.time() + 900
    while time.time() < deadline:
        pr = requests.get(f"{ARK_BASE}/{task_id}", headers=_ark_headers(), timeout=60)
        pr.raise_for_status()
        pd = pr.json()
        status = pd.get("status")
        if status == "succeeded":
            video_url = (pd.get("content") or {}).get("video_url")
            if not video_url:
                raise RuntimeError(f"Ark succeeded but no video_url: {pd}")
            dl = requests.get(video_url, timeout=600)  # link valid 24h
            dl.raise_for_status()
            output.write_bytes(dl.content)
            return
        if status in ("failed", "expired"):
            raise RuntimeError(f"Ark task {status}: {pd.get('error')}")
        time.sleep(3)
    raise TimeoutError(f"Ark task {task_id} still processing after 900s")


def cmd_video(args):
    spec = VIDEO_MODELS[args.video_model]
    if args.resolution not in spec["resolutions"]:
        result_json(False, error=f"{args.video_model} supports resolutions: {', '.join(spec['resolutions'])} (got {args.resolution})")
        sys.exit(1)
    if spec["backend"] == "ark" and not (4 <= args.duration <= 15):
        result_json(False, error="Seedance duration must be 4-15 seconds")
        sys.exit(1)

    cost = max(1, round(args.duration * spec["cents_per_sec"]))
    check_budget(cost)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    image_path = Path(args.image)
    if not image_path.exists():
        result_json(False, error=f"Reference image not found: {image_path}")
        sys.exit(1)

    print(f"Generating {args.duration}s video ({args.video_model}, {args.resolution})...", file=sys.stderr)
    try:
        if spec["backend"] == "ark":
            _gen_ark_video(spec, args, image_path, output)
        else:
            payload = {
                "prompt": args.prompt,
                "image": _image_data_uri(image_path),
                "duration": args.duration,
            }
            content = _ws_submit_and_poll(spec["slug"], payload, timeout_s=900)
            output.write_bytes(content)
    except Exception as e:
        result_json(False, error=str(e))
        sys.exit(1)

    print(f"Saved: {output}", file=sys.stderr)
    record_spend(cost, f"video:{args.video_model}")
    result_json(True, path=str(output), cost_cents=cost)


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
    parser = argparse.ArgumentParser(
        description="2D Asset Generator — Gemini (Google AI Studio) / gpt-image-2 (OpenAI) / Wan 2.7 (WaveSpeed)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_img = sub.add_parser("image", help="Generate or edit a PNG image")
    p_img.add_argument("--prompt", required=True, help="Full image generation/edit prompt")
    p_img.add_argument("--model", choices=list(MODELS.keys()), default=DEFAULT_MODEL,
                       help=f"Model (default: {DEFAULT_MODEL}). wan-2.7-* are wavespeed-only & content-permissive.")
    p_img.add_argument("--provider", choices=["auto", "official", "wavespeed"], default="auto",
                       help="Connection route. auto = official if vendor key set, else wavespeed.")
    p_img.add_argument("--size", choices=list(SIZE_PX.keys()), default="1K",
                       help="Longest-side resolution (model-dependent). Default: 1K")
    p_img.add_argument("--aspect-ratio", choices=ASPECT_RATIOS, default="1:1",
                       help="Aspect ratio. Default: 1:1")
    p_img.add_argument("--image", action="append", default=None,
                       help="Reference image (repeatable). Required for wan-2.7-edit*.")
    p_img.add_argument("-o", "--output", required=True, help="Output PNG path")
    p_img.set_defaults(func=cmd_image)

    p_vid = sub.add_parser("video", help="Generate MP4 from prompt + start image (Seedance 直链 or wavespeed Wan)")
    p_vid.add_argument("--prompt", required=True, help="Video generation prompt (motion description)")
    p_vid.add_argument("--image", required=True, help="Starting frame image path (first_frame)")
    p_vid.add_argument("--video-model", choices=list(VIDEO_MODELS.keys()), default=DEFAULT_VIDEO_MODEL,
                       help=f"seedance-2.0 (1.0¢/s, up to 1080p) / seedance-2.0-fast (0.8¢/s) / "
                            f"seedance-2.0-mini (0.6¢/s) via Ark 直链; wan-2.7 via wavespeed. Default: {DEFAULT_VIDEO_MODEL}")
    p_vid.add_argument("--duration", type=int, required=True, help="Duration seconds (Seedance: 4-15)")
    p_vid.add_argument("--resolution", choices=["480p", "720p", "1080p"], default="720p",
                       help="Video resolution (1080p = seedance-2.0 only). Default: 720p")
    p_vid.add_argument("--ratio", choices=["1:1", "16:9", "9:16", "4:3", "3:4", "21:9", "adaptive"], default="1:1",
                       help="Aspect ratio (sprite pipeline uses 1:1). Default: 1:1")
    p_vid.set_defaults(func=cmd_video)
    p_vid.add_argument("-o", "--output", required=True, help="Output MP4 path")

    p_budget = sub.add_parser("set_budget", help="Set the asset generation budget in cents")
    p_budget.add_argument("cents", type=int, help="Budget in cents")
    p_budget.set_defaults(func=cmd_set_budget)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
