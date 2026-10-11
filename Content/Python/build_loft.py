# -*- coding: utf-8 -*-
"""
build_loft.py
=============
Unreal Engine 5 のエディタ内で実行すると、夕方のロフト風リビング
（レベル /Game/Loft/Maps/L_Loft）を自動生成します。

実行方法（どれか 1 つ）
  1. エディタのメニュー  Tools > My3DSpace > Build Loft Scene
  2. アウトプットログの入力欄を "Python" に切り替えて
         import build_loft; build_loft.main()
  3. 入力欄が "Cmd" のまま
         py build_loft.py

生成されるもの
  /Game/Loft/Maps/L_Loft        レベル（建物・家具・外構・ライト・ポストプロセス）
  /Game/Loft/Materials/*        三面投影 PBR マスターマテリアルとインスタンス
  /Game/Loft/Textures/*         RawAssets/Textures から取り込んだテクスチャ

再実行すると /Game/Loft 以下を作り直します（手で編集した内容は消えます）。
"""
import math
import os
import random
import re
import traceback

import unreal

ROOT = "/Game/Loft"
MAP_DIR = ROOT + "/Maps"
MAP_NAME = "L_Loft"
MAP_PATH = MAP_DIR + "/" + MAP_NAME
TEX_DIR = ROOT + "/Textures"
MAT_DIR = ROOT + "/Materials"

CUBE = "/Engine/BasicShapes/Cube"
CYL = "/Engine/BasicShapes/Cylinder"
SPHERE = "/Engine/BasicShapes/Sphere"

EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
MP = unreal.MaterialProperty


# ------------------------------------------------------------------ utils ----
def log(msg):
    unreal.log("[Loft] " + str(msg))


def warn(msg):
    unreal.log_warning("[Loft] " + str(msg))


def project_dir():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def set_props(obj, **props):
    """set_editor_property をまとめて呼ぶ。存在しないプロパティは警告して飛ばす。"""
    for key, value in props.items():
        try:
            obj.set_editor_property(key, value)
        except Exception as exc:  # noqa: BLE001
            warn("%s: '%s' は設定できませんでした (%s)" % (type(obj).__name__, key, exc))


