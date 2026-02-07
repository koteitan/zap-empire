# Zap Empire: クロスレビューノート（統合版）

**レビュアー**: system-autonomy, system-nostr, system-zap
**承認者**: team-lead
**日付**: 2026-02-08
**ステータス**: 最終版 -- すべての解決事項はチームリードにより確認済み

**レビュー対象ドキュメント**:
- `docs/autonomy-design.md`（system-autonomy担当）
- `docs/nostr-design.md`（system-nostr担当）
- `docs/zap-design.md`（system-zap担当）

---

## 確認済みの解決事項

以下のすべての問題はチームリードによりレビューおよび解決済みです。各解決事項は最終決定であり、それぞれの設計ドキュメントに反映する必要があります。

---

### ISSUE-1: Heartbeat event kind の競合 [重大]

**発見事項**: autonomy-designではheartbeatにkind `30078`（パラメータ付き置換可能event）を使用しています。nostr-designではkind `4300`（通常event）を使用しています。kind `30078`はnostr-designではプログラムリスティングにも使用されており、三重の競合が発生しています。

| ドキュメント | Heartbeat Kind | 詳細 |
|---|---|---|
| autonomy-design.md | `30078`（パラメータ付き置換可能） | セクション3.1 -- agent IDを`d`タグに使用 |
| nostr-design.md | `4300`（通常event） | セクション6.8 -- `agent_name`タグを使用 |

**解決策**: **kind `4300`**（通常event、置換不可）を使用する。

Heartbeatは一時的なステータスシグナルであり、インプレースで更新されるべきデータではありません。通常event kindが意味的に正しいです。kind `30078`はプログラムリスティング専用とします。

**更新が必要**: autonomy-design.md セクション3.1および3.2。

---

### ISSUE-2: Heartbeat間隔の不一致 [中程度]

**発見事項**: autonomy-designでは5秒間隔のheartbeatと15秒のデッド閾値を指定しています。nostr-designでは30秒間隔と60秒のオフライン検出を指定しています。

| ドキュメント | Heartbeat間隔 | デッド閾値 |
|---|---|---|
| autonomy-design.md | 5秒 | 15秒（3回のビート欠落） |
| nostr-design.md | 30秒 | 60秒 |

**解決策**: **5秒間隔**、**15秒のデッド閾値**（3回のビート欠落）を使用する。

autonomyフレームワークがヘルス監視の権限を持ちます。5秒間隔のビートにより、リスタート回復フローにとって重要な高速クラッシュ検出が可能になります。relayは13体のagentからの毎秒約2.6個のheartbeat eventを容易に処理できます。

**更新が必要**: nostr-design.md セクション6.8およびセクション8。

---

### ISSUE-3: Heartbeatペイロードスキーマの不一致 [中程度]

**発見事項**: heartbeatのcontentフィールドが2つのドキュメント間で異なっています。

| フィールド | autonomy-design | nostr-design |
|---|---|---|
| `status` | `healthy` / `degraded` / `shutting-down` | `online` / `busy` / `idle` |
| `uptime` | `uptime`（秒） | `uptime_secs`（秒） |
| `memory` | `mem_mb` | 含まれず |
| `balance` | 含まれず | `balance_sats` |
| `programs` | 含まれず | `programs_owned`, `programs_listed` |
| `trades` | 含まれず | `active_trades` |

**解決策**: **両方のスキーマを統合**して単一のheartbeatペイロードにする。

autonomy-designのフィールド（`status`, `uptime_secs`, `mem_mb`）はスーパーバイザー向けのシステムレベルヘルスデータを提供します。nostr-designのフィールド（`balance_sats`, `programs_owned`, `programs_listed`, `active_trades`）はダッシュボード向けのアプリケーションレベルデータを提供します。両方が必要です。

正規heartbeatペイロード:

