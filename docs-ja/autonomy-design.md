# Zap Empire: 自律フレームワーク設計

## 1. 概要

本ドキュメントでは、Zap Empire の agent プロセスがローカルの WSL2 環境上でどのように起動・監視・管理・復旧されるかを規定する。本システムは **10 個の user agent**（`user0`〜`user9`）と、インフラを管理する複数の **system agent** をサポートする。

### 1.1 Agent 一覧

| Agent 種別 | インスタンス数 | 役割 |
|---|---|---|
| `system-master` | 1 | 最上位の supervisor。他のすべての agent を起動し監視する |
| `nostr-relay` | 1 | ローカル Nostr relay サーバー |
| `cashu-mint` | 1 | ecash の発行と償還を行う Cashu mint |
| `user0`〜`user9` | 10 | プログラムの作成・取引・トランザクションを行う user agent |

合計: 管理対象 **13 プロセス**。

---

## 2. プロセス管理

### 2.1 技術選定: カスタムプロセスマネージャー

systemd（root 権限が必要で WSL2 のセットアップを複雑にする）や `supervisord` のようなサードパーティの supervisor を使う代わりに、Zap Empire ではプロジェクトの主要言語で書かれた**カスタム軽量プロセスマネージャー**を使用する。これにより、外部依存なしにライフサイクル、heartbeat のセマンティクス、agent 間メッセージングを完全に制御できる。

プロセスマネージャーは `system-master` に組み込まれている。

### 2.2 プロセスの起動

`system-master` が唯一のエントリーポイントである。起動時に以下を行う:

1. 実行すべきすべての agent を列挙した宣言的な agent マニフェスト（`config/agents.json`）を読み込む。
2. 各 agent を OS レベルのプロセス生成（`subprocess.Popen`）により**子プロセス**として起動する。
3. 各 agent の **PID**、**起動タイムスタンプ**、**割り当て ID**（例: `user3`）を記録する。
4. 各子プロセスの `stdout`/`stderr` を `logs/<agent-id>/` 配下の agent ごとのローテーションログファイルにパイプする。

#### Agent マニフェストの例

```json
{
  "relay_url": "ws://127.0.0.1:7777",
  "mint_url": "http://127.0.0.1:3338",
  "agents": [
    { "id": "nostr-relay",  "cmd": "./strfry", "args": ["relay"],                          "restart": "always" },
    { "id": "cashu-mint",   "cmd": "python",   "args": ["-m", "cashu.mint"],               "restart": "always" },
    { "id": "user0",        "cmd": "python",   "args": ["src/user/main.py", "0"],          "restart": "on-failure" },
    { "id": "user1",        "cmd": "python",   "args": ["src/user/main.py", "1"],          "restart": "on-failure" }
  ]
}
```

### 2.3 起動順序と依存関係

agent は**依存順序**に従って起動される:

1. **フェーズ 1 -- インフラ**: `nostr-relay`、`cashu-mint`
2. **フェーズ 2 -- ユーザー**: `user0` から `user9`（フェーズ 1 の agent が正常な heartbeat を報告した後に並列起動可能）

`system-master` はフェーズ 2 に進む前に、フェーズ 1 の agent が最初の成功した heartbeat を発信するのを待つ。

---

## 3. Heartbeat メカニズム

### 3.1 設計

管理対象のすべての agent は、定期的に `system-master` へ **heartbeat メッセージ**を送信する。heartbeat はプロジェクト独自の Nostr relay をトランスポート層として使用し、agent 間通信と一貫した設計を保つ。

| パラメータ | 値 |
|---|---|
| heartbeat 間隔 | **5 秒** |
| heartbeat タイムアウト（dead 判定閾値） | **15 秒**（3 回分の未着） |
| heartbeat Nostr event kind | `4300`（regular event） |
| heartbeat tags | `["agent_name", "<id>"]`、`["role", "<role>"]` |

### 3.2 Heartbeat ペイロード

各 heartbeat はローカル relay に publish される Nostr event である:

```json
{
  "kind": 4300,
  "tags": [
    ["agent_name", "user3"],
    ["role", "user-agent"]
  ],
  "content": "{\"status\":\"healthy\",\"uptime_secs\":3621,\"mem_mb\":42,\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0,\"ts\":1700000000}"
}
```

`content` 内のフィールド:

| フィールド | 型 | 説明 |
|---|---|---|
| `status` | string | `healthy`、`degraded`、または `shutting-down` |
| `uptime_secs` | int | agent 起動からの経過秒数 |
| `mem_mb` | int | 常駐メモリ（MB） |
| `balance_sats` | int | 現在の Cashu wallet 残高（sats） |
| `programs_owned` | int | agent が保有するプログラム数 |
| `programs_listed` | int | 売りに出されているプログラム数 |
| `active_trades` | int | 進行中の取引交渉の数 |
| `ts` | int | heartbeat の Unix タイムスタンプ |

