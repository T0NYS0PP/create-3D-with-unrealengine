#!/usr/bin/env python3
"""
タイル状に繋がる PBR テクスチャを numpy で生成する（開発用。ユーザーは実行不要）。

出力（RawAssets/Textures/）:
  T_<name>_BC.png  … RGB = ベースカラー(sRGB), A = ラフネス
  T_<name>_N.png   … ノーマルマップ（R = -dh/dU, G = -dh/dV, B = up）

ノーマルの向きは build_loft.py の三面投影マテリアルがワールド空間で
直接合成する前提（接空間を使わない）なので、U/V の符号はここで固定する。
"""
import os
import sys

import numpy as np
from PIL import Image

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "RawAssets/Textures"


# ---------------------------------------------------------------- noise ----
def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def perlin(size, px, py, rng):
    """周期 (px, py) 格子のタイル可能な Perlin ノイズ。おおよそ [-1, 1]。"""
    px, py = max(1, int(px)), max(1, int(py))
    ang = rng.random((py, px)) * 2 * np.pi
    gx, gy = np.cos(ang), np.sin(ang)
    xs = np.arange(size) / size * px
    ys = np.arange(size) / size * py
    x = np.broadcast_to(xs[None, :], (size, size))
    y = np.broadcast_to(ys[:, None], (size, size))
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx = x - x0
    fy = y - y0
    x1 = (x0 + 1) % px
    y1 = (y0 + 1) % py
    x0 = x0 % px
    y0 = y0 % py

    def dot(ix, iy, dx, dy):
        return gx[iy, ix] * dx + gy[iy, ix] * dy

    n00 = dot(x0, y0, fx, fy)
    n10 = dot(x1, y0, fx - 1, fy)
    n01 = dot(x0, y1, fx, fy - 1)
    n11 = dot(x1, y1, fx - 1, fy - 1)
    u = _fade(fx)
    v = _fade(fy)
    nx0 = n00 * (1 - u) + n10 * u
    nx1 = n01 * (1 - u) + n11 * u
    return (nx0 * (1 - v) + nx1 * v) * 1.414


def fbm(size, px, py, octaves, rng, gain=0.5, lac=2.0):
    out = np.zeros((size, size))
    amp, norm = 1.0, 0.0
    for _ in range(octaves):
        out += amp * perlin(size, px, py, rng)
        norm += amp
        amp *= gain
        px *= lac
        py *= lac
    return out / norm


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def to8(a):
    return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)


def normal_map(h, strength):
    """高さ h (float, タイル可能) から法線を作る。R=-dh/dU, G=-dh/dV, B=up。"""
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    nx = -dx * strength
    ny = -dy * strength
    nz = np.ones_like(h)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / l, ny / l, nz / l], axis=-1)
    return to8(n * 0.5 + 0.5)


def save(name, rgb, rough, normal):
    os.makedirs(OUT_DIR, exist_ok=True)
    rgba = np.concatenate([to8(rgb), to8(rough)[..., None]], axis=-1)
    Image.fromarray(rgba, "RGBA").save(os.path.join(OUT_DIR, f"T_{name}_BC.png"), optimize=True)
    Image.fromarray(normal, "RGB").save(os.path.join(OUT_DIR, f"T_{name}_N.png"), optimize=True)
    print(f"  {name}: {rgba.shape[1]}x{rgba.shape[0]}")