```json
{
  "kind": 4300,
  "pubkey": "<agent-pubkey>",
  "tags": [
    ["agent_name", "user3"],
    ["role", "user-agent"]
  ],
  "content": "{\"status\":\"healthy\",\"uptime_secs\":3621,\"mem_mb\":42,\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0,\"ts\":1700000000}"
}
```

ステータス語彙: `healthy` / `degraded` / `shutting-down`（autonomy-design由来、system-masterが監視判断に使用）。

**更新が必要**: autonomy-design.md（セクション3.2）およびnostr-design.md（セクション6.8）の両方。

---

### ISSUE-4: プログラムリスティングのevent kind競合 [重大]

**発見事項**: nostr-designではプログラムリスティングにkind `30078`を使用しています。zap-designではkind `30023`（NIP-23 長文コンテンツ）を使用しています。

| ドキュメント | リスティングKind | 詳細 |
|---|---|---|
| nostr-design.md | `30078` | パラメータ付き置換可能、`d`タグ = プログラムUUID |
| zap-design.md | `30023` | NIP-23「長文コンテンツ」 |

**解決策**: **kind `30078`**（NIP-78 アプリケーション固有データ、パラメータ付き置換可能）を使用する。

kind `30023`はNIP-23「長文コンテンツ」であり、ブログ記事や論文を対象としたもので、マーケットプレイスリスティングとは意味的に合致しません。kind `30078`はアプリケーション固有の置換可能範囲（30000-39999）にあり、プログラムリスティングのようなカスタム置換可能データに適切な範囲です。nostr-designにはこのkind用の完全なリスティング構造が既に定義されています。

**更新が必要**: zap-design.md セクション5.1、5.3、および8.4。

---

### ISSUE-5: トレードメッセージの転送方式の競合 [重大]

**発見事項**: nostr-designではトレードメッセージにカスタムevent kind `4200-4203`および`4210`を定義しています（すべて平文）。zap-designではすべてのトレードおよび支払いメッセージを暗号化DM（kind `4`, NIP-04）経由でルーティングしています。

| ドキュメント | トレードメッセージの手段 | 詳細 |
|---|---|---|
| nostr-design.md | カスタムkind `4200-4203`, `4210`（平文） | 構造化されたトレードプロトコル |
| zap-design.md | 暗号化DM、kind `4`（NIP-04） | すべてのトレード/支払いを暗号化DMとして送信 |

**解決策**: **ハイブリッドアプローチ**。

- **公開カスタムkind**（`4200-4203`）をトレード交渉（オファー、承諾、拒否、完了）に使用。これらはダッシュボードから観測可能で、マーケットプレイス分析に活用できます。
- **新規kind `4204`**（"Trade Payment"）を**暗号化されたCashuトークン転送**に使用。Cashuトークンはbearer instrument（持参人型証券）であり、トークン文字列を見た誰でも換金できます。トークン転送は必ず暗号化（NIP-04またはNIP-44）する必要があります。
- **kind `4210`**（Program Delivery）も**暗号化**します -- プログラムソースコードは有料商品であり、relayの観測者に見えてはなりません。

更新されたトレードフロー:

```
Step  Kind   Name              Encryption  Description
───── ────── ───────────────── ─────────── ────────────────────────────────────
1     30078  Program Listing   Public      Seller lists program for sale
2     4200   Trade Offer       Public      Buyer proposes purchase
3     4201   Trade Accept      Public      Seller accepts with payment info
4     4204   Trade Payment     ENCRYPTED   Buyer sends Cashu token to seller
5     9735   Zap Receipt       Public      system-cashu confirms payment
6     4210   Program Delivery  ENCRYPTED   Seller sends program source to buyer
7     4203   Trade Complete    Public      Buyer confirms receipt
```

**更新が必要**: nostr-design.md（kind 4204を追加、4210を暗号化として明記）およびzap-design.md（カスタムkindを採用、トレードフローでkind 4のDMを置き換え）の両方。

