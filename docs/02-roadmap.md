# その先のステップ

`01-first-3d-space.md` で部屋ができたら、次は興味に合わせて進む。

## A. 広い屋外をつくりたい

1. **Landscape Mode**（`Shift + 2`）で地形を作成。Sculpt で山や谷をつくる。
2. **Foliage Mode**（`Shift + 3`）で草や木をばらまく。
3. **Fab / Quixel Megascans** から岩・木・地面マテリアルを取り込む。
4. **Open World** テンプレートで新規レベルを作ると、最初から広い地形がある。

## B. 建物や部屋を作り込みたい

1. **Modeling Mode** の PolyEdit / Boolean でドアや窓をくり抜く。
2. **Blender** で作ったメッシュを FBX / glTF で読み込む（`Content/Meshes` に入れる）。
3. **Nanite** を有効にすると高ポリゴンでも軽く動く（インポート時に **Build Nanite** にチェック）。

## C. 動くものを置きたい（Blueprint）

1. **Content Browser > Add > Blueprint Class > Actor** で `BP_Door` を作成。
2. Static Mesh を追加し、**Event Graph** で `Event BeginPlay` → `Timeline` → `Set Relative Rotation`。
3. **Box Collision** を追加して `On Component Begin Overlap` で開くようにする。

## D. 見た目を良くしたい

1. **Post Process Volume** を置き、**Infinite Extent** を ON にして露出・色味を調整。
2. **Lumen** は `Config/DefaultEngine.ini` で有効化済み。鏡面が欲しければ **Reflection Method = Lumen** のまま、
   マテリアルの **Roughness** を下げる。
3. **Sequencer**（Window > Cinematics > Sequencer）でカメラを動かして動画を書き出す。

## E. 他の人に見せたい

1. **Platforms > Windows > Package Project** で実行ファイルを書き出す。
2. Blueprint のみのプロジェクトなら Visual Studio は不要。C++ を使い始めたら
   Visual Studio 2022 の「C++ によるゲーム開発」ワークロードが必要になる。

## 参考リンク

- 公式ドキュメント（日本語）: https://dev.epicgames.com/documentation/ja-jp/unreal-engine
- 公式チュートリアル: https://dev.epicgames.com/community/unreal-engine/learning
- Fab（無料アセット）: https://www.fab.com/
