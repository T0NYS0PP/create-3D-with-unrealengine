# -*- coding: utf-8 -*-
"""
render_shots.py
===============
L_Loft を開き、決められた視点からスクリーンショットを撮って（既定では）エディタを終了します。
`Tools\\ue.cmd shots` が内部でこう起動します:

    UnrealEditor.exe My3DSpace.uproject -ExecCmds="py import render_shots" -unattended -NoSplash

エディタ内のアウトプットログ（Python）から手動で動かすこともできます:

    import render_shots            # 読み込んだ時点で撮影が始まる

出力先: Saved/Screenshots/WindowsEditor/Loft_<視点名>.png
環境変数: LOFT_WIDTH, LOFT_HEIGHT (解像度), LOFT_WARMUP (撮影前の待ち秒数),
          LOFT_KEEP_OPEN=1 (撮影後もエディタを閉じない)
"""
import os
import time
import traceback

import unreal

MAP_PATH = "/Game/Loft/Maps/L_Loft"

# (ファイル名, 位置 (X, Y, Z) cm, 回転 (Pitch, Yaw, Roll) 度)
VIEWS = [
    ("01_sofa_to_window", (-330, -150, 150), (-4, 22, 0)),
    ("02_window_light", (150, -200, 140), (-2, 30, 0)),
    ("03_dining", (60, -40, 160), (-8, 35, 0)),
    ("04_kitchen", (-60, 40, 150), (-8, 123, 0)),
    ("05_from_terrace", (640, 0, 150), (-5, 180, 0)),
    ("06_outside", (1200, -500, 200), (-6, 160, 0)),
]

WIDTH = int(os.environ.get("LOFT_WIDTH", "1920"))
HEIGHT = int(os.environ.get("LOFT_HEIGHT", "1080"))
WARMUP_SEC = float(os.environ.get("LOFT_WARMUP", "30"))
SETTLE_SEC = 4.0      # 視点を変えてから撮影するまで（Lumen / TSR の収束待ち）
AFTER_SHOT_SEC = 2.5  # 撮影要求からファイル書き出しまでの余裕
KEEP_OPEN = os.environ.get("LOFT_KEEP_OPEN", "0") == "1"

_state = {"phase": "load", "t0": time.time(), "index": 0, "handle": None, "camera": None}


def _log(msg):
    unreal.log("[LoftShots] " + str(msg))


def _finish(reason):
    _log("終了: " + reason)
    if _state["handle"] is not None:
        try:
            unreal.unregister_slate_post_tick_callback(_state["handle"])
        except Exception:  # noqa: BLE001
            pass
        _state["handle"] = None
    if not KEEP_OPEN:
        unreal.SystemLibrary.quit_editor()


def _set_view(loc, rot):
    rotator = unreal.Rotator(roll=float(rot[2]), pitch=float(rot[0]), yaw=float(rot[1]))
    location = unreal.Vector(float(loc[0]), float(loc[1]), float(loc[2]))
    cam = _state["camera"]
    if cam is not None:
        cam.set_actor_location_and_rotation(location, rotator, False, True)
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        ues.set_level_viewport_camera_info(location, rotator)
    except Exception as exc:  # noqa: BLE001
        _log("ビューポートカメラの移動に失敗: %s" % exc)


def _take_shot(name):
    filename = "Loft_%s.png" % name
    cam = _state["camera"]
    try:
        unreal.AutomationLibrary.take_high_res_screenshot(WIDTH, HEIGHT, filename, camera=cam,
                                                          force_game_view=True)
    except TypeError:
        unreal.AutomationLibrary.take_high_res_screenshot(WIDTH, HEIGHT, filename, cam)
    _log("撮影: %s (%dx%d)" % (filename, WIDTH, HEIGHT))


def _load():
    if not unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        _finish("レベル %s がありません。先に Tools\\ue.cmd build を実行してください" % MAP_PATH)
        return False
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.load_level(MAP_PATH):
        _finish("レベルを開けませんでした")
        return False
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cam = eas.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(0, 0, 150),
                                     unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if cam is not None:
        cam.set_actor_label("ShotCamera")
        try:
            comp = cam.get_cine_camera_component()
            comp.set_editor_property("current_focal_length", 24.0)
            comp.set_editor_property("current_aperture", 4.0)
        except Exception as exc:  # noqa: BLE001
            _log("カメラ設定: %s" % exc)
    _state["camera"] = cam
    _set_view(VIEWS[0][1], VIEWS[0][2])
    _log("レベルを開きました。シェーダー待ち %.0f 秒" % WARMUP_SEC)
    return True


def _tick(delta_seconds):
    try:
        now = time.time()
        elapsed = now - _state["t0"]
        phase = _state["phase"]
        if phase == "load":
            _state["phase"] = "warmup"
            _state["t0"] = now
            if not _load():
                _state["phase"] = "done"
        elif phase == "warmup":
            if elapsed >= WARMUP_SEC:
                _state["phase"] = "settle"
                _state["t0"] = now
        elif phase == "settle":
            if elapsed >= SETTLE_SEC:
                _take_shot(VIEWS[_state["index"]][0])
                _state["phase"] = "wait"
                _state["t0"] = now
        elif phase == "wait":
            if elapsed >= AFTER_SHOT_SEC:
                _state["index"] += 1
                if _state["index"] >= len(VIEWS):
                    _state["phase"] = "done"
                    _finish("%d 枚撮影しました → Saved/Screenshots/WindowsEditor/" % len(VIEWS))
                    return
                name, loc, rot = VIEWS[_state["index"]]
                _set_view(loc, rot)
                _state["phase"] = "settle"
                _state["t0"] = now
    except Exception:  # noqa: BLE001
        _state["phase"] = "done"
        _finish("エラー:\n" + traceback.format_exc())


def start():
    if _state["handle"] is not None:
        _log("すでに実行中です")
        return
    _state.update({"phase": "load", "t0": time.time(), "index": 0})
    _state["handle"] = unreal.register_slate_post_tick_callback(_tick)
    _log("撮影を開始します（%d 視点）" % len(VIEWS))


start()
