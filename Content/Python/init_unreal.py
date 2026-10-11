# -*- coding: utf-8 -*-
"""
init_unreal.py
エディタ起動時に自動実行され、Tools メニューに「Build Loft Scene」を追加します。
（Content/Python/ 直下の init_unreal.py は Python プラグインが自動で読み込みます）
"""
import importlib
import traceback

import unreal

MENU_PATH = "LevelEditor.MainMenu.Tools"
SECTION = "My3DSpace"
_ENTRIES = []  # GC で消えないよう保持


@unreal.uclass()
class BuildLoftMenuEntry(unreal.ToolMenuEntryScript):
    @unreal.ufunction(override=True)
    def execute(self, context):
        try:
            import build_loft
            importlib.reload(build_loft)
            build_loft.main()
        except Exception:  # noqa: BLE001
            unreal.log_error("[My3DSpace] Build Loft Scene failed:\n" + traceback.format_exc())


def register_menu():
    menus = unreal.ToolMenus.get()
    tools_menu = menus.find_menu(MENU_PATH)
    if tools_menu is None:
        unreal.log_warning("[My3DSpace] Tools メニューが見つからないため、メニュー登録を省略しました")
        return
    tools_menu.add_section(SECTION, "My3DSpace")
    entry = BuildLoftMenuEntry()
    entry.init_entry(
        "My3DSpace",
        MENU_PATH,
        SECTION,
        "BuildLoftScene",
        "Build Loft Scene",
        "夕方のロフト風リビング (L_Loft) を自動生成します",
    )
    entry.register_menu_entry()
    _ENTRIES.append(entry)
    menus.refresh_all_widgets()
    unreal.log("[My3DSpace] Tools > My3DSpace > Build Loft Scene を登録しました")


try:
    register_menu()
except Exception:  # noqa: BLE001
    unreal.log_warning("[My3DSpace] メニュー登録に失敗しました（アウトプットログで "
                       "import build_loft; build_loft.main() でも実行できます）\n" + traceback.format_exc())