---

### ISSUE-6: Agent命名の不整合 [中程度]

**発見事項**: ドキュメント間で3つの異なる命名規則が使用されています。

| ドキュメント | Cashu Mint Agent | Relay Agent | Cashu Zap Agent |
|---|---|---|---|
| autonomy-design.md | `cashu-mint` | `nostr-relay` | 記載なし |
| nostr-design.md | `system-cashu` | `system-relay` | `system-cashu` |
| zap-design.md | `system-cashu` | `system-nostr` | `system-mint-admin` |

**解決策**: 以下の正規名称に統一する:

| 正規名称 | 役割 | 説明 |
|---|---|---|
| `system-master` | プロセススーパーバイザー | 最上位スーパーバイザー、すべてのagentを起動・監視 |
| `system-relay` | Nostr relayプロセス | ポート7777のローカルstrfry relay |
| `system-mint` | Cashu mintプロセス | ポート3338のNutshell mint |
| `system-cashu` | Zap receipt発行者 | トークンスワップを監視し、kind 9735 receiptを発行 |
| `system-escrow` | Escrow agent | 高額トレードのエスクロー支払いを保持 |
| `user0`--`user9` | User agent | プログラムを作成しトランザクションを行うトレーディングagent |

**更新が必要**: 3つの設計ドキュメントすべて。

---

### ISSUE-7: データディレクトリ構造の競合 [中程度]

**発見事項**: 3つの異なるディレクトリレイアウトが提案されています。

| ドキュメント | レイアウト |
|---|---|
| autonomy-design.md | `data/<agent-id>/state.json`, `logs/<agent-id>/` |
| nostr-design.md | `data/agents/<agent-id>/nostr_secret.hex` |
| zap-design.md | `data/wallets/<agent-id>/wallet.db`, `data/mint/` |

**解決策**: `data/<agent-id>/`配下にすべてのagent固有ファイルをまとめた統一レイアウトにする。

```
zap-empire/
  config/
    agents.json              # Agent manifest (autonomy framework)
    constants.json           # Shared constants (relay URL, mint URL, ports)
  data/
    system-master/
      pids.json              # Child process PIDs for crash recovery
      control.sock           # Unix domain socket for zapctl
    system-relay/
      state.json
    system-mint/
      state.json
      mint.db                # Cashu mint SQLite database
    system-cashu/
      state.json
      nostr_secret.hex
      nostr_pubkey.hex
      wallet.db
      wallet.json
    system-escrow/
      state.json
      nostr_secret.hex
      nostr_pubkey.hex
      wallet.db
      wallet.json
    user0/
      state.json             # Autonomy framework state
      nostr_secret.hex       # Nostr keypair
      nostr_pubkey.hex
      wallet.db              # Cashu wallet
      wallet.json
    user1/
      ...
    user9/
      ...
  logs/
    system-master/
      state.log
      master.log
    system-relay/
      stdout.log
      stderr.log
    user0/
      stdout.log
      stderr.log
    ...
```

基本原則: すべてのagent固有データは`data/<agent-id>/`配下に配置する。`data/agents/`、`data/wallets/`などの別ディレクトリは設けない。

**更新が必要**: 3つの設計ドキュメントすべて。

---

### ISSUE-8: Zap receipt発行者のアイデンティティ [中程度]

**発見事項**: nostr-designでは`system-cashu`がkind `9735` zap receiptを発行するとしています。zap-designでは支払いループに仲介agentを介さない、買い手から売り手への直接トークン転送を記述しています。

**解決策**: **`system-cashu`**がmintでのトークンスワップを確認した後にkind `9735` zap receiptを発行する。

フロー: 買い手が暗号化されたCashuトークン（kind `4204`）を売り手に送信すると、売り手はmintでそれを換金します。`system-cashu`はmintのスワップ活動を監視し（または売り手から通知を受け）、支払いの独立した証明としてkind `9735` zap receiptを発行します。これはNIP-57のパターンに従い、信頼された第三者（"zapプロバイダー"）がreceiptを発行します。

