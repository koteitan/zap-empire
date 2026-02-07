# tmux キー設定メモ

## 問題

WezTerm が `Ctrl+B` を横取りするため、tmux のデフォルト prefix が使えない。

## 解決: prefix を Ctrl+A に変更

`~/.tmux.conf` に追加:

```
set -g prefix C-a
unbind C-b
bind C-a send-prefix
```

## 起動中の tmux セッションに反映する方法

tmux 内のペインで直接実行:

```bash
tmux source-file ~/.tmux.conf
```

Claude Agent Team の tmux セッションが動いていて Ctrl+C できない場合は、**別のターミナルタブ**から:

```bash
# セッション名を確認
tmux -L claude-swarm-XXXXX list-sessions

# 別ターミナルから設定を反映
tmux -L claude-swarm-XXXXX source-file ~/.tmux.conf
```

## 基本操作 (prefix = Ctrl+A)

| 操作 | キー |
|---|---|
| ペイン切り替え | `Ctrl+A` + 矢印キー |
| ペインをズーム/戻す | `Ctrl+A` + `z` |
| ペイン一覧 | `Ctrl+A` + `q` |
| デタッチ | `Ctrl+A` + `d` または `tmux detach` |
| コマンドモード | `Ctrl+A` + `:` |

## 注意

- Claude Agent Team は独自の tmux ソケット (`claude-swarm-<PID>`) を使う
- デタッチすると全チームメイトの tmux セッションが切れる可能性あり
- エージェント作業中はデタッチせず、別ターミナルから操作するのが安全
