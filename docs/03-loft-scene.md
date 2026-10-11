# 自動生成シーン「夕方のロフト」(L_Loft)

`Tools > My3DSpace > Build Loft Scene` を 1 回実行すると、次の空間が生成されます。

- 8m × 6m × 天井高 3.2m のロフト風リビング。+X 側が幅 5m の大窓で、外にテラスと街並み。
- 床はオークのフローリング、壁は白い漆喰、天井はコンクリート、梁はダークウッド。
- ソファ・コーヒーテーブル・ラグ・サイドボード・アート・フロアランプ・観葉植物。
- ダイニングテーブルと椅子 4 脚、ペンダントライト 3 灯。
- 奥の壁に本棚（本 60 冊前後をランダム配置）、右の壁にキッチン（吊り戸棚下の間接照明つき）。
- 低い夕日（仰角 11°）が窓から差し込み、方立の影が床と奥の壁に伸びる。
- Lumen GI / Lumen 反射、仮想シャドウマップ、ボリュメトリックフォグ、Sky Atmosphere、Volumetric Cloud。
- 自動露出・ブルーム・ビネット・フィルムグレインを設定したポストプロセスボリューム。

アクター数は約 310 個。すべてエンジン付属の基本形状（Cube / Cylinder / Sphere）なので、
外部アセットのダウンロードは不要です。

## 実行手順

1. `My3DSpace.uproject` を開く（Python プラグインは有効化済み）。
2. メニュー **Tools > My3DSpace > Build Loft Scene** を選ぶ。
   - メニューが無い場合は、**Output Log** の入力欄左のドロップダウンを **Python** にして
     ```
     import build_loft; build_loft.main()
     ```
   - または入力欄を **Cmd** のまま `py build_loft.py`。
3. 進捗ダイアログが閉じたら完成。ビューポートはソファ越しに窓を見る位置に移動します。
4. `Alt + P` でプレイ。マウスで見回し、`WASD` で飛び回れます。
   `Esc` で戻り、`Ctrl + Shift + S` で保存。

初回はシェーダーコンパイルで 1 〜 3 分ほど待ちます。生成物は `Content/Loft/` 以下です。

## 仕組み

| ファイル | 役割 |
| --- | --- |
| `Content/Python/build_loft.py` | シーン生成本体。テクスチャ取込 → マテリアル作成 → レベル作成 → 配置 → ライト → 保存 |
| `Content/Python/init_unreal.py` | 起動時に Tools メニューへ項目を追加 |
| `RawAssets/Textures/*.png` | 木・コンクリート・漆喰・布の PBR テクスチャ（RGB = 色, A = ラフネス / ノーマル） |
| `Tools/gen_textures.py` | 上記テクスチャを numpy で生成した開発用スクリプト（再実行は不要） |

マテリアル `M_Triplanar` はワールド座標で三面投影するので、Cube をどんな大きさに伸ばしても
テクスチャが引き伸ばされません。パラメータは `TileSize`（cm）、`Tint`、`RoughnessScale`、
`RoughnessBias`、`NormalStrength`、`Metallic`。インスタンス（`MI_WoodFloor` など）を
ダブルクリックすれば、色や光沢をスライダーで調整できます。

## 調整のヒント

| やりたいこと | 場所 |
| --- | --- |
| 太陽の高さ・向きを変える | アウトライナの `Sun` を選び、回転 Y（Pitch）が高さ、Z（Yaw）が向き |
| 全体を明るく / 暗く | `PostProcess_Global` > Exposure > Exposure Compensation |
| 光の筋（ゴッドレイ）を強く | `HeightFog` > Volumetric Fog > Extinction Scale、`Sun` > Volumetric Scattering Intensity |
| 床の色を変える | `Content/Loft/Materials/MI_WoodFloor` > Tint |
| 重い | `Settings > Engine Scalability Settings` を Medium。`VolumetricCloud` を消すのも効く |

## 次にやるとリアルになること

1. **Fab / Quixel Megascans の無料アセット**に置き換える（ソファ、椅子、植物、小物）。
   `Window > Fab` で検索し、ドラッグして置くだけ。
2. 窓の外に **Landscape** を追加して街の代わりに公園や海にする。
3. `Camera_Hero` を選択して右クリック > **Pilot** にすると、カメラ視点で構図を調整できる。
   Sequencer で動かせば動画も書き出せる。
4. 壁や家具の角を **Modeling Mode > Bevel** で面取りすると、ハイライトが乗って一段リアルになる。

## うまくいかないとき

- **Tools に My3DSpace が無い**: `Edit > Plugins` で *Python Editor Script Plugin* と
  *Editor Scripting Utilities* が有効か確認して再起動。
- **テクスチャが見つからない警告**: `RawAssets/Textures/` が `.uproject` と同じ階層にあるか確認。
- **壁が真っ黒 / 市松模様**: マテリアルのコンパイル待ち。数十秒待つか、Output Log の
  `[Loft]` 警告を確認。三面投影が作れなかった場合は単色マテリアルに自動で切り替わる。
- **部屋が暗すぎる**: `PostProcess_Global` の Min EV100 を 2 程度まで下げる。
- **再生成したい**: もう一度 Build Loft Scene を実行（`Content/Loft` は作り直されるので、
  手で加えた変更は別フォルダに保存しておく）。