**更新が必要**: zap-design.md（支払いフローにsystem-cashuを追加）。

---

### ISSUE-9: Kind 30078の多重使用 [中程度]

**発見事項**: kind `30078`がプログラムリスティング（nostr-design）、トレードreceipt（zap-design）、heartbeat（autonomy-design）の3つの異なる意味目的で使用されていました。

**解決策**: 各目的に個別のkindを割り当てる。

- `30078` -- プログラムリスティング専用（パラメータ付き置換可能）
- `4300` -- Heartbeat（ISSUE-1で解決済み）
- トレードreceiptは`system-cashu`からのkind `9735` zap receiptに置き換え（ISSUE-8で解決済み）
- kind `30079`は廃止 -- NIP-33の置換可能eventが同じ`d`タグで再発行することでリスティング更新を処理します。別途「更新」用kindを設けるのは冗長です。

**更新が必要**: nostr-design.md（event kindテーブルからkind 30079を削除）、zap-design.md（receiptに30078ではなく9735を使用）。

---

### ISSUE-10: Escrow event kindの欠如 [新規 -- チームリードによる追加]

**発見事項**: zap-design.md（セクション9）にはescrowメカニズムが記述されていますが、escrow操作用のNostr event kindが定義されていません。escrowフローは標準化されたkindのない非公式なJSONメッセージを使用しています。

**解決策**: **escrow event kind `4220-4223`**を追加する:

| Kind | 名称 | 暗号化 | 説明 |
|---|---|---|---|
| `4220` | Escrow Lock | 暗号化 | 買い手がsystem-escrowに支払いをロック（Cashuトークンを含む） |
| `4221` | Escrow Release | 公開 | 買い手が受領を確認し、売り手への支払い解放を承認 |
| `4222` | Escrow Dispute | 公開 | 買い手がトレードに対し異議を申し立て |
| `4223` | Escrow Timeout | 公開 | system-escrowがタイムアウト満了後に自動解放 |

kind `4220`はCashu bearerトークンを含むため暗号化が必要です（kind `4204`と同じ根拠）。

**更新が必要**: nostr-design.md（event kindテーブルに追加）およびzap-design.md（セクション9、これらのkindを使用）の両方。

---

### ISSUE-11: Relay URLとMint URLの参照が一貫していない [軽微]

**発見事項**: autonomy-designではrelayポートが指定されていません。mint URLもautonomy-designには記載がありません。

| ドキュメント | Relay URL | Mint URL |
|---|---|---|
| autonomy-design.md | `ws://127.0.0.1:<port>`（未指定） | 記載なし |
| nostr-design.md | `ws://127.0.0.1:7777` | `http://127.0.0.1:3338`（trade accept内） |
| zap-design.md | 記載なし | `http://127.0.0.1:3338` |

**解決策**: 両URLを共有設定定数ファイルに追加し、一貫して参照する。

共有定数（`config/constants.json`）:

```json
{
  "relay_url": "ws://127.0.0.1:7777",
  "mint_url": "http://127.0.0.1:3338",
  "relay_port": 7777,
  "mint_port": 3338,
  "heartbeat_interval_ms": 5000,
  "heartbeat_timeout_ms": 15000,
  "startup_timeout_ms": 30000
}
```

**更新が必要**: autonomy-design.md（定数を参照し、ポート7777を明示的に指定）。

---

### ISSUE-12: 技術スタックの曖昧さ [軽微]

**発見事項**: autonomy-designではNode.js（agentマニフェストが`node`、`--max-old-space-size`を使用）を想定しています。nostr-designでは複数言語が列挙されています。zap-designではPython（Nutshellライブラリ）を想定しています。

