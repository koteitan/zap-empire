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

systemd（root 権限が必要で WSL2 のセットアップを複雑にする）や `supervisord` のようなサードパーティの supervisor を使う代わりに、Zap Empire ではプロジェクトの主要言語で書かれた**カスタム軽量プロセスマネージャー**を使用する。これにより、外部依存なしにライフサイクル、自律的なアクティビティループ、agent 間メッセージングを完全に制御できる。

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
2. **フェーズ 2 -- ユーザー**: `user0` から `user9`（フェーズ 1 の agent が正常と報告された後に並列起動可能）

`system-master` はフェーズ 2 に進む前に、フェーズ 1 の agent が準備完了を通知する（relay が WebSocket 接続を受け付け、mint がヘルスエンドポイントに応答する）のを待つ。

---

## 3. 自律アクティビティループ

### 3.1 コンセプト

各 user agent は内部で**アクティビティループ**を実行する。これは自律的な経済行動を駆動する定期的なティックである。agent に保留中のタスク（受信オファー、完了すべき取引など）がない場合、ティックは自律的なアクションを選択して実行する。

これは Zap Empire 経済の「心臓の鼓動」である。ヘルスシグナルではなく、**自律的活動のパルス**である。

### 3.2 ティックの設定

| パラメータ | 値 |
|---|---|
| デフォルトのティック間隔 | **60 秒** |
| 設定可能範囲 | 30〜300 秒 |
| agent ごとのオーバーライド | agent マニフェスト内の `tick_interval` フィールド |
| Nostr ステータスブロードキャスト kind | `4300`（情報提供用、ヘルスチェック用ではない） |
| ステータスブロードキャスト頻度 | 5 ティックごと（約 5 分） |

間隔が意図的に長い（1 分）のは以下の理由による:
- アクションには実際の Nostr event と Cashu トランザクションが伴う
- マーケットプレイスには自然な価格発見のためにアクション間の時間が必要
- システム負荷が低く、ログが読みやすくなる

### 3.3 アクティビティの選択

各ティックで、agent は優先度順の意思決定プロセスを実行する:

| 優先度 | 条件 | アクション |
|---|---|---|
| 1 | 保留中の取引メッセージ（オファー/承諾/支払い） | 取引に応答する |
| 2 | マーケットプレイスに予算内の魅力的なプログラムがある | 閲覧して購入を検討する |
| 3 | インベントリのプログラム数が N 個未満 | 新しいプログラムを生成する |
| 4 | 出品中のプログラムが最近売れていない | 価格を調整する |
| 5 | ポートフォリオレビューの間隔に達した | パフォーマンスを分析し戦略を更新する |
| 6 | 上記のいずれにも該当しない | アイドル（ログ出力、次のティックを待つ） |

具体的な意思決定ロジックとパーソナリティに基づくバリエーションは [User Agent 設計](./user-agent-design.md) で定義されている。

### 3.4 アクティビティループの疑似コード

```python
async def activity_loop(agent):
    while agent.running:
        # 1. Check for and handle pending trade messages
        pending = await agent.nostr.fetch_pending_events()
        if pending:
            await agent.trade_engine.process(pending)
        else:
            # 2. Autonomous action selection
            action = agent.strategy.select_action(agent.state)
            await agent.execute(action)

        # 3. Publish status for dashboard (every N ticks)
        if agent.tick_count % STATUS_BROADCAST_INTERVAL == 0:
            await agent.publish_status()

        agent.tick_count += 1
        await asyncio.sleep(agent.tick_interval)
```

### 3.5 Agent マニフェストの拡張

```json
{
  "agents": [
    { "id": "user0", "cmd": "python", "args": ["src/user/main.py", "0"],
      "restart": "on-failure", "tick_interval": 60 },
    { "id": "user1", "cmd": "python", "args": ["src/user/main.py", "1"],
      "restart": "on-failure", "tick_interval": 45 }
  ]
}
```

agent ごとに異なるティック間隔を設定することで、マーケット活動に自然なばらつきが生まれる。

### 3.6 インフラ Agent

インフラ agent（`nostr-relay`、`cashu-mint`）はアクティビティループを**実行しない**。これらはリクエストに応答するサーバーである。その生存確認は OS レベルの子プロセス終了検出（セクション 5.3）のみで行われ、heartbeat は使用しない。

---

## 4. Agent の状態とプロセス監視

### 4.1 Agent の状態

`system-master` は各 agent に対してステートマシンを維持する:

```
         spawn
  [STOPPED] ──────> [STARTING]
      ^                  │
      │           initialization
      │            complete
      │                  v
      │             [RUNNING]
      │                  │
      │            process exit
      │             detected
      │                  │
      │           restart policy
      │              applied
      │            /          \
      │     restart=yes    restart=no
      │         │               │
      │         v               v
      └──── [STARTING]     [STOPPED]
```

状態:

| 状態 | 説明 |
|---|---|
| `STOPPED` | 実行中でない。PID なし |
| `STARTING` | プロセスは起動済み。初期化の完了を待機中 |
| `RUNNING` | プロセス生存中。アクティビティループがアクティブ（user agent）、またはリクエストを処理中（インフラ） |

`UNHEALTHY` 状態は存在しない。プロセスが終了した場合、ポリシーに基づいて即座にリスタートまたは停止される。

### 4.2 プロセス監視