# ------------------------------------------------------------- materials ----
def make_wood(size=1024, seed=1):
    """オークのフローリング。タイル = 256cm。板幅 16cm、板長 128cm。"""
    rng = np.random.default_rng(seed)
    plank_w, plank_l = size // 16, size // 2
    rows, cols = size // plank_w, size // plank_l
    yy, xx = np.mgrid[0:size, 0:size]
    row = yy // plank_w
    offsets = rng.integers(0, plank_l, size=rows)
    off = offsets[row]
    xl = (xx - off) % plank_l
    col = ((xx - off) // plank_l) % cols
    pid = row * cols + col
    yl = yy % plank_w
    n_planks = rows * cols
    p_bright = rng.uniform(0.80, 1.18, n_planks)[pid]
    p_warm = rng.uniform(-0.05, 0.05, n_planks)[pid]
    p_phase = rng.uniform(0, 1, n_planks)[pid]
    p_freq = rng.uniform(0.7, 1.5, n_planks)[pid]
    p_shift = rng.uniform(0, 1, n_planks)[pid]

    streak = fbm(size, 2, 24, 4, rng)       # 板の長手方向に伸びる木目
    fine = fbm(size, 6, 96, 3, rng)         # 細かい繊維
    pores = fbm(size, 48, 256, 2, rng)      # 導管
    along = fbm(size, 1, 6, 2, rng)         # 長手方向のゆるい明暗

    rings = np.sin((yl / plank_w * 5.0 * p_freq + p_phase + 1.8 * streak + 0.4 * p_shift) * 2 * np.pi)
    grain = (rings * 0.5 + 0.5) ** 2.2
    light = np.array([0.74, 0.55, 0.36])
    dark = np.array([0.46, 0.31, 0.18])
    mix = np.clip(0.12 + 0.42 * grain + 0.16 * fine, 0, 1)
    rgb = light[None, None, :] * (1 - mix[..., None]) + dark[None, None, :] * mix[..., None]
    rgb *= p_bright[..., None]
    rgb *= (1 + 0.08 * along)[..., None]
    rgb[..., 0] *= 1 + p_warm
    rgb[..., 2] *= 1 - p_warm
    pore_mask = smoothstep(0.45, 0.7, pores)
    rgb *= (1 - 0.12 * pore_mask)[..., None]

    ex = np.minimum(xl, plank_l - 1 - xl)
    ey = np.minimum(yl, plank_w - 1 - yl)
    e = np.minimum(ex, ey)
    bevel = np.clip(e / 2.5, 0, 1)
    gap = (e < 1).astype(float)
    rgb *= (1 - 0.55 * gap)[..., None]
    rgb *= (0.88 + 0.12 * bevel)[..., None]

    h = 0.75 * bevel + 0.06 * streak + 0.03 * fine - 0.05 * pore_mask
    rough = 0.36 + 0.14 * grain + 0.05 * fine + 0.12 * pore_mask + 0.35 * (1 - bevel)
    save("Wood", rgb, rough, normal_map(h, 2.2))


def make_concrete(size=1024, seed=2):
    """打ちっぱなしコンクリート。タイル = 250cm。"""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size]
    n1 = fbm(size, 3, 3, 6, rng)
    n2 = fbm(size, 12, 12, 5, rng)
    n3 = fbm(size, 48, 48, 3, rng)
    stain = fbm(size, 5, 5, 3, rng)
    pit_n = fbm(size, 40, 40, 2, rng)
    pit = smoothstep(0.52, 0.78, pit_n)
    seam = smoothstep(3.0, 0.0, np.minimum(yy, size - yy).astype(float))  # 型枠の継ぎ目
    seam = np.maximum(seam, smoothstep(2.0, 0.0, np.abs(xx - size * 0.5)))

    h = 0.5 + 0.16 * n1 + 0.10 * n2 + 0.05 * n3 - 0.35 * pit - 0.3 * seam
    g = 0.56 + 0.09 * n1 + 0.05 * n2 + 0.03 * n3 - 0.12 * pit - 0.18 * seam
    g *= 1 - 0.14 * np.clip(stain - 0.15, 0, 1)
    rgb = np.stack([g * (1.00 + 0.015 * n1), g * 0.985, g * (0.95 - 0.015 * n1)], axis=-1)
    rough = 0.78 + 0.07 * n2 + 0.06 * n3 + 0.15 * pit
    save("Concrete", rgb, rough, normal_map(h, 3.0))


def make_plaster(size=512, seed=3):
    """白い漆喰壁。タイル = 100cm。"""
    rng = np.random.default_rng(seed)
    fine = fbm(size, 24, 24, 4, rng)
    low = fbm(size, 3, 3, 3, rng)
    trowel = fbm(size, 6, 6, 2, rng)
    h = 0.5 + 0.05 * fine + 0.04 * low + 0.03 * trowel
    base = np.array([0.88, 0.865, 0.835])
    rgb = base[None, None, :] * (1 + 0.035 * low + 0.02 * fine)[..., None]
    rough = 0.72 + 0.07 * fine + 0.03 * low
    save("Plaster", rgb, rough, normal_map(h, 1.6))


def make_fabric(size=512, seed=4):
    """織物（ソファ・ラグ用）。色は Tint で付ける前提のグレー。タイル = 40cm。"""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size]
    p = 4
    weave = 0.5 + 0.25 * (np.sin(2 * np.pi * xx / p) + np.sin(2 * np.pi * yy / p))
    fuzz = fbm(size, 32, 32, 3, rng)
    fold = fbm(size, 3, 3, 3, rng)
    h = 0.5 * weave + 0.12 * fuzz + 0.10 * fold
    g = 0.62 * (0.90 + 0.16 * weave + 0.06 * fuzz + 0.05 * fold)
    rgb = np.stack([g, g, g], axis=-1)
    rough = 0.90 - 0.06 * fuzz - 0.04 * weave
    save("Fabric", rgb, rough, normal_map(h, 2.0))


if __name__ == "__main__":
    print(f"writing to {OUT_DIR}")
    make_wood()
    make_concrete()
    make_plaster()
    make_fabric()