| ドキュメント | 想定言語 | 詳細 |
|---|---|---|
| autonomy-design.md | Node.js | マニフェストが`node`を使用、`--max-old-space-size`によるメモリ制限 |
| nostr-design.md | 複数言語 | Python、Node.js、Rustがすべてオプションとして列挙 |
| zap-design.md | Python | すべてのコード例がNutshell（Python）を使用 |

**解決策**: **全体をPython**で統一（初回レビュー後にチームリードが更新）。

- **すべてのagentおよびmint**: Python -- Cashu mint（Nutshell）はPythonであり、agentはウォレット操作に`cashu.wallet`を直接インポートします。Nostr通信には`pynostr`または`websockets`を使用します。
- これにより、agentとmint間の不要なHTTPホップが排除され、スタック全体が単一言語で統一されシンプルになります。

3つの設計ドキュメント（autonomy-design.md、nostr-design.md、zap-design.md）はすべてPythonを主要言語として反映するよう更新されました。

**ステータス**: 全ドキュメントに適用済み。

---

## 更新されたEvent Kindテーブル（正規版）

これがZap Empireにおけるすべての Nostr event kindの唯一の信頼できる情報源です。

### 標準Kind

| Kind | NIP | 名称 | 説明 |
|---|---|---|---|
| `0` | NIP-01 | Agent Metadata | agentのアイデンティティとプロファイル（起動時に発行） |
| `5` | NIP-09 | Event Deletion | オファーの取り消し、リスティングのキャンセル |
| `9735` | NIP-57 | Zap Receipt | 支払い確認（system-cashuが発行） |

### アプリケーションKind -- マーケットプレイス

| Kind | 名称 | 置換可能? | 暗号化 | 説明 |
|---|---|---|---|---|
| `30078` | Program Listing | はい（`d`タグ） | 公開 | agentがプログラムを出品 |

### アプリケーションKind -- トレードプロトコル

| Kind | 名称 | 置換可能? | 暗号化 | 説明 |
|---|---|---|---|---|
| `4200` | Trade Offer | いいえ | 公開 | 買い手がプログラムの購入を提案 |
| `4201` | Trade Accept | いいえ | 公開 | 売り手がオファーを承諾 |
| `4202` | Trade Reject | いいえ | 公開 | 売り手がオファーを拒否 |
| `4203` | Trade Complete | いいえ | 公開 | 買い手が配信受領を確認 |
| `4204` | Trade Payment | いいえ | **暗号化** | 買い手がCashuトークンを売り手に送信 |
| `4210` | Program Delivery | いいえ | **暗号化** | 売り手がプログラムソースを買い手に送信 |

### アプリケーションKind -- Escrow

| Kind | 名称 | 置換可能? | 暗号化 | 説明 |
|---|---|---|---|---|
| `4220` | Escrow Lock | いいえ | **暗号化** | 買い手がCashuトークンをsystem-escrowにロック |
| `4221` | Escrow Release | いいえ | 公開 | 買い手が売り手への支払い解放を承認 |
| `4222` | Escrow Dispute | いいえ | 公開 | 買い手がトレードに異議を申し立て |
| `4223` | Escrow Timeout | いいえ | 公開 | system-escrowが期限切れescrowを自動解放 |

### アプリケーションKind -- システム

| Kind | 名称 | 置換可能? | 暗号化 | 説明 |
|---|---|---|---|---|
| `4300` | Agent Status Broadcast | いいえ | 公開 | ダッシュボード向けの定期的なステータスレポート（約5分ごと）; ヘルス監視用ではない |
| `4301` | Agent Status Change | いいえ | 公開 | agentの状態遷移アナウンス |

### 廃止/削除されたKind

| Kind | 以前の用途 | 理由 |
|---|---|---|
| `30079` | Program Listing Update | 冗長; NIP-33の置換可能eventが同じ`d`タグでkind `30078`を再発行することで更新を処理 |
| `30023` | Program Listing（zap-design） | kind `30078`に置き換え; NIP-23はリスティングには意味的に不適切 |