### 3.3 フォールバック: パイプベースの Heartbeat

Nostr relay 自体が監視対象の agent である場合（鶏と卵の問題）、`system-master` は**セカンダリチャネル**を通じて `nostr-relay` を監視する:

- `nostr-relay` は 5 秒ごとに `stdout` に heartbeat 行を書き込む。
- `system-master` は子プロセスのパイプを直接読み取る。
- 形式: `HEARTBEAT <unix_timestamp> <status>`

これにより、relay が利用不可能な場合でも（あるいは利用可能になる前でも）`nostr-relay` の健全性が追跡される。

---

## 4. ヘルスモニタリング

### 4.1 Agent の状態

`system-master` は各 agent に対してステートマシンを維持する:

```
         spawn
  [STOPPED] ──────> [STARTING]
      ^                  │
      │           first heartbeat
      │                  v
      │             [RUNNING]
      │            /         \
      │    heartbeat          timeout / crash
      │    received            detected
      │        │                  │
      │        v                  v
      │    [RUNNING]         [UNHEALTHY]
      │                          │
      │                   restart policy
      │                   applied
      │                  /          \
      │          restart=yes     restart=no
      │              │                │
      │              v                v
      └──────── [STARTING]      [STOPPED]
```

状態:

| 状態 | 説明 |
|---|---|
| `STOPPED` | 実行中でない。PID なし |
| `STARTING` | プロセスは起動済み。最初の heartbeat を待機中 |
| `RUNNING` | 正常。heartbeat が時間通りに到着している |
| `UNHEALTHY` | タイムアウト閾値を超えて heartbeat が未着 |

### 4.2 ヘルスチェックループ

`system-master` は **5 秒**ごとにヘルスチェックループを実行する:

1. 各 agent について `time_since_last_heartbeat` を計算する。
2. `>= 15s` かつ状態が `RUNNING` の場合、`UNHEALTHY` に遷移する。
3. `UNHEALTHY` の場合、その agent のリスタートポリシーを適用する（セクション 5 参照）。
4. `STARTING` 状態の agent に heartbeat が到着した場合、`RUNNING` に遷移する。
5. すべての状態遷移を `logs/system-master/state.log` に記録する。

### 4.3 システムダッシュボード（オプション、フェーズ 2）

agent の状態テーブルを表示するシンプルなステータスエンドポイントまたは CLI コマンド:

```
Agent         State      Last Beat   Uptime    Restarts
───────────── ────────── ─────────── ───────── ────────
nostr-relay   RUNNING    2s ago      1h 23m    0
cashu-mint    RUNNING    1s ago      1h 23m    0
user0         RUNNING    3s ago      1h 22m    1
user1         UNHEALTHY  18s ago     0h 04m    3
...
user9         RUNNING    0s ago      1h 22m    0
```

---

## 5. Agent ライフサイクル

### 5.1 起動

1. `system-master` が agent マニフェストを読み込む。
2. agent プロセスを起動し、状態を `STARTING` にする。
3. **30 秒**の**起動タイムアウト**を開始する。
4. タイムアウト内に agent が最初の heartbeat を送信すれば、状態は `RUNNING` になる。
5. heartbeat なくタイムアウトが満了した場合、状態は `UNHEALTHY` になり、リスタートポリシーが適用される。

### 5.2 グレースフル停止

1. `system-master` が agent プロセスに `SIGTERM` を送信する。
2. agent はシグナルを受信し、`status: "shutting-down"` の最終 heartbeat を publish し、クリーンアップを実行してから終了コード 0 で終了する。
3. `system-master` はプロセスの終了を最大 **10 秒**待つ。
4. プロセスが終了しない場合、`system-master` は `SIGKILL` を送信する。
5. 状態が `STOPPED` になる。

### 5.3 クラッシュ検出

クラッシュは以下の場合に検出される:
- 子プロセスが予期せず終了した場合（終了コード != 0、またはシグナルによる kill）。
- `system-master` が子プロセスハンドルの `exit` イベントを受信した場合。

クラッシュ時:
1. 状態が `UNHEALTHY` に遷移する。
2. 終了コード/シグナル、タイムスタンプ、agent の stderr の最後 50 行がログに記録される。
3. リスタートポリシーが直ちに適用される。

### 5.4 リスタートポリシー

各 agent はマニフェスト内に `restart` フィールドを持つ:

| ポリシー | 動作 |
|---|---|
| `always` | 終了コードに関係なく常にリスタートする。インフラ agent に使用。 |
| `on-failure` | 終了コードが != 0 の場合のみリスタートする。user agent に使用。 |
| `never` | リスタートしない。ワンショットタスクに使用。 |

