"""One-off tool: fits a track background image (frontend/track_maps/<key>.png)
onto a real recorded lap's telemetry, producing the TRACK_MAPS entry to paste
into frontend/index.html.

The image must already be a plain top-down track outline/silhouette (PNG,
transparent background, non-transparent pixels forming the road shape) --
see README for where these come from. This script finds the rotation +
uniform scale + translation that best aligns the image's outline with the
shape actually driven, by resampling both closed curves to the same number
of points and searching over rotation/mirror/cyclic-shift for the best fit
(Procrustes alignment per candidate).

Needs numpy, pillow, scikit-image (not part of the app's own requirements --
`pip install numpy pillow scikit-image` in a scratch venv is enough, this
script is never imported by the running app).

Usage:
    python3 scripts/calibrate_track_map.py <track_name> <image_path> [lap_id]
    (default lap_id: the fastest valid lap on record for that track)
    (default server: http://127.0.0.1:8081, override with ACC_SERVER_URL)

Example:
    python3 scripts/calibrate_track_map.py Monza frontend/track_maps/monza.png

Prints a ready-to-paste TRACK_MAPS entry, and a fit error (0 = perfect,
above ~0.15 usually means the wrong image/track or a bad lap was used --
sanity-check visually before trusting it).
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image
from skimage import measure

SERVER_URL = os.environ.get("ACC_SERVER_URL", "http://127.0.0.1:8081")


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def pick_fastest_lap_id(track: str) -> int:
    laps = fetch_json(f"{SERVER_URL}/api/laps?track={urllib.parse.quote(track)}")
    if not laps:
        raise SystemExit(f"No recorded laps found for track {track!r}")
    best = min(laps, key=lambda l: l["lap_time_ms"])
    return best["id"]


def resample_closed(pts: np.ndarray, n: int) -> np.ndarray:
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    arc = np.concatenate([[0], np.cumsum(seg)])
    target = np.linspace(0, arc[-1], n, endpoint=False)
    return np.stack([
        np.interp(target, arc, pts[:, 0]),
        np.interp(target, arc, pts[:, 1]),
    ], axis=1)


def image_outline(image_path: str):
    img = np.array(Image.open(image_path).convert("RGBA"))
    binary = img[..., 3] > 40
    contours = sorted(measure.find_contours(binary.astype(float), 0.5), key=len, reverse=True)
    outer = contours[0]  # (row, col) = (y, x)
    return np.stack([outer[:, 1], outer[:, 0]], axis=1), img.shape[1], img.shape[0]


def best_fit(tel_pts: np.ndarray, img_pts: np.ndarray, n: int = 300):
    tel_r = resample_closed(tel_pts, n)
    img_r = resample_closed(img_pts, n)

    def eval_shift(tel_seq, shift):
        img_shifted = np.roll(img_r, shift, axis=0)
        sc = (tel_seq[:, 0] - tel_seq[:, 0].mean()) + 1j * (tel_seq[:, 1] - tel_seq[:, 1].mean())
        dc = (img_shifted[:, 0] - img_shifted[:, 0].mean()) + 1j * (img_shifted[:, 1] - img_shifted[:, 1].mean())
        z = np.sum(np.conj(sc) * dc) / np.sum(np.conj(sc) * sc)
        err = np.sqrt(np.mean(np.abs(sc * z - dc) ** 2)) / np.sqrt(np.mean(np.abs(dc) ** 2))
        return err, z

    best = None
    for direction in (1, -1):
        for flip in (False, True):
            ts = tel_r[::direction].copy()
            if flip:
                ts[:, 0] = -ts[:, 0]
            for shift in range(0, n, 2):
                err, z = eval_shift(ts, shift)
                if best is None or err < best[0]:
                    best = (err, flip, shift, z, ts)

    err, flip, shift, z, ts = best
    for shift in range(max(0, best[2] - 2), min(n, best[2] + 3)):
        e, zz = eval_shift(ts, shift)
        if e < err:
            err, shift, z = e, shift, zz

    img_shifted = np.roll(img_r, shift, axis=0)
    return {
        "flipX": bool(flip),
        "rotationDeg": math.degrees(np.angle(z)),
        "scale": abs(z),
        "telCentroid": [float(ts[:, 0].mean()), float(ts[:, 1].mean())],
        "imgCentroid": [float(img_shifted[:, 0].mean()), float(img_shifted[:, 1].mean())],
        "err": float(err),
    }


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    track, image_path = sys.argv[1], sys.argv[2]
    lap_id = int(sys.argv[3]) if len(sys.argv) > 3 else pick_fastest_lap_id(track)

    lap = fetch_json(f"{SERVER_URL}/api/laps/{lap_id}")
    tel_pts = np.array([[s["x"], s["z"]] for s in lap["samples"]])
    img_pts, img_w, img_h = image_outline(image_path)

    fit = best_fit(tel_pts, img_pts)
    print(f"# lap {lap_id} ({lap['track']}, {lap['lap_time_ms']}ms) -- fit error {fit['err']:.4f}", file=sys.stderr)
    if fit["err"] > 0.15:
        print("# WARNING: high error -- check the image matches this track before trusting this", file=sys.stderr)

    image_ref = os.path.relpath(image_path, "frontend").replace(os.sep, "/")
    print(f'''    "{track}": {{
      image: "{image_ref}",
      imgWidth: {img_w}, imgHeight: {img_h},
      rotationDeg: {fit["rotationDeg"]},
      scale: {fit["scale"]},
      flipX: {str(fit["flipX"]).lower()},
      telCentroid: [{fit["telCentroid"][0]}, {fit["telCentroid"][1]}],
      imgCentroid: [{fit["imgCentroid"][0]}, {fit["imgCentroid"][1]}],
    }},''')


if __name__ == "__main__":
    main()