---

## 更新されたAgentインベントリ（正規版）

| 正規名称 | タイプ | 再起動ポリシー | ウォレット? | Nostrアイデンティティ? | 説明 |
|---|---|---|---|---|---|
| `system-master` | supervisor | N/A（最上位） | なし | なし | すべてのagentを起動・監視; zapctlを公開 |
| `system-relay` | infrastructure | `always` | なし | あり | `ws://127.0.0.1:7777`上のローカルstrfry Nostr relay |
| `system-mint` | infrastructure | `always` | なし | なし | `http://127.0.0.1:3338`上のNutshell Cashu mint（Python） |
| `system-cashu` | system agent | `always` | あり | あり | mintスワップを監視し、kind 9735 zap receiptを発行 |
| `system-escrow` | system agent | `on-failure` | あり | あり | 高額トレードのエスクロー支払いを保持 |
| `user0` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user1` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user2` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user3` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user4` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user5` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user6` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user7` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user8` | user agent | `on-failure` | あり | あり | トレーディングagent |
| `user9` | user agent | `on-failure` | あり | あり | トレーディングagent |

**合計**: 15の管理対象プロセス。

### 起動順序

1. **フェーズ1 -- インフラストラクチャ**: `system-relay`, `system-mint`（並列）
2. **フェーズ2 -- システムagent**: `system-cashu`, `system-escrow`（フェーズ1が正常になった後）
3. **フェーズ3 -- User agent**: `user0`から`user9`（並列、フェーズ2が正常になった後）

---

## 更新されたトレードフロー（正規版）

```
Seller (user3)              Relay                system-cashu         Buyer (user7)
     |                        |                       |                    |
     |-- 30078 listing ------>|                       |                    |
     |                        |                       |                    |
     |                        |<----- 4200 offer -------------------------|
     |<--- 4200 offer --------|                       |                    |
     |                        |                       |                    |
     |-- 4201 accept -------->|                       |                    |
     |                        |---- 4201 accept ----->|------------------->|
     |                        |                       |                    |
     |                        |<----- 4204 payment (ENCRYPTED) -----------|
     |<--- 4204 payment ------|                       |                    |
     |                        |                       |                    |
     |  [redeem token at mint]|                       |                    |
     |  ...................... mint swap ............. |                    |
     |                        |                       |                    |
     |                        |<-- 9735 zap receipt --|                    |
     |<--- 9735 receipt ------|                       |--- 9735 receipt -->|
     |                        |                       |                    |
     |-- 4210 delivery ------>| (ENCRYPTED)           |                    |
     |                        |---- 4210 delivery --->|------------------->|
     |                        |                       |                    |
     |                        |<----- 4203 complete ----------------------|
     |<--- 4203 complete -----|                       |                    |
     |                        |                       |                    |
```

### トレード状態マシン

```
LISTED ──> OFFERED ──> ACCEPTED ──> PAID ──> DELIVERED ──> COMPLETE
                   \──> REJECTED
```

| 状態 | トリガー | Event Kind |
|---|---|---|
| LISTED | 売り手がリスティングを発行 | `30078` |
| OFFERED | 買い手がオファーを送信 | `4200` |
| ACCEPTED | 売り手が承諾 | `4201` |
| REJECTED | 売り手が拒否 | `4202` |
| PAID | 買い手がトークンを送信 + system-cashuが確認 | `4204` + `9735` |
| DELIVERED | 売り手がプログラムソースを送信 | `4210` |
| COMPLETE | 買い手が受領を確認 | `4203` |

---

## サマリーテーブル