### 5.5 リスタートのバックオフ

急速なリスタートループ（クラッシュ→リスタート→クラッシュ）を防ぐため、リスタートには**ジッター付き指数バックオフ**が使用される:

| リスタート # | 遅延 |
|---|---|
| 1 | 1 秒 |
| 2 | 2 秒 |
| 3 | 4 秒 |
| 4 | 8 秒 |
| 5+ | 16 秒（上限） |

さらに 0〜500ms のランダムジッターが加算される。

agent が連続 **60 秒**以上 `RUNNING` 状態を維持した場合、バックオフカウンターは **0 にリセット**される。

### 5.6 最大リスタート回数制限

agent が **5 分以内に 10 回**リスタートした場合、`STOPPED` 状態に置かれ `restart-exhausted` とフラグ付けされる。`system-master` はクリティカルエラーをログに記録する。リスタートには手動介入（またはオペレーターからのコマンド）が必要となる。

---

## 6. Agent 間の監視

### 6.1 監視ツリー

```
system-master (root supervisor)
├── nostr-relay          [restart: always]
├── cashu-mint           [restart: always]
├── user0                [restart: on-failure]
├── user1                [restart: on-failure]
├── ...
└── user9                [restart: on-failure]
```

`system-master` が**唯一の supervisor** である。初期設計ではネストされた監視はない -- agent 数（13）は十分に少なく、フラットなツリーが十分であり、理解しやすい。

### 6.2 依存関係を考慮したリスタート

インフラ agent（`nostr-relay` または `cashu-mint`）がクラッシュしてリスタートする場合:

1. `system-master` はすべての依存 agent（user agent）を **`WAITING`** サブ状態に遷移させる。
2. user agent には `SIGUSR1` が送信され、外部操作の一時停止とメッセージのバッファリングが通知される。
3. インフラ agent が `RUNNING` に復帰すると、`system-master` は user agent に `SIGUSR2` を送信して再開を指示する。

これにより、relay や mint の短時間の停止時に user agent が一斉に障害を起こすことを防ぐ。

### 6.3 カスケード停止

`system-master` 自体が停止される場合（`SIGTERM` または `SIGINT` を受信）:

1. まず user agent を停止する（フェーズ 2 の逆順）: `user9`〜`user0` に `SIGTERM` を送信し、終了を待つ。
2. 次にインフラ agent を停止する（フェーズ 1 の逆順）: `cashu-mint`、次に `nostr-relay` に `SIGTERM` を送信する。
3. 正常終了する。

これにより、mint/relay が停止する前に user agent が進行中のトランザクションを完了できる。

---

## 7. クラッシュ復旧とデータ整合性

### 7.1 Agent 状態の永続化

各 agent は定期的に自身の状態をディスクに永続化する:

- **場所**: `data/agents/<agent-id>/state.json`
- **頻度**: 30 秒ごと、およびグレースフルシャットダウン時。
- **内容**: agent 固有（例: user agent の wallet 残高、保留中のトランザクション）。

リスタート時、agent は `state.json` を読み込んで最後のチェックポイントから再開する。

### 7.2 system-master のクラッシュ復旧

`system-master` 自体がクラッシュした場合（例: OOM による kill やオペレーターのミス）:

1. リスタート時、`system-master` は起動したすべての子プロセスの PID を記録した `data/system-master/pids.json` を読み込む。
2. 記録された各 PID について、プロセスがまだ生存しているか確認する（`kill -0 <pid>`）。
3. 生存している場合、監視を再接続する（heartbeat の再購読、relay の stdout パイプの再接続）。
4. 停止している場合、リスタートポリシーを適用する。

これにより、`system-master` はすべての agent をリスタートせずに復旧できる。

### 7.3 孤児プロセスのクリーンアップ

起動時に `system-master` は、想定されるコマンドパターンに一致するプロセスを確認することで、孤児プロセス（supervisor なしで実行中の agent）もスキャンする。孤児は設定に応じて養子として管理されるか、kill される。

---

## 8. スケーラビリティに関する考慮事項

### 8.1 現在の規模

- 10 user agent + 3 system プロセス = 合計 13 プロセス。
- heartbeat トラフィック: 5 秒ごとに 13 イベント = ローカル relay 上で約 2.6 イベント/秒。
- これはどの Nostr relay 実装でも容易に処理できる。

### 8.2 10 ユーザー超へのスケーリング

10 を超える user agent が必要な場合:

- agent マニフェストは任意のエントリーをサポートしている。`user10`〜`user99` の追加は設定変更のみで可能。
- relay 負荷が懸念される場合、heartbeat 間隔を 10 秒や 15 秒に延長できる。
- user agent を**監視グループ**（例: `user0-9`、`user10-19`）にまとめ、グループごとにサブ supervisor を配置して 2 階層のツリーを構成できる。