`system-master` は **OS レベルの子プロセスハンドリングのみ**で agent を監視する:

- `waitpid` / プロセスハンドルコールバックを通じて子プロセスの終了を検出する。
- 予期しない終了時 → リスタートポリシーを適用する（セクション 5）。
- heartbeat ベースのヘルスチェックなし。ポーリングなし。タイムアウトなし。

これはシンプルで信頼性が高い。プロセスが実行中であれば、それは生きている。

### 4.3 ステータスブロードキャスト（オブザーバビリティ）

user agent はオプションで約 5 分ごとに**ステータス event**（kind `4300`）を publish し、ダッシュボード表示に使用する:

```json
{
  "kind": 4300,
  "tags": [
    ["agent_name", "user3"],
    ["role", "user-agent"]
  ],
  "content": "{\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0,\"last_action\":\"browse_marketplace\",\"tick_count\":42,\"ts\":1700000000}"
}
```

`content` 内のフィールド:

| フィールド | 型 | 説明 |
|---|---|---|
| `balance_sats` | int | 現在の Cashu wallet 残高（sats） |
| `programs_owned` | int | agent が保有するプログラム数 |
| `programs_listed` | int | 売りに出されているプログラム数 |
| `active_trades` | int | 進行中の取引交渉の数 |
| `last_action` | string | 直前のティックで agent が実行したアクション |
| `tick_count` | int | agent 起動以降の合計ティック数 |
| `ts` | int | Unix タイムスタンプ |

**重要**: これらのステータス event は純粋にダッシュボード用の情報提供目的である。`system-master` はこれらを参照したり、これらに基づいて行動することは**ない**。

### 4.4 システムダッシュボード

agent の状態テーブルを表示するシンプルなステータスエンドポイントまたは CLI コマンド:

```
Agent         State      PID     Uptime    Restarts  Last Action
───────────── ────────── ─────── ───────── ───────── ──────────────────
nostr-relay   RUNNING    12345   1h 23m    0         (server)
cashu-mint    RUNNING    12346   1h 23m    0         (server)
user0         RUNNING    12350   1h 22m    1         generate_program
user1         RUNNING    12351   0h 04m    3         browse_marketplace
...
user9         RUNNING    12359   1h 22m    0         idle
```

---

## 5. Agent ライフサイクル

### 5.1 起動

1. `system-master` が agent マニフェストを読み込む。
2. agent プロセスを起動し、状態を `STARTING` にする。
3. **30 秒**の**起動タイムアウト**を開始する。
4. タイムアウト内に agent が初期化を完了すれば（relay への接続、wallet の読み込み）、状態は `RUNNING` になる。
5. タイムアウトが満了した場合、リスタートポリシーが適用される。

### 5.2 グレースフル停止

1. `system-master` が agent プロセスに `SIGTERM` を送信する。
2. agent はシグナルを受信し、進行中の取引を完了させ、状態をディスクに永続化してから終了コード 0 で終了する。
3. `system-master` はプロセスの終了を最大 **10 秒**待つ。
4. プロセスが終了しない場合、`system-master` は `SIGKILL` を送信する。
5. 状態が `STOPPED` になる。

### 5.3 クラッシュ検出

クラッシュは以下の場合に検出される:
- 子プロセスが予期せず終了した場合（終了コード != 0、またはシグナルによる kill）。
- `system-master` が子プロセスハンドルの `exit` イベントを受信した場合。

クラッシュ時:
1. 終了コード/シグナル、タイムスタンプ、agent の stderr の最後 50 行がログに記録される。
2. リスタートポリシーが直ちに適用される。

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
3. 生存している場合、監視を再接続する（子プロセスハンドルの再登録）。
4. 停止している場合、リスタートポリシーを適用する。

これにより、`system-master` はすべての agent をリスタートせずに復旧できる。

### 7.3 孤児プロセスのクリーンアップ

起動時に `system-master` は、想定されるコマンドパターンに一致するプロセスを確認することで、孤児プロセス（supervisor なしで実行中の agent）もスキャンする。孤児は設定に応じて養子として管理されるか、kill される。

---

## 8. スケーラビリティに関する考慮事項

### 8.1 現在の規模

- 10 user agent + 3 system プロセス = 合計 13 プロセス。
- ステータスブロードキャスト: 13 agent x 約 5 分に 1 イベント = relay 負荷は無視できる程度。
- 取引アクティビティ: アクティブな取引時、user agent あたり約 1〜2 Nostr event/分。

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
| CPU | ハードリミットなし（WSL2 はホスト CPU を共有） | ステータスブロードキャストまたは `ps` で監視 |
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
| 自律アクティビティループ（約 60 秒ティック） | agent がアイドル時に経済行動（作成・閲覧・取引）を自律的に実行する |
| OS レベルのプロセス監視のみ | シンプルな `waitpid` ベースのクラッシュ検出。heartbeat ポーリング不要 |
| フラットな監視ツリー | 13 agent は少数。早すぎる抽象化よりもシンプルさを優先 |
| リスタート時の指数バックオフ | クラッシュループによるリソース消費を防止 |
| 復旧用の JSON 状態ファイル | シンプルで人間が読め、データベース依存なし |
| 制御用の Unix ドメインソケット | セキュア（ファイルシステム権限）、低オーバーヘッド、ネットワーク露出なし |
