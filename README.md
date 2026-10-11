# create-3D-with-unrealengine

Unreal Engine 5 で 3D 空間をつくる練習用プロジェクトです。

## 構成

| パス | 内容 |
| --- | --- |
| `My3DSpace.uproject` | プロジェクト本体（ダブルクリックでエディタが開く） |
| `Config/` | プロジェクト設定（起動マップ、レンダリング設定など） |
| `Content/` | レベル・メッシュ・マテリアルなどのアセット置き場 |
| `docs/01-first-3d-space.md` | 最初の 3D 空間をつくる手順 |
| `docs/02-roadmap.md` | その先のステップ |

## はじめかた

1. このリポジトリをクローンする。
2. `My3DSpace.uproject` をダブルクリックする。
   - インストール済みの UE バージョンと `EngineAssociation`（現在 `5.6`）が違う場合、
     「Select Unreal Engine Version」ダイアログが出るので、入っているバージョンを選ぶ。
3. 「Missing Modules」や「Rebuild」の確認が出たら **Yes** を押す（Blueprint のみなので数秒で終わる）。
4. エディタが開いたら、床とライトだけの空のレベルが表示される。ここから `docs/01-first-3d-space.md` の手順に進む。

## Git の扱い

- `Binaries/` `Intermediate/` `Saved/` `DerivedDataCache/` はエディタが自動生成するので、`.gitignore` で除外済み。
- `.uasset` / `.umap` はバイナリ。アセットが増えてきたら Git LFS を使う。
  ```
  git lfs install
  ```
  `.gitattributes` に LFS の設定は入れてあるので、上のコマンドを一度実行すれば有効になる。
- 保存は `Ctrl + Shift + S`（全て保存）してからコミットする。