### 8.3 リソース制限

各 agent プロセスは、1 つの暴走 agent が他を枯渇させるのを防ぐために制約されるべきである:

| リソース | 制限値 | メカニズム |
|---|---|---|
| メモリ | user agent あたり 256 MB | `resource.setrlimit()`（Python）または cgroup |
| CPU | ハードリミットなし（WSL2 はホスト CPU を共有） | heartbeat の `cpu_pct` フィールドで監視 |
| ファイルディスクリプタ | agent あたり 1024 | `ulimit -n` |
| ディスク（ログ） | agent あたり 50 MB | ログローテーション（5 ファイル x 10 MB を保持） |

### 8.4 WSL2 固有の注意事項

- **デフォルトで systemd なし**: WSL2 ディストリビューションでは systemd が有効とは限らない。カスタムプロセスマネージャーはこの依存を完全に回避する。
- **ファイルシステムのパフォーマンス**: agent の状態ファイルは Linux ファイルシステム（`/home/...`）に書き込まれ、`/mnt/c/` には書き込まれない。NTFS 変換のオーバーヘッドを避けるためである。
- **ネットワーキング**: Nostr relay は `127.0.0.1`（localhost）にバインドする。すべての agent は `ws://127.0.0.1:7777` 経由で接続する。Cashu mint は `http://127.0.0.1:3338` で利用可能。Windows ファイアウォールの設定は不要。
- **プロセスシグナル**: `SIGTERM`、`SIGKILL`、`SIGUSR1`、`SIGUSR2` はすべて WSL2 上で正しく動作する。

---

## 9. ロギングとオブザーバビリティ

### 9.1 ログ構造

```
logs/
├── system-master/
│   ├── state.log        # すべての agent の状態遷移
│   └── master.log       # system-master 自身の運用ログ
├── nostr-relay/
│   ├── stdout.log
│   └── stderr.log
├── cashu-mint/
│   ├── stdout.log
│   └── stderr.log
├── user0/
│   ├── stdout.log
│   └── stderr.log
...
```

### 9.2 ログローテーション

- 各ログファイルは **10 MB** でローテーションされる。
- agent ごとに最後の **5 つのローテーションファイル**が保持される。
- ローテーションは `system-master`（または組み込みのシンプルなローテーター）が処理し、外部ツールは使用しない。

### 9.3 構造化ロギング

すべての agent は JSON 形式のログ行を出力する:

```json
{"ts":"2025-01-15T12:00:00Z","level":"info","agent":"user3","msg":"Published program listing","event_id":"abc123"}
```

これにより、専門的なツールなしに `grep`/`jq` ベースでの分析が可能となる。

---

## 10. 制御インターフェース

### 10.1 CLI コマンド

`system-master` は `data/system-master/control.sock` の Unix ドメインソケット経由で制御インターフェースを公開する。オペレーター用 CLI ツール（`zapctl`）がコマンドを送信する:

| コマンド | 説明 |
|---|---|
| `zapctl status` | agent ステータステーブルを表示（セクション 4.3） |
| `zapctl stop <agent-id>` | agent をグレースフルに停止 |
| `zapctl start <agent-id>` | 停止中の agent を起動 |
| `zapctl restart <agent-id>` | グレースフルリスタート |
| `zapctl logs <agent-id>` | agent のログを tail |
| `zapctl shutdown` | システム全体のグレースフルシャットダウン |

### 10.2 Nostr ベースの制御（将来）

後のフェーズでは、`system-master` が Nostr event（kind `30079`）として制御コマンドを受け付け、relay を通じたリモート管理を可能にすることができる。これは初期実装のスコープ外である。

---

## 11. 主要な設計判断のまとめ

| 判断 | 根拠 |
|---|---|
| systemd ではなくカスタムプロセスマネージャー | root 権限の要件を回避。すべての WSL2 環境で動作。Nostr とのより緊密な統合 |
| Nostr ベースの heartbeat | 既存インフラの再利用。heartbeat は任意の relay 購読者が観測可能 |
| relay 監視のパイプフォールバック | relay を relay 経由で監視するという鶏と卵の問題を解決 |
| フラットな監視ツリー | 13 agent は少数。早すぎる抽象化よりもシンプルさを優先 |
| リスタート時の指数バックオフ | クラッシュループによるリソース消費を防止 |
| 復旧用の JSON 状態ファイル | シンプルで人間が読め、データベース依存なし |
| 制御用の Unix ドメインソケット | セキュア（ファイルシステム権限）、低オーバーヘッド、ネットワーク露出なし |