| 問題 | 重大度 | 解決策 | 更新が必要なドキュメント |
|---|---|---|---|
| ISSUE-1: Heartbeat kind | 重大 | kind `4300`を使用 | autonomy-design |
| ISSUE-2: Heartbeat間隔 | 中程度 | 5秒間隔を使用 | nostr-design |
| ISSUE-3: Heartbeatペイロード | 中程度 | 両スキーマを統合 | autonomy-design, nostr-design |
| ISSUE-4: リスティングkind | 重大 | kind `30078`を使用 | zap-design |
| ISSUE-5: トレード転送方式 | 重大 | ハイブリッド: 公開交渉 + 暗号化支払い（kind `4204`） | nostr-design, zap-design |
| ISSUE-6: Agent命名 | 中程度 | 標準化された名称（インベントリ参照） | 3ドキュメントすべて |
| ISSUE-7: ディレクトリ構造 | 中程度 | `data/<agent-id>/`統一レイアウト | 3ドキュメントすべて |
| ISSUE-8: Zap receipt発行者 | 中程度 | system-cashuがkind `9735`を発行 | zap-design |
| ISSUE-9: Kind 30078の多重使用 | 中程度 | 目的ごとに個別kind; `30079`を廃止 | nostr-design, zap-design |
| ISSUE-10: Escrow event kind | 新規 | kind `4220-4223`を追加 | nostr-design, zap-design |
| ISSUE-11: Relay/Mint URL | 軽微 | 共有`config/constants.json` | autonomy-design |
| ISSUE-12: 技術スタック | 軽微 | Mint=Python, Agent=全体をPythonで統一 | zap-design, nostr-design |
| ISSUE-13: Heartbeat再設計 | 重大 | Heartbeatはヘルスチェックではない; 自律的アクティビティループ（約60秒ティック）として再設計。Kind 4300はダッシュボード専用のステータスブロードキャスト（約5分）に用途変更。UNHEALTHY状態を廃止。プロセス監視はOSレベルのwaitpidのみで実施。 | autonomy-design, nostr-design, user-agent-design |

---

## アクションアイテム

### system-autonomy (autonomy-design.md)
1. ~~heartbeat kindを`30078`から`4300`に更新~~ 完了
2. ~~heartbeatペイロードスキーマを統合~~ 完了
3. relay URL `ws://127.0.0.1:7777`およびmint URL `http://127.0.0.1:3338`を追加（セクション8.4）
4. agentインベントリを更新: agentを正規名称にリネーム、`system-cashu`と`system-escrow`を追加、合計を15に更新（セクション1.1）
5. フェーズ2（システムagent）を起動順序に追加（セクション2.3）
6. 共有設定に`config/constants.json`を参照
7. **ISSUE-13**: heartbeatを自律的アクティビティループ（約60秒ティック）に再設計。UNHEALTHY状態を廃止、ヘルスチェックループを廃止、アクティビティ選択ロジックを追加。完了

### system-nostr (nostr-design.md)
1. ~~heartbeat間隔を30秒から5秒に更新~~ → **ISSUE-13**: Kind 4300をステータスブロードキャスト（約5分）に用途変更。完了
2. event kindテーブルからkind `30079`を削除（セクション5）
3. kind `4204`（Trade Payment、暗号化）をevent kindテーブルに追加
4. kind `4210`（Program Delivery）を暗号化として明記
5. escrow kind `4220-4223`をevent kindテーブルに追加
6. agent名を正規命名規則に更新
7. `nostr-tools`を主要クライアントライブラリとして推奨

### system-zap (zap-design.md)
1. リスティングkindを`30023`から`30078`に更新（セクション5.1、5.3、8.4）
2. カスタムトレードkind `4200-4203`、支払い用`4204`、配信用`4210`を採用
3. zap receipt発行者としてsystem-cashuを支払いフローに追加
4. セクション9でescrow kind `4220-4223`を使用
5. Pythonに加えてNode.js/cashu-tsのコード例を追加
6. agent名を正規命名規則に更新
7. ディレクトリレイアウトを`data/<agent-id>/`に更新
