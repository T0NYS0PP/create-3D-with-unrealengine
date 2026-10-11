# この PC の Unreal Engine を Claude に操作させる

クラウド上の Claude Code セッションは、あなたの PC には触れません。
Claude にエディタを起動させたり、シーンを生成・撮影させたりするには、
**Claude Code をこの PC 上で動かす**必要があります。やり方は 2 つです。

## A. Claude デスクトップアプリ（かんたん）

1. Claude デスクトップアプリを開き、**Code** タブでこのリポジトリのフォルダを開く。
2. チャットで「`Tools\ue.cmd build` を実行して」のように頼む。
   Claude がこの PC でコマンドを実行し、結果（ログや画像）を読み取れる。

## B. ターミナルから remote-control

1. このリポジトリのフォルダでターミナルを開き、次を実行する。
   ```
   claude remote-control
   ```
2. Claude Code アプリ（ブラウザ / スマホ）にこのセッションが表示されるので、
   そこから指示する。コマンドは PC 側で実行される。

どちらの場合も、初回は Claude が実行するコマンドの許可を求めてくるので「許可」を選ぶ。

## Claude が使うコマンド

`Tools\ue.cmd` が UE のインストール先を自動で探して `UnrealEditor.exe` を起動します。

| コマンド | 内容 |
| --- | --- |
| `Tools\ue.cmd find` | 見つかった UnrealEditor.exe のパスを表示 |
| `Tools\ue.cmd open` | エディタでプロジェクトを開く |
| `Tools\ue.cmd build` | エディタを起動 → `build_loft.py` でシーン生成 → 終了（数分） |
| `Tools\ue.cmd shots` | L_Loft を 6 視点で撮影して `Saved\Screenshots\Loft\*.png` に保存 → 終了 |
| `Tools\ue.cmd run path\to\script.py` | 任意の UE Python スクリプトを実行 |
| `Tools\ue.cmd log` | ログから `[Loft]` とエラー行だけ抜き出す |

UE が見つからない場合は、環境変数 `UE_ROOT` にインストール先を入れてください。

```
setx UE_ROOT "C:\Program Files\Epic Games\UE_5.6"
```

## 典型的な流れ

1. `Tools\ue.cmd build` でシーンを生成する。
2. `Tools\ue.cmd shots` で撮影し、Claude が画像を見て配置やライティングを直す。
3. `Content/Python/build_loft.py` を修正 → 1 に戻る。
4. 仕上げは `Tools\ue.cmd open` で自分の目で確認する。

撮影の視点は `Content/Python/render_shots.py` の `VIEWS` で変えられます。