def vec(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def rot(pitch=0.0, yaw=0.0, roll=0.0):
    return unreal.Rotator(roll=float(roll), pitch=float(pitch), yaw=float(yaw))


def color(r, g, b, a=1.0):
    return unreal.LinearColor(float(r), float(g), float(b), float(a))


# --------------------------------------------------------- material graph ----
# ノードの入出力ピン名はエンジンのバージョンで表記が揺れるので、候補を順に試す。
OUT_ALIASES = {
    "": [""],
    "RGB": ["RGB", ""],
    "XYZ": ["XYZ", ""],
}
IN_ALIASES = {
    "Input": ["Input", "", "In"],
    "UVs": ["UVs", "Coordinates"],
    "VectorInput": ["VectorInput", "Input", ""],
    "Exponent": ["Exponent", "Exp"],
}


def connect(src, out_name, dst, in_name):
    for o in OUT_ALIASES.get(out_name, [out_name]):
        for i in IN_ALIASES.get(in_name, [in_name]):
            if MEL.connect_material_expressions(src, o, dst, i):
                return
    raise RuntimeError("ノード接続に失敗: %s[%s] -> %s[%s]" % (
        type(src).__name__, out_name, type(dst).__name__, in_name))


def connect_prop(src, out_name, prop):
    for o in OUT_ALIASES.get(out_name, [out_name]):
        if MEL.connect_material_property(src, o, prop):
            return
    raise RuntimeError("マテリアル出力への接続に失敗: %s[%s] -> %s" % (
        type(src).__name__, out_name, prop))


class Graph(object):
    """マテリアルグラフを組み立てる小さなヘルパー。"""

    def __init__(self, material):
        self.mat = material

    def node(self, cls, x, y, **props):
        expr = MEL.create_material_expression(self.mat, cls, int(x), int(y))
        for key, value in props.items():
            expr.set_editor_property(key, value)
        return expr

    def mask(self, src, out, x, y, r=False, g=False, b=False, a=False):
        m = self.node(unreal.MaterialExpressionComponentMask, x, y, r=r, g=g, b=b, a=a)
        connect(src, out, m, "Input")
        return m

    def binop(self, cls, a, ao, b, bo, x, y):
        n = self.node(cls, x, y)
        connect(a, ao, n, "A")
        connect(b, bo, n, "B")
        return n

    def mul(self, a, ao, b, bo, x, y):
        return self.binop(unreal.MaterialExpressionMultiply, a, ao, b, bo, x, y)

    def add(self, a, ao, b, bo, x, y):
        return self.binop(unreal.MaterialExpressionAdd, a, ao, b, bo, x, y)

    def div(self, a, ao, b, bo, x, y):
        return self.binop(unreal.MaterialExpressionDivide, a, ao, b, bo, x, y)

    def append(self, a, ao, b, bo, x, y):
        return self.binop(unreal.MaterialExpressionAppendVector, a, ao, b, bo, x, y)

    def scalar(self, name, default, x, y):
        return self.node(unreal.MaterialExpressionScalarParameter, x, y,
                         parameter_name=name, default_value=float(default))

    def vector(self, name, default, x, y):
        return self.node(unreal.MaterialExpressionVectorParameter, x, y,
                         parameter_name=name, default_value=default)

    def const(self, value, x, y):
        return self.node(unreal.MaterialExpressionConstant, x, y, r=float(value))

    def const3(self, rgb, x, y):
        return self.node(unreal.MaterialExpressionConstant3Vector, x, y, constant=color(*rgb))


def asset_tools():
    return unreal.AssetToolsHelpers.get_asset_tools()


def new_material(name):
    mat = asset_tools().create_asset(name, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if mat is None:
        raise RuntimeError("マテリアル %s を作成できませんでした" % name)
    return mat


def finish_material(mat):
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    return mat


def build_triplanar_master(name, tex_bc, tex_n):
    """
    ワールド座標で三面投影する PBR マスター。
    テクスチャ: BaseColor(RGB=色, A=ラフネス), Normal。
    ノーマルはワールド空間で直接合成するので tangent_space_normal=False。
    パラメータ: TileSize, Tint, RoughnessScale, RoughnessBias, NormalStrength, Metallic
    """
    mat = new_material(name)
    set_props(mat, tangent_space_normal=False)
    g = Graph(mat)

    p_tile = g.scalar("TileSize", 256.0, -2600, -500)
    p_tint = g.vector("Tint", color(1, 1, 1), -700, -800)
    p_rs = g.scalar("RoughnessScale", 1.0, -700, -250)
    p_rb = g.scalar("RoughnessBias", 0.0, -700, -150)
    p_metal = g.scalar("Metallic", 0.0, -300, 50)
    p_ns = g.scalar("NormalStrength", 1.0, -700, 400)

    # ワールド座標 → 3 方向の UV
    wp = g.node(unreal.MaterialExpressionWorldPosition, -2600, -300)
    wps = g.div(wp, "XYZ", p_tile, "", -2400, -300)
    uv_xy = g.mask(wps, "", -2200, -400, r=True, g=True)   # 床・天井 (Z 投影)
    uv_xz = g.mask(wps, "", -2200, -300, r=True, b=True)   # Y 向きの壁
    uv_yz = g.mask(wps, "", -2200, -200, g=True, b=True)   # X 向きの壁

    # 面の向きから各投影の重み
    vn = g.node(unreal.MaterialExpressionVertexNormalWS, -2600, 300)
    vabs = g.node(unreal.MaterialExpressionAbs, -2400, 300)
    connect(vn, "", vabs, "Input")
    vpow = g.node(unreal.MaterialExpressionPower, -2200, 300, const_exponent=4.0)
    connect(vabs, "", vpow, "Base")
    wx = g.mask(vpow, "", -2000, 200, r=True)
    wy = g.mask(vpow, "", -2000, 300, g=True)
    wz = g.mask(vpow, "", -2000, 400, b=True)
    wsum = g.add(g.add(wx, "", wy, "", -1800, 250), "", wz, "", -1700, 300)
    nwx = g.div(wx, "", wsum, "", -1500, 200)
    nwy = g.div(wy, "", wsum, "", -1500, 300)
    nwz = g.div(wz, "", wsum, "", -1500, 400)

    def blend(a, ao, b, bo, c, co, x, y):
        ma = g.mul(a, ao, nwx, "", x, y)
        mb = g.mul(b, bo, nwy, "", x, y + 100)
        mc = g.mul(c, co, nwz, "", x, y + 200)
        return g.add(g.add(ma, "", mb, "", x + 200, y), "", mc, "", x + 400, y + 100)

    def sample(pname, tex, uv, stype, x, y):
        t = g.node(unreal.MaterialExpressionTextureSampleParameter2D, x, y,
                   parameter_name=pname, texture=tex, sampler_type=stype)
        connect(uv, "", t, "UVs")
        return t

    st_color = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
    st_normal = unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL

    # ベースカラー + ラフネス（アルファ）
    bc_x = sample("BaseColor", tex_bc, uv_yz, st_color, -1300, -900)
    bc_y = sample("BaseColor", tex_bc, uv_xz, st_color, -1300, -700)
    bc_z = sample("BaseColor", tex_bc, uv_xy, st_color, -1300, -500)
    col = blend(bc_x, "RGB", bc_y, "RGB", bc_z, "RGB", -1000, -900)
    col_t = g.mul(col, "", p_tint, "", -300, -800)
    connect_prop(col_t, "", MP.MP_BASE_COLOR)

    rough = blend(bc_x, "A", bc_y, "A", bc_z, "A", -1000, -300)
    rough_s = g.mul(rough, "", p_rs, "", -400, -250)
    rough_b = g.add(rough_s, "", p_rb, "", -250, -250)
    rough_c = g.node(unreal.MaterialExpressionClamp, -100, -250, min_default=0.0, max_default=1.0)
    connect(rough_b, "", rough_c, "Input")
    connect_prop(rough_c, "", MP.MP_ROUGHNESS)
    connect_prop(p_metal, "", MP.MP_METALLIC)

    # ノーマル: 各投影のタンジェント空間法線をワールド軸に振り分けて合成
    n_x = sample("Normal", tex_n, uv_yz, st_normal, -1300, 300)
    n_y = sample("Normal", tex_n, uv_xz, st_normal, -1300, 500)
    n_z = sample("Normal", tex_n, uv_xy, st_normal, -1300, 700)
    zero = g.const(0.0, -1100, 950)

    def rgb_parts(t, y):
        return (g.mask(t, "RGB", -1100, y, r=True),
                g.mask(t, "RGB", -1100, y + 60, g=True),
                g.mask(t, "RGB", -1100, y + 120, b=True))

    xr, xg, xb = rgb_parts(n_x, 300)
    yr, yg, yb = rgb_parts(n_y, 500)
    zr, zg, zb = rgb_parts(n_z, 700)
    lat_x = g.append(g.append(zero, "", xr, "", -900, 300), "", xg, "", -800, 300)   # (0, nx, ny)
    lat_y = g.append(g.append(yr, "", zero, "", -900, 500), "", yg, "", -800, 500)   # (nx, 0, ny)
    lat_z = g.append(g.append(zr, "", zg, "", -900, 700), "", zero, "", -800, 700)   # (nx, ny, 0)
    lateral = blend(lat_x, "", lat_y, "", lat_z, "", -700, 500)
    lateral_s = g.mul(lateral, "", p_ns, "", -200, 500)
    up = blend(xb, "", yb, "", zb, "", -700, 1000)
    along_n = g.mul(up, "", vn, "", -200, 1000)
    nsum = g.add(lateral_s, "", along_n, "", -50, 700)
    nrm = g.node(unreal.MaterialExpressionNormalize, 100, 700)
    connect(nsum, "", nrm, "VectorInput")
    connect_prop(nrm, "", MP.MP_NORMAL)

    return finish_material(mat)


def build_solid_master(name):
    """単色 PBR。パラメータ: Color, Roughness, Metallic"""
    mat = new_material(name)
    g = Graph(mat)
    p_col = g.vector("Color", color(0.5, 0.5, 0.5), -400, -200)
    p_rough = g.scalar("Roughness", 0.5, -400, 0)
    p_metal = g.scalar("Metallic", 0.0, -400, 100)
    connect_prop(p_col, "", MP.MP_BASE_COLOR)
    connect_prop(p_rough, "", MP.MP_ROUGHNESS)
    connect_prop(p_metal, "", MP.MP_METALLIC)
    return finish_material(mat)


def build_emissive_master(name):
    """発光（電球など）。パラメータ: Color, Strength"""
    mat = new_material(name)
    g = Graph(mat)
    p_col = g.vector("Color", color(1.0, 0.82, 0.6), -500, -100)
    p_str = g.scalar("Strength", 4000.0, -500, 100)
    emis = g.mul(p_col, "", p_str, "", -250, 0)
    black = g.const3((0.02, 0.02, 0.02), -500, -300)
    connect_prop(black, "", MP.MP_BASE_COLOR)
    connect_prop(emis, "", MP.MP_EMISSIVE_COLOR)
    return finish_material(mat)


def build_glass(name):
    """窓ガラス。半透明 + Surface ForwardShading で反射が乗る。"""
    mat = new_material(name)
    set_props(mat, blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
    set_props(mat, translucency_lighting_mode=unreal.TranslucencyLightingMode.TLM_SURFACE_FORWARD_SHADING)
    set_props(mat, screen_space_reflections=True)
    g = Graph(mat)
    base = g.const3((0.02, 0.025, 0.03), -500, -300)
    rough = g.const(0.03, -500, -150)
    spec = g.const(1.0, -500, -50)
    opacity = g.const(0.12, -500, 50)
    connect_prop(base, "", MP.MP_BASE_COLOR)
    connect_prop(rough, "", MP.MP_ROUGHNESS)
    connect_prop(spec, "", MP.MP_SPECULAR)
    connect_prop(opacity, "", MP.MP_OPACITY)
    return finish_material(mat)


def make_instance(name, parent, scalars=None, vectors=None, textures=None):
    mi = asset_tools().create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant,
                                    unreal.MaterialInstanceConstantFactoryNew())
    if mi is None:
        raise RuntimeError("マテリアルインスタンス %s を作成できませんでした" % name)
    MEL.set_material_instance_parent(mi, parent)
    for key, value in (scalars or {}).items():
        MEL.set_material_instance_scalar_parameter_value(mi, key, float(value))
    for key, value in (vectors or {}).items():
        MEL.set_material_instance_vector_parameter_value(mi, key, color(*value))
    for key, value in (textures or {}).items():
        if value is not None:
            MEL.set_material_instance_texture_parameter_value(mi, key, value)
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    return mi


# --------------------------------------------------------------- textures ----
TEXTURE_SETS = ("Wood", "Concrete", "Plaster", "Fabric")


def import_textures():
    raw_dir = os.path.join(project_dir(), "RawAssets", "Textures")
    tasks = []
    for name in TEXTURE_SETS:
        for suffix in ("BC", "N"):
            filename = os.path.join(raw_dir, "T_%s_%s.png" % (name, suffix))
            if not os.path.isfile(filename):
                warn("テクスチャが見つかりません: %s" % filename)
                continue
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", filename)
            task.set_editor_property("destination_path", TEX_DIR)
            task.set_editor_property("destination_name", "T_%s_%s" % (name, suffix))
            task.set_editor_property("automated", True)
            task.set_editor_property("save", False)
            task.set_editor_property("replace_existing", True)
            tasks.append(task)
    if tasks:
        asset_tools().import_asset_tasks(tasks)

    textures = {}
    for name in TEXTURE_SETS:
        for suffix in ("BC", "N"):
            path = "%s/T_%s_%s" % (TEX_DIR, name, suffix)
            tex = unreal.load_asset(path) if EAL.does_asset_exist(path) else None
            if tex is None:
                warn("読み込めませんでした: %s" % path)
                textures[(name, suffix)] = None
                continue
            if suffix == "N":
                set_props(tex, srgb=False,
                          compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP,
                          lod_group=unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
            else:
                set_props(tex, srgb=True,
                          compression_settings=unreal.TextureCompressionSettings.TC_DEFAULT)
            EAL.save_loaded_asset(tex)
            textures[(name, suffix)] = tex
    return textures


# -------------------------------------------------------------- materials ----
BOOK_COLORS = [
    (0.55, 0.12, 0.10), (0.12, 0.22, 0.40), (0.20, 0.35, 0.22), (0.80, 0.68, 0.40),
    (0.90, 0.88, 0.82), (0.10, 0.10, 0.11), (0.60, 0.40, 0.20), (0.30, 0.15, 0.35),
    (0.75, 0.30, 0.15), (0.25, 0.45, 0.50),
]


def build_solid_materials():
    """テクスチャを使わないマテリアル一式（金属・塗装・本・ガラス・発光）。"""
    M = {}
    solid = build_solid_master("M_Solid")

    def S(name, rgb, rough=0.5, metal=0.0):
        return make_instance(name, solid, scalars={"Roughness": rough, "Metallic": metal},
                             vectors={"Color": rgb})

    M["metal_black"] = S("MI_MetalBlack", (0.02, 0.02, 0.022), 0.35, 1.0)
    M["metal_brushed"] = S("MI_MetalBrushed", (0.56, 0.57, 0.58), 0.32, 1.0)
    M["white"] = S("MI_WhitePaint", (0.86, 0.86, 0.84), 0.45)
    M["quartz"] = S("MI_Quartz", (0.88, 0.87, 0.84), 0.18)
    M["ceramic"] = S("MI_Ceramic", (0.90, 0.88, 0.83), 0.22)
    M["leaf"] = S("MI_Leaf", (0.05, 0.16, 0.05), 0.65)
    M["soil"] = S("MI_Soil", (0.08, 0.06, 0.05), 0.95)
    M["dark"] = S("MI_DarkPaint", (0.06, 0.055, 0.05), 0.5)
    M["art_teal"] = S("MI_ArtTeal", (0.05, 0.22, 0.24), 0.85)
    M["art_rust"] = S("MI_ArtRust", (0.48, 0.17, 0.09), 0.85)
    M["kraft"] = S("MI_Kraft", (0.52, 0.40, 0.27), 0.9)
    M["books"] = [S("MI_Book_%02d" % i, rgb, 0.75) for i, rgb in enumerate(BOOK_COLORS)]

    M["glass"] = build_glass("M_Glass")
    emissive = build_emissive_master("M_Emissive")
    M["bulb"] = make_instance("MI_Bulb", emissive, scalars={"Strength": 4000.0},
                              vectors={"Color": (1.0, 0.80, 0.58)})
    M["globe"] = make_instance("MI_Globe", emissive, scalars={"Strength": 300.0},
                               vectors={"Color": (1.0, 0.86, 0.68)})
    return M


def build_textured_materials(textures):
    """三面投影マスターと、床・壁・布などのインスタンス。"""
    M = {}

    def tex(n, s):
        return textures.get((n, s))

    if tex("Wood", "BC") is None or tex("Wood", "N") is None:
        raise RuntimeError("テクスチャが無いので三面投影マテリアルを作れません")

    tri = build_triplanar_master("M_Triplanar", tex("Wood", "BC"), tex("Wood", "N"))

    def T(name, texset, tile, tint=(1, 1, 1), rs=1.0, rb=0.0, ns=1.0):
        return make_instance(name, tri,
                             scalars={"TileSize": tile, "RoughnessScale": rs, "RoughnessBias": rb,
                                      "NormalStrength": ns},
                             vectors={"Tint": tint},
                             textures={"BaseColor": tex(texset, "BC"), "Normal": tex(texset, "N")})

    M["wood_floor"] = T("MI_WoodFloor", "Wood", 256)
    M["wood_table"] = T("MI_WoodTable", "Wood", 120, (1.0, 0.96, 0.9), rs=0.9)
    M["wood_dark"] = T("MI_WoodDark", "Wood", 180, (0.30, 0.24, 0.20), rs=0.9, rb=0.05)
    M["plaster"] = T("MI_Plaster", "Plaster", 100)
    M["concrete"] = T("MI_Concrete", "Concrete", 250)
    M["concrete_ground"] = T("MI_ConcreteGround", "Concrete", 420, (0.55, 0.55, 0.56), rb=0.12)
    M["building_a"] = T("MI_BuildingA", "Concrete", 1400, (0.72, 0.70, 0.68), rb=0.1)
    M["building_b"] = T("MI_BuildingB", "Concrete", 1800, (0.46, 0.48, 0.52), rb=0.1)
    M["building_c"] = T("MI_BuildingC", "Concrete", 1100, (0.60, 0.52, 0.46), rb=0.1)
    M["fabric_sofa"] = T("MI_FabricSofa", "Fabric", 40, (0.14, 0.17, 0.22), ns=1.2)
    M["fabric_cushion"] = T("MI_FabricCushion", "Fabric", 40, (0.42, 0.40, 0.36), ns=1.2)
    M["fabric_rug"] = T("MI_FabricRug", "Fabric", 70, (0.50, 0.44, 0.36), ns=1.5)
    M["fabric_pillow"] = T("MI_FabricPillow", "Fabric", 30, (0.55, 0.22, 0.12), ns=1.2)
    return M


def build_fallback_materials(M):
    """三面投影マテリアルが作れなかったときに単色で代用する。"""
    solid_path = MAT_DIR + "/M_Solid"
    solid = unreal.load_asset(solid_path) if EAL.does_asset_exist(solid_path) else build_solid_master("M_Solid")

    def S(name, rgb, rough=0.6):
        return make_instance(name, solid, scalars={"Roughness": rough}, vectors={"Color": rgb})

    fallback = {
        "wood_floor": ((0.52, 0.36, 0.22), 0.45), "wood_table": ((0.6, 0.45, 0.3), 0.45),
        "wood_dark": ((0.18, 0.13, 0.10), 0.5), "plaster": ((0.85, 0.84, 0.81), 0.75),
        "concrete": ((0.5, 0.49, 0.47), 0.8), "concrete_ground": ((0.3, 0.3, 0.3), 0.85),
        "building_a": ((0.6, 0.58, 0.55), 0.8), "building_b": ((0.4, 0.42, 0.45), 0.8),
        "building_c": ((0.5, 0.44, 0.4), 0.8), "fabric_sofa": ((0.12, 0.15, 0.2), 0.9),
        "fabric_cushion": ((0.4, 0.38, 0.34), 0.9), "fabric_rug": ((0.48, 0.42, 0.34), 0.95),
        "fabric_pillow": ((0.5, 0.2, 0.1), 0.9),
        "metal_black": ((0.02, 0.02, 0.022), 0.35), "metal_brushed": ((0.56, 0.57, 0.58), 0.32),
        "white": ((0.86, 0.86, 0.84), 0.45), "quartz": ((0.88, 0.87, 0.84), 0.18),
        "ceramic": ((0.90, 0.88, 0.83), 0.22), "leaf": ((0.05, 0.16, 0.05), 0.65),
        "soil": ((0.08, 0.06, 0.05), 0.95), "dark": ((0.06, 0.055, 0.05), 0.5),
        "art_teal": ((0.05, 0.22, 0.24), 0.85), "art_rust": ((0.48, 0.17, 0.09), 0.85),
        "kraft": ((0.52, 0.40, 0.27), 0.9), "glass": ((0.6, 0.65, 0.7), 0.05),
        "bulb": ((1.0, 0.9, 0.7), 0.3), "globe": ((1.0, 0.9, 0.7), 0.3),
    }
    if "books" not in M:
        M["books"] = [S("MI_Fallback_Book_%02d" % i, rgb, 0.75) for i, rgb in enumerate(BOOK_COLORS)]
    for key, (rgb, rough) in fallback.items():
        if key not in M:
            M[key] = S("MI_Fallback_%s" % key, rgb, rough)
    return M


# ------------------------------------------------------------------ scene ----
class Scene(object):
    def __init__(self):
        self.eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.cube = unreal.load_asset(CUBE)
        self.cyl = unreal.load_asset(CYL)
        self.sphere = unreal.load_asset(SPHERE)
        self.count = 0

    # --- static meshes -------------------------------------------------
    def mesh(self, mesh, label, loc, size, mat, folder, rotation=(0, 0, 0), shadow=True):
        actor = self.eas.spawn_actor_from_class(unreal.StaticMeshActor, vec(*loc),
                                                rot(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        if actor is None:
            warn("スポーン失敗: " + label)
            return None
        actor.set_actor_label(label)
        comp = actor.static_mesh_component
        comp.set_static_mesh(mesh)
        actor.set_actor_scale3d(vec(size[0] / 100.0, size[1] / 100.0, size[2] / 100.0))
        if mat is not None:
            comp.set_material(0, mat)
        if not shadow:
            comp.set_cast_shadow(False)
            set_props(comp, affect_distance_field_lighting=False, affect_dynamic_indirect_lighting=False)
        actor.set_folder_path(folder)
        self.count += 1
        return actor

    def box(self, label, x0, x1, y0, y1, z0, z1, mat, folder, shadow=True):
        return self.mesh(self.cube, label, ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0),
                         (x1 - x0, y1 - y0, z1 - z0), mat, folder, shadow=shadow)

    def cylinder(self, label, cx, cy, z0, z1, radius, mat, folder):
        return self.mesh(self.cyl, label, (cx, cy, (z0 + z1) / 2.0),
                         (2 * radius, 2 * radius, z1 - z0), mat, folder)

    def ball(self, label, cx, cy, cz, radius, mat, folder, shadow=True):
        return self.mesh(self.sphere, label, (cx, cy, cz), (2 * radius, 2 * radius, 2 * radius),
                         mat, folder, shadow=shadow)

    # --- lights ----------------------------------------------------------
    def light(self, actor_cls, comp_cls, label, loc, rotation=(0, 0, 0), **props):
        actor = self.eas.spawn_actor_from_class(actor_cls, vec(*loc),
                                                rot(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        if actor is None:
            warn("ライトのスポーン失敗: " + label)
            return None
        actor.set_actor_label(label)
        actor.set_folder_path("Lighting")
        comp = actor.get_component_by_class(comp_cls)
        if comp is None:
            warn("ライトコンポーネントが取れません: " + label)
            return actor
        try:
            comp.set_mobility(unreal.ComponentMobility.MOVABLE)
        except Exception as exc:  # noqa: BLE001
            warn("mobility: %s" % exc)
        set_props(comp, **props)
        self.count += 1
        return actor

    def point_light(self, label, loc, lumens, kelvin=2700.0, radius=600.0, scatter=0.3):
        return self.light(unreal.PointLight, unreal.PointLightComponent, label, loc,
                          intensity_units=unreal.LightUnits.LUMENS, intensity=float(lumens),
                          use_temperature=True, temperature=float(kelvin),
                          attenuation_radius=float(radius), source_radius=3.0, soft_source_radius=10.0,
                          cast_shadows=True, volumetric_scattering_intensity=float(scatter),
                          specular_scale=1.0)

    def actor(self, actor_cls, label, loc, rotation=(0, 0, 0), folder="Misc"):
        actor = self.eas.spawn_actor_from_class(actor_cls, vec(*loc),
                                                rot(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        if actor is not None:
            actor.set_actor_label(label)
            actor.set_folder_path(folder)
            self.count += 1
        return actor


# 室内: X -400..400, Y -300..300, Z 0..320  (単位 cm)。窓は +X 側の壁。
def build_architecture(S, M):
    F = "Architecture"
    S.box("Floor_Wood", -420, 420, -320, 320, -26, 0, M["wood_floor"], F)
    S.box("Ceiling", -420, 420, -320, 320, 320, 340, M["concrete"], F)
    S.box("Roof_Overhang", 420, 540, -320, 320, 320, 340, M["concrete"], F)
    S.box("Wall_Back", -420, -400, -320, 320, 0, 320, M["plaster"], F)
    S.box("Wall_Left", -420, 420, -320, -300, 0, 320, M["plaster"], F)
    S.box("Wall_Right", -420, 420, 300, 320, 0, 320, M["plaster"], F)
    S.box("Wall_Front_PierL", 400, 420, -320, -250, 0, 320, M["plaster"], F)
    S.box("Wall_Front_PierR", 400, 420, 250, 320, 0, 320, M["plaster"], F)
    S.box("Wall_Front_Sill", 400, 420, -250, 250, 0, 45, M["plaster"], F)
    S.box("Wall_Front_Header", 400, 420, -250, 250, 290, 320, M["plaster"], F)
    for i, x in enumerate((-200, 0, 200)):
        S.box("Beam_%d" % i, x - 15, x + 15, -300, 300, 292, 320, M["wood_dark"], F)
    # 巾木
    S.box("Skirting_Back_A", -400, -398.5, -300, -215, 0, 10, M["white"], F)
    S.box("Skirting_Back_B", -400, -398.5, -105, 300, 0, 10, M["white"], F)
    S.box("Skirting_Left", -400, 400, -300, -298.5, 0, 10, M["white"], F)
    S.box("Skirting_Right", -400, 400, 298.5, 300, 0, 10, M["white"], F)
    S.box("Skirting_Front", 398.5, 400, -300, 300, 0, 10, M["white"], F)
    # ドア（奥の壁、左寄り）
    S.box("Door_Frame", -400, -396, -215, -105, 0, 215, M["white"], F)
    S.box("Door_Panel", -397.5, -395.5, -210, -110, 0, 210, M["dark"], F)
    S.box("Door_HandleRose", -396, -394, -122, -118, 98, 102, M["metal_brushed"], F)
    S.box("Door_HandleBar", -395.5, -393.5, -132, -112, 99.5, 101.5, M["metal_brushed"], F)


def build_window(S, M):
    F = "Architecture/Window"
    mb = M["metal_black"]
    S.box("WinFrame_Bottom", 404, 412, -250, 250, 45, 50, mb, F)
    S.box("WinFrame_Top", 404, 412, -250, 250, 285, 290, mb, F)
    S.box("WinFrame_Left", 404, 412, -250, -245, 45, 290, mb, F)
    S.box("WinFrame_Right", 404, 412, 245, 250, 45, 290, mb, F)
    for i, y in enumerate((-125, 0, 125)):
        S.box("WinMullion_%d" % i, 404, 412, y - 2.5, y + 2.5, 50, 285, mb, F)
    S.box("WinTransom", 404, 412, -245, 245, 213, 217, mb, F)
    S.box("WinGlass", 407.5, 408.5, -245, 245, 50, 285, M["glass"], F, shadow=False)


def build_living(S, M, rng):
    F = "Furniture/Living"
    S.box("Rug", -240, 120, -170, 170, 0, 1.5, M["fabric_rug"], F)
    # ソファ（窓の方を向く）
    S.box("Sofa_Base", -205, -110, -120, 120, 12, 42, M["fabric_sofa"], F)
    for i, (x, y) in enumerate(((-195, -110), (-120, -110), (-195, 110), (-120, 110))):
        S.cylinder("Sofa_Leg_%d" % i, x, y, 0, 12.5, 2.5, M["metal_black"], F)
    S.box("Sofa_Back", -205, -185, -120, 120, 41.5, 88, M["fabric_sofa"], F)
    S.box("Sofa_ArmL", -205, -110, -120, -100, 41.5, 62, M["fabric_sofa"], F)
    S.box("Sofa_ArmR", -205, -110, 100, 120, 41.5, 62, M["fabric_sofa"], F)
    S.box("Sofa_SeatL", -183, -112, -98, -2, 41.5, 54, M["fabric_cushion"], F)
    S.box("Sofa_SeatR", -183, -112, 2, 98, 41.5, 54, M["fabric_cushion"], F)
    S.box("Sofa_BackCushionL", -185.5, -172, -98, -2, 53.5, 86, M["fabric_cushion"], F)
    S.box("Sofa_BackCushionR", -185.5, -172, 2, 98, 53.5, 86, M["fabric_cushion"], F)
    S.box("Sofa_Pillow", -178, -160, -92, -48, 53.5, 82, M["fabric_pillow"], F)
    # コーヒーテーブル
    S.box("CoffeeTable_Top", -50, 70, -55, 55, 40, 44, M["wood_dark"], F)
    for i, (x, y) in enumerate(((-45, -50), (65, -50), (-45, 50), (65, 50))):
        S.cylinder("CoffeeTable_Leg_%d" % i, x, y, 0, 40.5, 2.0, M["metal_black"], F)
    S.box("Table_Book_A", -30, -4, -40, -20, 43.5, 46.5, M["books"][4], F)
    S.box("Table_Book_B", -28, -6, -38, -18, 46, 48.5, M["books"][0], F)
    S.cylinder("Table_Bowl", 30, 15, 43.5, 50, 11, M["ceramic"], F)
    # サイドボード（左の壁）
    S.box("Sideboard", -170, 70, -298, -255, 10, 62, M["wood_dark"], F)
    for i, (x, y) in enumerate(((-165, -295), (65, -295), (-165, -258), (65, -258))):
        S.cylinder("Sideboard_Leg_%d" % i, x, y, 0, 10.5, 2.0, M["metal_black"], F)
    S.cylinder("Sideboard_Vase", -120, -277, 61.5, 92, 7, M["ceramic"], F)
    S.box("Sideboard_BookStack", 10, 38, -290, -265, 61.5, 70, M["books"][3], F)
    # アート（左の壁）
    S.box("Art1_Frame", -160, -60, -300, -297, 120, 200, M["dark"], F)
    S.box("Art1_Canvas", -156, -64, -297.2, -296.4, 124, 196, M["art_teal"], F)
    S.box("Art2_Frame", -40, 60, -300, -297, 120, 200, M["dark"], F)
    S.box("Art2_Canvas", -36, 56, -297.2, -296.4, 124, 196, M["art_rust"], F)
    # フロアランプ（球形シェード、中にポイントライト）
    S.cylinder("FloorLamp_Base", -215, 165, 0, 2, 14, M["metal_black"], F)
    S.cylinder("FloorLamp_Pole", -215, 165, 2, 150, 1.2, M["metal_black"], F)
    S.ball("FloorLamp_Globe", -215, 165, 160, 17, M["globe"], F, shadow=False)
    S.point_light("FloorLamp_Light", (-215, 165, 160), 700, 2700, 650, 0.3)
    # 観葉植物（左奥のコーナー）
    S.cylinder("Plant_Pot", -340, -240, 0, 40, 18, M["ceramic"], F)
    S.cylinder("Plant_Soil", -340, -240, 39, 41, 16, M["soil"], F)
    S.cylinder("Plant_Trunk", -340, -240, 40, 85, 2, M["wood_dark"], F)
    for i in range(8):
        a = rng.uniform(0, 6.283)
        d = rng.uniform(0, 26)
        S.ball("Plant_Leaf_%d" % i, -340 + d * math.cos(a), -240 + d * math.sin(a),
               rng.uniform(80, 125), rng.uniform(20, 32), M["leaf"], F)


def build_dining(S, M):
    F = "Furniture/Dining"
    S.box("DiningTable_Top", 190, 340, 60, 150, 72, 76, M["wood_table"], F)
    for i, (x, y) in enumerate(((198, 68), (332, 68), (198, 142), (332, 142))):
        S.cylinder("DiningTable_Leg_%d" % i, x, y, 0, 72.5, 2.5, M["metal_black"], F)
    S.cylinder("Dining_Bottle", 250, 105, 75.5, 100, 3.5, M["art_teal"], F)
    S.cylinder("Dining_Cup_A", 268, 95, 75.5, 84, 3.6, M["ceramic"], F)
    S.cylinder("Dining_Cup_B", 282, 118, 75.5, 84, 3.6, M["ceramic"], F)

    def chair(idx, cx, cy, facing):
        # facing: +1 = +Y を向く（背もたれは -Y 側）, -1 = その逆
        S.box("Chair%d_Seat" % idx, cx - 21, cx + 21, cy - 21, cy + 21, 43, 47, M["wood_dark"], F)
        for j, (dx, dy) in enumerate(((-18, -18), (18, -18), (-18, 18), (18, 18))):
            S.cylinder("Chair%d_Leg_%d" % (idx, j), cx + dx, cy + dy, 0, 43.5, 1.6, M["metal_black"], F)
        by0 = cy - 21 if facing > 0 else cy + 18
        S.box("Chair%d_Back" % idx, cx - 21, cx + 21, by0, by0 + 3, 46.5, 90, M["wood_dark"], F)

    chair(0, 228, 35, +1)
    chair(1, 302, 35, +1)
    chair(2, 228, 175, -1)
    chair(3, 302, 175, -1)
    # ペンダントライト
    for i, x in enumerate((225, 270, 315)):
        S.cylinder("Pendant%d_Cord" % i, x, 105, 235, 320, 0.4, M["metal_black"], F)
        S.cylinder("Pendant%d_Shade" % i, x, 105, 215, 235, 11, M["metal_black"], F)
        S.ball("Pendant%d_Bulb" % i, x, 105, 212, 3, M["bulb"], F, shadow=False)
        S.point_light("Pendant%d_Light" % i, (x, 105, 212), 550, 2700, 600, 0.35)


def build_kitchen(S, M):
    F = "Furniture/Kitchen"
    S.box("Kitchen_ToeKick", -335, -85, 246, 300, 0, 10.5, M["dark"], F)
    S.box("Kitchen_BaseCabinet", -340, -80, 240, 300, 10, 88, M["wood_dark"], F)
    S.box("Kitchen_Countertop", -342, -78, 238, 300, 88, 92, M["quartz"], F)
    S.box("Kitchen_UpperCabinet", -340, -80, 262, 300, 150, 225, M["white"], F)
    S.box("Kitchen_Fridge", -72, -2, 232, 300, 0, 205, M["metal_brushed"], F)
    S.box("Kitchen_FridgeHandle", -62, -58, 230.5, 232, 60, 150, M["metal_black"], F)
    for i in range(5):
        x = -330 + i * 52
        S.box("Kitchen_DrawerHandle_%d" % i, x, x + 36, 238.5, 240, 76, 78, M["metal_black"], F)
    S.cylinder("Kitchen_Kettle", -270, 275, 92, 112, 9, M["metal_brushed"], F)
    S.cylinder("Kitchen_Kettle_Lid", -270, 275, 112, 115, 3, M["dark"], F)
    S.box("Kitchen_CuttingBoard", -215, -180, 258, 282, 92, 94, M["wood_table"], F)
    S.box("Kitchen_Shelf", -330, -100, 280, 300, 110, 112.5, M["wood_dark"], F)
    for i in range(4):
        x = -315 + i * 55
        S.cylinder("Kitchen_Jar_%d" % i, x, 290, 112.5, 112.5 + 14 + 3 * (i % 2), 5.5, M["glass"], F)
    # 吊り戸棚下のライン照明（レクトライト）
    S.light(unreal.RectLight, unreal.RectLightComponent, "Kitchen_UnderCabinetLight",
            (-210, 281, 149), rotation=(-90, 0, 0),
            intensity_units=unreal.LightUnits.LUMENS, intensity=450.0,
            use_temperature=True, temperature=3200.0, source_width=250.0, source_height=6.0,
            attenuation_radius=300.0, barn_door_angle=60.0, cast_shadows=True,
            volumetric_scattering_intensity=0.2)


def build_shelf(S, M, rng):
    F = "Furniture/Shelf"
    S.box("Shelf_SideL", -398, -366, 120, 122.5, 0, 220, M["wood_dark"], F)
    S.box("Shelf_SideR", -398, -366, 277.5, 280, 0, 220, M["wood_dark"], F)
    for i, z in enumerate((0, 55, 110, 165, 217.5)):
        S.box("Shelf_Board_%d" % i, -398, -366, 122.5, 277.5, z, z + 2.5, M["wood_dark"], F)
    for shelf_idx, z in enumerate((57.5, 112.5, 167.5)):
        y = 125.0
        limit = 275.0 - (50 if shelf_idx == 2 else 0)
        n = 0
        while y < limit:
            if rng.random() < 0.12:
                y += rng.uniform(4, 10)
                continue
            w = rng.uniform(2.2, 5.0)
            h = rng.uniform(19, 29)
            d = rng.uniform(18, 25)
            if y + w > limit:
                break
            mat = M["books"][rng.randrange(len(M["books"]))]
            S.box("Book_%d_%d" % (shelf_idx, n), -396, -396 + d, y, y + w, z - 0.3, z + h, mat, F)
            y += w
            n += 1
    S.box("Shelf_BoxA", -395, -368, 128, 158, 2.2, 32, M["kraft"], F)
    S.box("Shelf_BoxB", -395, -368, 162, 192, 2.2, 32, M["kraft"], F)
    S.cylinder("Shelf_Vase", -382, 250, 167.2, 197, 7, M["ceramic"], F)
    S.box("Shelf_Frame", -394, -392, 232, 270, 167.2, 198, M["dark"], F)
    S.box("Shelf_FramePhoto", -392.2, -391.6, 235, 267, 170.2, 195, M["art_rust"], F)


def build_terrace(S, M):
    F = "Exterior/Terrace"
    S.box("Terrace_Floor", 420, 740, -320, 320, -26, -1, M["concrete"], F)
    mb = M["metal_black"]
    for i, y in enumerate(range(-300, 301, 100)):
        S.cylinder("Rail_Post_%d" % i, 735, y, -1, 106, 2, mb, F)
    S.box("Rail_Top", 733, 737, -320, 320, 106, 110, mb, F)
    S.box("Rail_Mid", 733.8, 736.2, -320, 320, 55, 57, mb, F)
    for side, y in (("L", -315), ("R", 315)):
        for i, x in enumerate(range(480, 741, 85)):
            S.cylinder("Rail_%s_Post_%d" % (side, i), min(x, 735), y, -1, 106, 2, mb, F)
        S.box("Rail_%s_Top" % side, 420, 737, y - 2, y + 2, 106, 110, mb, F)
        S.box("Rail_%s_Mid" % side, 420, 737, y - 1.2, y + 1.2, 55, 57, mb, F)
    S.box("Planter", 620, 700, -300, -220, -1, 45, M["concrete"], F)
    S.box("Planter_Soil", 624, 696, -296, -224, 42, 44, M["soil"], F)
    for i, (dx, dy, dz, r) in enumerate(((0, 0, 70, 30), (-22, 18, 62, 22), (20, -16, 60, 20),
                                         (10, 22, 85, 18), (-14, -20, 84, 17))):
        S.ball("Planter_Leaf_%d" % i, 660 + dx, -260 + dy, dz, r, M["leaf"], F)


def build_city(S, M):
    F = "Exterior/City"
    S.box("Ground", -6000, 9000, -6000, 6000, -45, -22, M["concrete_ground"], F)
    S.box("Street_Curb", 900, 930, -6000, 6000, -22, -8, M["concrete"], F)
    buildings = (
        (1500, 2100, -1800, -1100, 1400, "a"), (2300, 3300, -1500, -700, 2600, "b"),
        (1800, 2600, -3000, -2000, 900, "c"), (3600, 4600, -800, 200, 1800, "a"),
        (1200, 1700, -2600, -2100, 600, "c"), (2600, 3400, 2200, 3200, 1200, "b"),
        (4200, 5200, 2800, 3800, 2200, "c"), (6000, 7000, 4000, 5000, 4500, "b"),
        (5000, 5800, -2400, -1400, 3200, "a"), (3800, 4400, -3600, -2800, 1500, "b"),
        (-2500, -1500, -2600, -1600, 1600, "a"), (-3000, -2200, 1800, 2800, 2000, "c"),
        (1400, 2200, 3400, 4200, 800, "a"),
    )
    for i, (x0, x1, y0, y1, h, kind) in enumerate(buildings):
        S.box("Building_%02d" % i, x0, x1, y0, y1, -30, h, M["building_" + kind], F)
        # 屋上の塔屋
        S.box("Building_%02d_Roof" % i, x0 + (x1 - x0) * 0.6, x1 - (x1 - x0) * 0.1,
              y0 + (y1 - y0) * 0.2, y0 + (y1 - y0) * 0.5, h, h + 90 + (i % 3) * 40, M["building_b"], F)


def build_lighting(S):
    # 太陽: 窓 (+X) の外、やや +Y 寄りの低い位置。forward = 光の進む向き。
    S.light(unreal.DirectionalLight, unreal.DirectionalLightComponent, "Sun",
            (0, 0, 600), rotation=(-11, 200, 0),
            intensity=30000.0, use_temperature=True, temperature=4300.0,
            atmosphere_sun_light=True, light_source_angle=1.2,
            cast_shadows=True, dynamic_shadow_distance_movable_light=20000.0,
            volumetric_scattering_intensity=1.5, cast_volumetric_shadow=True,
            indirect_lighting_intensity=1.0)
    S.light(unreal.SkyLight, unreal.SkyLightComponent, "SkyLight", (0, 0, 800),
            real_time_capture=True, intensity=1.0, cast_shadows=True,
            source_type=unreal.SkyLightSourceType.SLS_CAPTURED_SCENE)
    S.actor(unreal.SkyAtmosphere, "SkyAtmosphere", (0, 0, 0), folder="Lighting")
    S.actor(unreal.VolumetricCloud, "VolumetricCloud", (0, 0, 0), folder="Lighting")
    fog = S.actor(unreal.ExponentialHeightFog, "HeightFog", (0, 0, -100), folder="Lighting")
    if fog is not None:
        fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
        if fc is not None:
            set_props(fc, fog_density=0.008, fog_height_falloff=0.3, start_distance=0.0,
                      volumetric_fog=True, volumetric_fog_scattering_distribution=0.4,
                      volumetric_fog_extinction_scale=3.0, volumetric_fog_distance=6000.0)
            for key in ("fog_inscattering_luminance", "fog_inscattering_color"):
                try:
                    fc.set_editor_property(key, color(0.58, 0.52, 0.56))
                    break
                except Exception:  # noqa: BLE001
                    continue


def build_post_process(S):
    ppv = S.actor(unreal.PostProcessVolume, "PostProcess_Global", (0, 0, 150), folder="Lighting")
    if ppv is None:
        return
    set_props(ppv, unbound=True, priority=1.0)
    s = ppv.get_editor_property("settings")
    values = [
        ("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM),
        ("auto_exposure_bias", 0.3),
        ("auto_exposure_min_brightness", 4.0),
        ("auto_exposure_max_brightness", 14.0),
        ("auto_exposure_speed_up", 3.0),
        ("auto_exposure_speed_down", 1.0),
        ("bloom_intensity", 0.25),
        ("vignette_intensity", 0.3),
        ("film_grain_intensity", 0.08),
        ("motion_blur_amount", 0.0),
        ("lens_flare_intensity", 0.0),
        ("white_temp", 6500.0),
        ("color_saturation", unreal.Vector4(1.04, 1.04, 1.04, 1.0)),
        ("color_contrast", unreal.Vector4(1.03, 1.03, 1.03, 1.0)),
        ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN),
        ("reflection_method", unreal.ReflectionMethod.LUMEN),
        ("lumen_scene_lighting_quality", 2.0),
        ("lumen_scene_detail", 2.0),
        ("lumen_final_gather_quality", 2.0),
        ("lumen_reflection_quality", 2.0),
    ]
    for key, value in values:
        try:
            s.set_editor_property("override_" + key, True)
            s.set_editor_property(key, value)
        except Exception as exc:  # noqa: BLE001
            warn("PostProcess '%s' は設定できませんでした (%s)" % (key, exc))
    set_props(ppv, settings=s)


def build_player_and_camera(S):
    S.actor(unreal.PlayerStart, "PlayerStart", (-250, -60, 95), rotation=(0, 10, 0), folder="Gameplay")
    cam = S.actor(unreal.CineCameraActor, "Camera_Hero", (-330, -150, 150), rotation=(-4, 22, 0),
                  folder="Cameras")
    if cam is not None:
        try:
            cc = cam.get_cine_camera_component()
            set_props(cc, current_focal_length=24.0, current_aperture=4.0)
        except Exception as exc:  # noqa: BLE001
            warn("カメラ設定: %s" % exc)
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        ues.set_level_viewport_camera_info(vec(-330, -150, 150), rot(pitch=-4, yaw=22))
    except Exception as exc:  # noqa: BLE001
        warn("ビューポートカメラ: %s" % exc)


# --------------------------------------------------------------- lifecycle ----
def reset_content():
    """前回の生成物を消す。生成先のマップを開いていても安全なよう、先に空マップへ退避する。"""
    try:
        unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    except Exception as exc:  # noqa: BLE001
        warn("空マップへの退避に失敗 (%s)" % exc)
    for d in (MAP_DIR, MAT_DIR, TEX_DIR):
        try:
            if EAL.does_directory_exist(d):
                EAL.delete_directory(d)
        except Exception as exc:  # noqa: BLE001
            warn("削除に失敗 %s (%s)" % (d, exc))
    for d in (ROOT, MAP_DIR, MAT_DIR, TEX_DIR):
        if not EAL.does_directory_exist(d):
            EAL.make_directory(d)


def create_level():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.new_level(MAP_PATH):
        raise RuntimeError("レベル %s を作成できませんでした" % MAP_PATH)
    return les


def save_everything(les):
    try:
        les.save_current_level()
    except Exception as exc:  # noqa: BLE001
        warn("レベル保存: %s" % exc)
    try:
        EAL.save_directory(ROOT, only_if_is_dirty=False, recursive=True)
    except Exception as exc:  # noqa: BLE001
        warn("アセット保存: %s" % exc)


def set_startup_map():
    full = "%s.%s" % (MAP_PATH, MAP_NAME)
    try:
        unreal.GameMapsSettings.set_game_default_map(full)
    except Exception as exc:  # noqa: BLE001
        warn("GameDefaultMap: %s" % exc)
    try:
        gms = unreal.get_default_object(unreal.GameMapsSettings)
        gms.set_editor_property("editor_startup_map", unreal.SoftObjectPath(full))
    except Exception as exc:  # noqa: BLE001
        warn("EditorStartupMap (memory): %s" % exc)
    try:
        cfg_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_config_dir())
        cfg = os.path.join(cfg_dir, "DefaultEngine.ini")
        with open(cfg, "r", encoding="utf-8") as fh:
            text = fh.read()
        section = "[/Script/EngineSettings.GameMapsSettings]"
        if section not in text:
            text = section + "\n" + text
        for key in ("EditorStartupMap", "GameDefaultMap"):
            pattern = r"^%s=.*$" % key
            if re.search(pattern, text, flags=re.M):
                text = re.sub(pattern, "%s=%s" % (key, full), text, flags=re.M)
            else:
                text = text.replace(section, "%s\n%s=%s" % (section, key, full), 1)
        with open(cfg, "w", encoding="utf-8") as fh:
            fh.write(text)
        log("DefaultEngine.ini の起動マップを %s にしました" % full)
    except Exception as exc:  # noqa: BLE001
        warn("DefaultEngine.ini の更新に失敗 (%s)" % exc)


def main():
    log("=== ロフトシーンの生成を開始 ===")
    rng = random.Random(7)
    with unreal.ScopedSlowTask(10, "Building Loft scene") as task:
        task.make_dialog(True)

        def step(label, fn, *args):
            task.enter_progress_frame(1, label)
            log(label)
            try:
                return fn(*args)
            except Exception:  # noqa: BLE001
                warn("%s で失敗しました:\n%s" % (label, traceback.format_exc()))
                return None

        step("前回の生成物を削除", reset_content)
        textures = step("テクスチャを読み込み", import_textures) or {}
        M = step("単色マテリアルを作成", build_solid_materials) or {}
        textured = step("テクスチャ付きマテリアルを作成", build_textured_materials, textures)
        if textured:
            M.update(textured)
        if "wood_floor" not in M or "metal_black" not in M:
            warn("一部のマテリアルが作れなかったので単色で代用します")
            step("代替マテリアルを作成", build_fallback_materials, M)

        les = step("レベルを作成", create_level)
        if les is None:
            warn("レベルを作成できなかったため中断します")
            return
        S = Scene()
        step("建物を配置", lambda: (build_architecture(S, M), build_window(S, M)))
        step("家具を配置", lambda: (build_living(S, M, rng), build_dining(S, M),
                               build_kitchen(S, M), build_shelf(S, M, rng)))
        step("外構と街を配置", lambda: (build_terrace(S, M), build_city(S, M)))
        step("ライティングとポストプロセス", lambda: (build_lighting(S), build_post_process(S),
                                           build_player_and_camera(S)))
        step("保存", lambda: (save_everything(les), set_startup_map()))
    log("=== 完了: アクター %d 個を配置しました。Alt+P で歩き回れます ===" % S.count)


if __name__ == "__main__":
    main()
