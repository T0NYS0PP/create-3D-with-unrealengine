# 最初の 3D 空間をつくる

目標: 床・壁・ライトのある部屋をつくり、その中を一人称で歩けるようにする。所要時間は 30 分くらい。

## 0. エディタの基本操作

| 操作 | キー |
| --- | --- |
| 視点を回す | 右クリック + ドラッグ |
| 前後左右に移動 | 右クリックしながら `W A S D` |
| 上下に移動 | 右クリックしながら `E` / `Q` |
| 選んだものにフォーカス | `F` |
| 移動 / 回転 / 拡大縮小ツール | `W` / `E` / `R` |
| プレイ開始 / 停止 | `Alt + P` / `Esc` |
| 全て保存 | `Ctrl + Shift + S` |

## 1. 自分のレベルを作る

1. メニュー **File > New Level** を選び、**Basic** を選択。
2. **File > Save Current Level As** で `Content/Maps/MyLevel` として保存（`Maps` フォルダは新規作成）。
3. **Edit > Project Settings > Maps & Modes** を開き、
   **Editor Startup Map** と **Game Default Map** を `MyLevel` に変更する。
   次回からこのレベルで起動する。

## 2. 床と壁を置く（Modeling Mode）

1. 画面左上のモード選択で **Modeling** を選ぶ（`Shift + 5`）。
2. **Create > Box** を選び、ビューポートでドラッグして床をつくる。
   右のパネルで Width `2000`、Depth `2000`、Height `20` にして **Accept**。
3. 同じ要領で壁を 4 枚つくる。Width `2000`、Depth `20`、Height `400` で、
   **移動ツール (`W`)** で床の四辺に並べる。
   - コピーしたいときは `Alt` を押しながらドラッグ。
   - 位置を揃えたいときは右上のグリッドスナップを ON にする（デフォルト 10cm）。
4. 気に入らなければ Modeling Mode の **Deform / PolyEdit** で形を直せる。

Modeling Mode を使わない場合は、**Place Actors** パネル（`Ctrl + Shift + 1`）> **Shapes > Cube** を
ドラッグして置き、詳細パネルの **Scale** で引き伸ばしても同じことができる。

## 3. ライトを置く

Basic レベルには最初から次が入っている。

- **Directional Light**（太陽）
- **Sky Light**（空からの環境光）
- **Sky Atmosphere**（空の色）
- **Exponential Height Fog**（霧）

部屋の中が暗いときは **Place Actors > Lights > Point Light** を天井あたりに置き、
詳細パネルで **Intensity** を `5000` 前後に上げる。
ライトは **Mobility = Movable** のままで OK（Lumen が動的に計算する）。

## 4. マテリアルで色をつける

1. **Content Browser**（`Ctrl + Space`）で `Content/Materials` フォルダを作る。
2. 右クリック > **Material** で `M_Floor` を作成して開く。
3. 左のパレットから **Constant3Vector** を出し（`3` キーを押しながらクリック）、
   **Base Color** につなぐ。ダブルクリックで色を選ぶ。
4. **Save** して、Content Browser からビューポートの床にドラッグ＆ドロップ。

手早く済ませたいときは、**Window > Quixel Bridge**（または Fab）から無料のマテリアルを
ダウンロードしてドラッグするだけでもよい。

## 5. 歩けるようにする

1. **Place Actors > Basic > Player Start** を部屋の中に置く。床から少し浮かせる。
2. **Edit > Project Settings > Maps & Modes > Default GameMode** を
   **ThirdPersonGameMode** などにしたい場合は、まず
   **Content Browser > Add > Add Feature or Content Pack > First Person** を追加する。
3. 追加後、**Default GameMode** に `BP_FirstPersonGameMode` を指定する。
4. `Alt + P` でプレイ。`WASD` で歩き、マウスで見回せたら完成。

Feature Pack を入れずに「とりあえず飛び回りたい」だけなら、
Default GameMode を変えずに `Alt + P` を押せば、ビューポートと同じ操作で飛び回れる。

## 6. 保存してコミット

```
Ctrl + Shift + S
git add .
git commit -m "Add MyLevel with floor, walls, and lights"
git push
```

## つまずきやすいところ

- **真っ暗になる**: Sky Light / Directional Light が消えていないか、Point Light の Intensity が小さすぎないか確認。
- **壁をすり抜ける**: Modeling Mode で作ったメッシュは自動でコリジョンがつく。
  自作メッシュを読み込んだ場合は、メッシュを開いて **Collision > Add Box Simplified Collision**。
- **エディタが重い**: **Settings > Engine Scalability Settings** を `Medium` に下げる。
- **レベルを保存し忘れる**: タブ名に `*` がついていたら未保存。
