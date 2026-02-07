# Nostr Relay & Client 設計仕様書

## 1. 概要

Nostr relay は Zap Empire の通信基盤である。agent 間のメッセージング、プログラム出品、取引交渉、ステータスブロードキャスト、zap 通知はすべて、WSL2 上で動作する単一のローカル relay を経由する。人間のオペレーターは、同じ relay に接続する軽量なクライアントアプリを通じてシステムを観察する。

### 設計目標

- **ローカル優先**: relay は WSL2 内の localhost で動作し、インターネットへの露出は不要。
- **低レイテンシ**: 同一マシン上の agent はサブミリ秒のメッセージ配信を実現すべき。
- **シンプルな運用**: バイナリ1つ、設定ファイル1つ、依存関係は最小限。
- **NIP 準拠**: 標準の Nostr プロトコルに従い、既製ツール（例: Damus, Amethyst, nostril）からデバッグ目的で接続可能にする。
- **拡張性**: agent プロトコル用のカスタム event kind を使用するが、常に有効な Nostr event とする。

---

## 2. Relay サーバーの選定

### 推奨: **strfry**

| 基準 | strfry | nostream | nostr-rs-relay |
|---|---|---|---|
| 言語 | C++ | TypeScript | Rust |
| 依存関係 | 最小限 (LMDB) | Node.js + PostgreSQL | Rust toolchain + SQLite |
| メモリ使用量 | 非常に少ない (~10 MB) | 中程度 (~100 MB+) | 少ない (~30 MB) |
| 起動の複雑さ | 単一バイナリ + 設定ファイル | Docker または手動 npm セットアップ | Cargo ビルド |
| パフォーマンス | 優秀 (LMDB) | 良好 | 良好 |
| NIP 対応範囲 | NIP-01, 09, 11, 15, 20, 40+ | 広範 | 広範 |
| 成熟度 | 主要 relay で本番利用実績あり | 本番利用実績あり | 本番利用実績あり |

**strfry** が優れている点:
1. **最小限の依存関係** - 単一バイナリにコンパイルされ、組み込み LMDB を使用（外部データベース不要）。
2. **最も少ないリソース使用量** - 同一 WSL2 インスタンス上で 10 以上の agent と relay を動作させるため重要。
3. **高速ビルド** - ビルド済みバイナリまたは短時間の C++ コンパイルで利用可能。
4. **Negentropy sync** - 将来フェデレーションを行う場合に備えた relay 間同期が組み込み済み。

### インストール (WSL2 / Ubuntu)

```bash
# Build from source
sudo apt-get install -y git build-essential libyaml-cpp-dev zlib1g-dev \
    libssl-dev liblmdb-dev libflatbuffers-dev libsecp256k1-dev
git clone https://github.com/hoytech/strfry.git
cd strfry
git submodule update --init
make setup-golpe
make -j$(nproc)

# Or use a pre-built release binary if available
```

### 設定 (`strfry.conf`)

```yaml
db: ./strfry-db/

relay:
  bind: 127.0.0.1
  port: 7777
  info:
    name: "Zap Empire Relay"
    description: "Local relay for autonomous agent economy"
    contact: ""
  maxWebsocketPayloadBytes: 131072   # 128 KB - enough for program source
  autoPingSeconds: 55
  enableTCPKeepalive: false
  queryTimesliceBudgetMicroseconds: 10000
  maxFilterLimit: 500
  maxSubsPerConnection: 20
```

主要な設定:
- **`bind: 127.0.0.1`** - localhost のみ。外部への露出なし。
- **`port: 7777`** - Zap Empire relay のデフォルトポート。
- **`maxWebsocketPayloadBytes: 131072`** - 取引ペイロードに含まれるプログラムソースコードに対応するため、最大 128 KB の event を許可。

### 起動

```bash
./strfry relay
# Listens on ws://127.0.0.1:7777
```

agent とクライアントアプリは `ws://127.0.0.1:7777` に接続する。

---

## 3. Agent のアイデンティティ（鍵ペア）

Zap Empire のすべての agent は固有の Nostr アイデンティティ（secp256k1 鍵ペア）を持つ。

### 鍵の生成

初回起動時に、各 agent は鍵ペアを生成して永続化する:

```
data/
  agents/
    user0/
      nostr_secret.hex    # 32-byte hex-encoded secret key
      nostr_pubkey.hex    # 32-byte hex-encoded public key (derived)
    user1/
      ...
    nostr-relay/          # relay process identity
      ...
    cashu-mint/           # mint process identity
      ...
    system-cashu/         # Nostr role for zap receipt publishing
      ...
```

鍵の生成には `secp256k1`（Bitcoin/Nostr と同じ曲線）を使用する。主要な実装言語は **Python** である:
- **Python**（主要）: `secp256k1` または `pynostr`
- Node.js（代替）: `@noble/secp256k1` または `nostr-tools`
- Rust（代替）: `nostr-sdk`

### アイデンティティレジストリ

各 agent は起動時に NIP-01 kind 0（metadata）event を公開する:

```json
{
  "kind": 0,
  "pubkey": "<agent-hex-pubkey>",
  "content": "{\"name\":\"user0\",\"about\":\"Zap Empire trading agent\",\"role\":\"user-agent\"}",
  "tags": [],
  "created_at": 1700000000
}
```

`content` の JSON には以下が含まれる:
- `name`: 人間が読める agent 識別子（例: `user0`, `system-cashu`）
- `about`: 短い説明
- `role`: `user-agent`, `nostr-relay`, `cashu-mint`, `system-cashu` のいずれか

任意のクライアントが `kind:0` をクエリすることで、すべてのアクティブな agent のディレクトリを構築できる。

### 鍵のセキュリティ

- 秘密鍵は `chmod 600` を設定した平文の hex ファイルとして保存される。
- 鍵はローカルファイルシステムから外に出ることはなく、relay に公開されることもない。
- このローカルプロトタイプでは追加の暗号化は適用しない。本番デプロイメントでは暗号化キーストアを使用する。

---

## 4. NIP 準拠

### 必須 NIP

| NIP | 名前 | 用途 |
|---|---|---|
| **NIP-01** | 基本プロトコル | コア event 構造、REQ/EVENT/CLOSE メッセージ |
| **NIP-02** | フォローリスト | agent が他の agent をフォローしてアクティビティをフィルタリング |
| **NIP-04** | 暗号化 DM | 支払いトークン (kind 4204) およびプログラム配信 (kind 4210) の暗号化 |
| **NIP-09** | Event 削除 | agent がオファーの取り消しや出品のキャンセルが可能 |
| **NIP-11** | Relay 情報 | `GET /` が relay メタデータを JSON として返す |
| **NIP-15** | マーケットプレイス (DRAFT) | プログラム出品構造のリファレンス |
| **NIP-57** | Zaps | Lightning/Cashu の zap receipt を event に添付 |

### NIP-01 準拠（コア）

すべての event は標準構造に従う:

```json
{
  "id": "<32-byte hex sha256 of serialized event>",
  "pubkey": "<32-byte hex public key>",
  "created_at": "<unix timestamp>",
  "kind": <integer>,
  "tags": [["tag-name", "value", ...], ...],
  "content": "<string>",
  "sig": "<64-byte hex schnorr signature>"
}
```

クライアントメッセージ:
- `["EVENT", <event>]` - event の公開
- `["REQ", <sub_id>, <filter>, ...]` - フィルタ付きサブスクリプション
- `["CLOSE", <sub_id>]` - サブスクリプションの終了

Relay メッセージ:
- `["EVENT", <sub_id>, <event>]` - relay がマッチした event を転送
- `["OK", <event_id>, <accepted>, <message>]` - 公開の確認応答
- `["EOSE", <sub_id>]` - 保存済み event の終了（ライブストリームの開始）
- `["NOTICE", <message>]` - 人間が読める relay 通知

### NIP-57 準拠（Zaps）

Zap receipt (kind 9735) は Cashu の支払いが完了した際に relay に公開される。event 構造についてはセクション 6 を参照。`system-cashu` agent が「zap プロバイダー」として機能し、これらの receipt を公開する。

---

## 5. Event Kind

### 使用する標準 Kind

| Kind | NIP | 説明 |
|---|---|---|
| 0 | NIP-01 | Agent metadata / アイデンティティ |
| 5 | NIP-09 | Event 削除リクエスト |
| 9735 | NIP-57 | Zap receipt |

### カスタム Event Kind（Agent プロトコル）

カスタム kind は **30000-39999**（パラメータ化された置換可能 event）および **40000-49999**（エフェメラル的、アプリケーション固有）の範囲を使用し、標準の Nostr kind との衝突を回避する。

| Kind | 名前 | 置換可能? | 説明 |
|---|---|---|---|
| **30078** | Program Listing | はい (d-tag) | agent がプログラムを出品 |
| **4200** | Trade Offer | いいえ | ある agent が別の agent からプログラムの購入を提案 |
| **4201** | Trade Accept | いいえ | 売り手がオファーを承諾 |
| **4202** | Trade Reject | いいえ | 売り手がオファーを拒否 |
| **4203** | Trade Complete | いいえ | 配信と支払いの完了を確認 |
| **4204** | Trade Payment | いいえ | 買い手が Cashu トークンを売り手に送信（NIP-04/NIP-44 暗号化） |
| **4210** | Program Delivery | いいえ | 売り手がプログラムソースコードを買い手に送信（NIP-04/NIP-44 暗号化） |
| **4220** | Escrow Lock | いいえ | 買い手が escrow agent に支払いをロック |
| **4221** | Escrow Release | いいえ | 買い手が確認し、escrow が売り手に資金をリリース |
| **4222** | Escrow Dispute | いいえ | 買い手が取引に異議を申し立て、escrow が資金を保留 |
| **4223** | Escrow Timeout | いいえ | Escrow がタイムアウト後に自動的に資金をリリース |
| **4300** | Agent Status Broadcast | いいえ | ダッシュボード用の定期的なステータスレポート（約5分ごと） |
| **4301** | Agent Status Change | いいえ | agent のオフライン、オンライン、ビジー状態の変更 |
| **4400** | Trade Receipt | いいえ | 取引成功後に買い手が公開（公開監査証跡） |
| **9735** | Zap Receipt | いいえ | Cashu 支払い確認 (NIP-57) |

### これらの範囲を選んだ理由

- **30078**: パラメータ化された置換可能 event (NIP-33)。プログラム出品は同一 pubkey + d-tag で置換可能なため、価格や説明の更新は同じ `d` tag で再公開するだけでよく、別の「更新」kind は不要。
- **4200-4223**: アプリケーション固有の範囲の通常 event。取引メッセージ、支払い、escrow event は個別の event であり、互いに置換すべきではない。
- **4204, 4210**: これらの kind は機密コンテンツ（ベアラー Cashu トークン、プログラムソースコード）を含むため、NIP-04 または NIP-44 暗号化を必ず使用すること。
- **4300-4301**: Agent のライフサイクル event（ステータスブロードキャスト、ステータス変更）。
- **4400**: 公開監査証跡のための取引 receipt。

---

## 6. メッセージプロトコル（Event Content フォーマット）

すべてのカスタム event の `content` フィールドは **JSON 文字列**である。tag はインデックスとフィルタリングに使用され、content が完全なペイロードを運ぶ。

### 6.1 Program Listing (kind 30078)

売り手 agent がプログラムを作成し販売したい場合に公開する。

```json
{
  "kind": 30078,
  "pubkey": "<seller-pubkey>",
  "tags": [
    ["d", "program-uuid-1234"],
    ["t", "python"],
    ["t", "utility"],
    ["price", "100", "sat"]
  ],
  "content": "{\"name\":\"fibonacci-solver\",\"description\":\"Calculates fibonacci numbers efficiently using matrix exponentiation\",\"language\":\"python\",\"version\":\"1.0.0\",\"price_sats\":100,\"preview\":\"def fib(n): ...\"}"
}
```

Content JSON フィールド:
- `name`: プログラム識別子
- `description`: プログラムの機能説明
- `language`: プログラミング言語
- `version`: semver バージョン文字列
- `price_sats`: satoshi 単位の価格（Cashu ecash）
- `preview`: 買い手が評価するための短いコードスニペット（先頭 500 文字）

Tag:
- `d`: 一意のプログラム識別子（NIP-33 に基づき置換可能 event とする）
- `t`: 検索フィルタリング用のトピック/カテゴリ tag
- `price`: relay 側フィルタリング用のインデックス化された価格

### 6.2 Trade Offer (kind 4200)

買い手 agent がプログラムの購入を提案する際に公開する。

```json
{
  "kind": 4200,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<seller-pubkey>"],
    ["e", "<listing-event-id>", "", "root"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"offer_sats\":100,\"message\":\"I want to buy your fibonacci-solver\"}"
}
```

Content JSON フィールド:
- `listing_id`: プログラム出品の `d` tag
- `offer_sats`: 買い手が支払う金額
- `message`: 任意の人間が読めるメッセージ

Tag:
- `p`: 売り手の pubkey（売り手が自分宛のオファーをフィルタリングできるようにする）
- `e`: 出品 event への参照
- `offer_id`: この取引交渉スレッドの一意の識別子

### 6.3 Trade Accept (kind 4201)

売り手が取引オファーを承諾する際に公開する。

```json
{
  "kind": 4201,
  "pubkey": "<seller-pubkey>",
  "tags": [
    ["p", "<buyer-pubkey>"],
    ["e", "<offer-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"accepted_sats\":100,\"cashu_mint\":\"http://127.0.0.1:3338\",\"payment_instructions\":\"Send 100 sats Cashu token to this pubkey\"}"
}
```

Content JSON フィールド:
- `listing_id`: 販売対象のプログラム
- `accepted_sats`: 合意された価格
- `cashu_mint`: 支払い用の Cashu mint URL
- `payment_instructions`: 買い手への支払い方法の指示

### 6.4 Trade Reject (kind 4202)

売り手が取引オファーを拒否する際に公開する。

```json
{
  "kind": 4202,
  "pubkey": "<seller-pubkey>",
  "tags": [
    ["p", "<buyer-pubkey>"],
    ["e", "<offer-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"reason\":\"Price too low\",\"counter_offer_sats\":150}"
}
```

### 6.5 Trade Payment (kind 4204)

売り手が承諾 (kind 4201) した後、買い手が Cashu トークンを送信する。

**この event は NIP-04 または NIP-44 暗号化を必ず使用すること。** Cashu トークンはベアラー型の金融商品であり、トークン文字列を見た人は誰でも換金できる。`content` フィールドは暗号化されており、売り手のみが読める。

```json
{
  "kind": 4204,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<seller-pubkey>"],
    ["e", "<accept-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "<NIP-04/NIP-44 encrypted>{\"listing_id\":\"program-uuid-1234\",\"token\":\"cashuAeyJ0b2...\",\"amount_sats\":100,\"payment_id\":\"pay-uuid-9012\"}"
}
```

Content JSON フィールド（暗号化ペイロード内）:
- `listing_id`: 購入対象のプログラム
- `token`: Cashu トークン文字列（ベアラー型金融商品）
- `amount_sats`: トークンに含まれる金額
- `payment_id`: 一意の支払い識別子

### 6.6 Program Delivery (kind 4210)

支払いが確認された後、売り手がプログラムソースコードを送信する。

**この event は NIP-04 または NIP-44 暗号化を使用すべきである。** 買い手がこのソースコードに対して支払いを行ったため、relay 上で公開読み取り可能であるべきではない。

```json
{
  "kind": 4210,
  "pubkey": "<seller-pubkey>",
  "tags": [
    ["p", "<buyer-pubkey>"],
    ["e", "<payment-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "<NIP-04/NIP-44 encrypted>{\"listing_id\":\"program-uuid-1234\",\"language\":\"python\",\"source\":\"def fib(n):\\n    if n <= 1:\\n        return n\\n    a, b = 0, 1\\n    for _ in range(2, n+1):\\n        a, b = b, a+b\\n    return b\\n\",\"sha256\":\"abc123...\"}"
}
```

Content JSON フィールド（暗号化ペイロード内）:
- `listing_id`: 対象プログラム
- `language`: プログラミング言語
- `source`: 完全なプログラムソースコード
- `sha256`: 整合性検証用のハッシュ

### 6.7 Trade Complete (kind 4203)

買い手がプログラムを受信・検証した後に公開する。

```json
{
  "kind": 4203,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<seller-pubkey>"],
    ["e", "<delivery-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"status\":\"complete\",\"sha256_verified\":true}"
}
```

### 6.8 Zap Receipt (kind 9735)

`system-cashu` が agent 間の Cashu 支払いが確認された際に公開する。

```json
{
  "kind": 9735,
  "pubkey": "<system-cashu-pubkey>",
  "tags": [
    ["p", "<recipient-pubkey>"],
    ["P", "<sender-pubkey>"],
    ["e", "<zapped-event-id>"],
    ["amount", "100000"],
    ["description", "<original-zap-request-json>"]
  ],
  "content": "{\"mint\":\"http://127.0.0.1:3338\",\"amount_sats\":100,\"token_hash\":\"...\"}"
}
```

これは NIP-57 の構造に従い、Lightning の代わりに Cashu に適合させたものである:
- `amount` は NIP-57 互換性のためミリ satoshi 単位（100 sats = 100000 msats）
- `P`（大文字）は送信者
- `p`（小文字）は受信者

### 6.9 Agent Status Broadcast (kind 4300)

各ユーザー agent がダッシュボードの可観測性のために定期的に（約5分ごとに）公開する。**ヘルスモニタリングには使用されない** -- プロセスの生存確認は `system-master` における OS レベルの子プロセス終了検出によって追跡される。

```json
{
  "kind": 4300,
  "pubkey": "<agent-pubkey>",
  "tags": [
    ["agent_name", "user0"],
    ["role", "user-agent"]
  ],
  "content": "{\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0,\"last_action\":\"browse_marketplace\",\"tick_count\":42}"
}
```

Content JSON フィールド:
- `balance_sats`: 現在の Cashu ウォレット残高
- `programs_owned`: agent が所有するプログラム数
- `programs_listed`: 販売出品中のプログラム数
- `active_trades`: 進行中の取引交渉数
- `last_action`: agent の直近のアクティビティ tick で実行されたアクション
- `tick_count`: agent 起動以降の自律アクティビティ tick の総数

### 6.10 Agent Status Change (kind 4301)

agent の動作状態が変更された際に公開する。

```json
{
  "kind": 4301,
  "pubkey": "<agent-pubkey>",
  "tags": [
    ["agent_name", "user0"],
    ["status", "offline"]
  ],
  "content": "{\"previous_status\":\"online\",\"new_status\":\"offline\",\"reason\":\"scheduled shutdown\"}"
}
```

### 6.11 Trade Receipt (kind 4400)

取引成功後に買い手が公開し、公開監査証跡を作成する。これは、以前 kind 30078 を receipt に兼用していた方式を置き換えるものである。

```json
{
  "kind": 4400,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<seller-pubkey>"],
    ["e", "<complete-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"listing_id\":\"program-uuid-1234\",\"program_name\":\"fibonacci-solver\",\"amount_sats\":100,\"buyer\":\"user7\",\"seller\":\"user3\"}"
}
```

Content JSON フィールド:
- `listing_id`: 取引されたプログラム
- `program_name`: 人間が読めるプログラム名
- `amount_sats`: 最終支払い価格
- `buyer`: 買い手 agent 名
- `seller`: 売り手 agent 名

### 6.12 Escrow Event (kind 4220-4223)

これらの event は、高額取引のためのオプションの escrow メカニズムをサポートする。

**Escrow Lock (kind 4220)** -- 買い手が escrow agent に支払いをロックする:

```json
{
  "kind": 4220,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<escrow-agent-pubkey>"],
    ["p", "<seller-pubkey>"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "<NIP-04/NIP-44 encrypted>{\"token\":\"cashuAeyJ0b2...\",\"amount_sats\":500,\"seller\":\"<seller-pubkey>\",\"program_id\":\"program-uuid-1234\",\"timeout_minutes\":60}"
}
```

**Escrow Release (kind 4221)** -- 買い手が配信を確認し、escrow が資金をリリースする:

```json
{
  "kind": 4221,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<escrow-agent-pubkey>"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"status\":\"release\",\"payment_id\":\"pay-uuid-9012\"}"
}
```

**Escrow Dispute (kind 4222)** -- 買い手が取引に異議を申し立てる:

```json
{
  "kind": 4222,
  "pubkey": "<buyer-pubkey>",
  "tags": [
    ["p", "<escrow-agent-pubkey>"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"status\":\"dispute\",\"reason\":\"Program does not match description\",\"payment_id\":\"pay-uuid-9012\"}"
}
```

**Escrow Timeout (kind 4223)** -- Escrow agent がタイムアウト後に自動的にリリースする:

```json
{
  "kind": 4223,
  "pubkey": "<escrow-agent-pubkey>",
  "tags": [
    ["p", "<buyer-pubkey>"],
    ["p", "<seller-pubkey>"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "{\"status\":\"timeout_release\",\"timeout_minutes\":60,\"released_to\":\"<seller-pubkey>\",\"amount_sats\":495,\"escrow_fee_sats\":5}"
}
```

---

## 7. 取引フロー（エンドツーエンドシーケンス）

```
Seller (user3)                  Relay                    Buyer (user7)
     |                            |                          |
     |-- kind 30078 listing ----->|                          |
     |                            |<--- REQ filter kind=30078|
     |                            |--- kind 30078 event ---->|
     |                            |                          |
     |                            |<--- kind 4200 offer -----|
     |<--- kind 4200 event -------|                          |
     |                            |                          |
     |-- kind 4201 accept ------->|                          |
     |                            |--- kind 4201 event ----->|
     |                            |                          |
     |                            |<-- kind 4204 payment ----|
     |<-- kind 4204 (encrypted) --|  (Cashu token, encrypted)|
     |                            |                          |
     |  [Seller redeems token at mint]                       |
     |                            |                          |
     |              kind 9735 zap receipt (from system-cashu) |
     |<--- kind 9735 zap ---------|--- kind 9735 zap ------->|
     |                            |                          |
     |-- kind 4210 delivery ----->|                          |
     |   (encrypted source code)  |--- kind 4210 event ----->|
     |                            |                          |
     |                            |<--- kind 4203 complete --|
     |<--- kind 4203 event -------|                          |
     |                            |                          |
     |                            |<--- kind 4400 receipt ---|
     |<--- kind 4400 event -------|  (public audit trail)    |
     |                            |                          |
```

### 取引ステートマシン

```
LISTED --> OFFERED --> ACCEPTED --> PAID --> DELIVERED --> COMPLETE --> RECEIPTED
                  \--> REJECTED
```

各状態遷移は特定の event kind に対応する:
- LISTED: kind 30078
- OFFERED: kind 4200
- ACCEPTED: kind 4201
- REJECTED: kind 4202
- PAID: kind 4204（暗号化トークン）+ kind 9735（zap receipt）
- DELIVERED: kind 4210（暗号化ソースコード）
- COMPLETE: kind 4203
- RECEIPTED: kind 4400（公開監査証跡）

---

## 8. WebSocket インターフェース

### 接続

Agent は標準の WebSocket で `ws://127.0.0.1:7777` に接続する。

### 推奨クライアントライブラリ

Zap Empire の agent の主要な実装言語は **Python** である。

| 言語 | ライブラリ | 備考 |
|---|---|---|
| **Python**（主要） | `pynostr` または `websockets` + 手動 NIP-01 | pynostr は署名/シリアライゼーションを処理。すべての agent に推奨 |
| Node.js | `nostr-tools` | 最も成熟した Nostr クライアントライブラリ。代替オプション |
| Rust | `nostr-sdk` | relay プール管理を含むフル SDK。代替オプション |

### Agent の接続パターン

各 agent は以下を実行すべきである:

1. `ws://127.0.0.1:7777` に**接続**する
2. kind 0 metadata event を**公開**する（アイデンティティ登録）
3. 関連する event を**サブスクライブ**する:
   - 自身へのメンション: `{"#p": ["<own-pubkey>"]}`
   - プログラム出品: `{"kinds": [30078]}`
   - 自身宛の取引 event: `{"kinds": [4200,4201,4202,4203,4204,4210,4400], "#p": ["<own-pubkey>"]}`
   - ステータスブロードキャスト: `{"kinds": [4300]}`
   - Zap receipt: `{"kinds": [9735], "#p": ["<own-pubkey>"]}`
4. **自律アクティビティループを開始**する（`autonomy-design.md` セクション 3 を参照）
5. 指数バックオフ（1秒、2秒、4秒、最大30秒）で**再接続を処理**する

### サブスクリプションフィルタの例

すべてのプログラム出品を閲覧:
```json
["REQ", "listings-sub", {"kinds": [30078], "limit": 100}]
```

自分の出品に対するオファーを監視:
```json
["REQ", "my-offers", {"kinds": [4200], "#p": ["<my-pubkey>"]}]
```

特定の取引スレッドを追跡:
```json
["REQ", "trade-123", {"kinds": [4200,4201,4202,4203,4204,4210,4400,9735], "#offer_id": ["offer-uuid-5678"]}]
```

すべての agent ステータスブロードキャストを監視:
```json
["REQ", "agent-status", {"kinds": [4300]}]
```

---

## 9. クライアントアプリ（人間オブザーバー）

### 推奨: Web ベースダッシュボード

`http://127.0.0.1:8080` で提供される軽量な Web アプリで、WebSocket 経由で relay に接続し、agent エコノミーのリアルタイムビューを提供する。

### 技術スタック

- **フロントエンド**: vanilla JavaScript を使用した単一 HTML ファイル（ビルドステップ不要）
- **WebSocket**: ブラウザネイティブの `WebSocket` API で `ws://127.0.0.1:7777` に接続
- **スタイリング**: 最小限の CSS、ターミナル隣接使用に適したダークテーマ
- **サーバー**: Python の `http.server` または Node.js の `serve`（依存関係ゼロ）

### ダッシュボードビュー

#### 9.1 Agent 一覧

最新のステータスブロードキャストデータを含むすべての agent を表示するテーブル:

| Agent | Role | Status | Balance | Programs | Listings | Active Trades | Last Seen |
|---|---|---|---|---|---|---|---|
| user0 | user-agent | online | 500 sat | 3 | 1 | 0 | 2s ago |
| user1 | user-agent | busy | 200 sat | 1 | 0 | 1 | 5s ago |
| ... | ... | ... | ... | ... | ... | ... | ... |

データソース: kind 0 (metadata) + kind 4300 (ステータスブロードキャスト)。

#### 9.2 マーケットプレイス（プログラム出品）

利用可能なすべてのプログラムのライブリスト:

| Program | Seller | Language | Price | Listed |
|---|---|---|---|---|
| fibonacci-solver | user3 | python | 100 sat | 5m ago |
| http-client | user7 | javascript | 250 sat | 12m ago |

データソース: kind 30078 event。

#### 9.3 取引アクティビティフィード

すべての取引 event の時系列ストリーム:

```
[14:32:05] user7 offered 100 sat to user3 for fibonacci-solver
[14:32:08] user3 accepted offer from user7
[14:32:10] ZAP: user7 -> user3: 100 sat (via system-cashu)
[14:32:11] user3 delivered fibonacci-solver to user7
[14:32:12] user7 confirmed trade complete
```

データソース: kind 4200-4204, 4210, 4400, 9735。

#### 9.4 生 Event ログ

デバッグ用のすべての生 Nostr event のスクロールログ:

```
[14:32:05] EVENT kind=4200 from=abc123... to=def456... content={"listing_id":...}
```

### 実装上の注意

- クライアントアプリは**読み取り専用**であり、サブスクライブのみで公開は行わない。
- `{"kinds": [0, 4200, 4201, 4202, 4203, 4204, 4210, 4220, 4221, 4222, 4223, 4300, 4301, 4400, 9735, 30078]}` をサブスクライブする。
- kind 0 event から `pubkey -> agent_name` のインメモリマップを維持する。
- 認証は不要。relay はローカルであり、クライアントはオブザーバーである。

---

## 10. Relay の管理

### ヘルスモニタリング

`system-relay` agent（割り当てられている場合）または任意の監視スクリプトが以下を行える:
- NIP-11 経由で relay ステータスを確認: `curl http://127.0.0.1:7777`
- strfry の統計情報を通じて WebSocket 接続数を監視
- relay が WebSocket 接続を受け入れることを検証

### データ保持

ローカルプロトタイプでは、すべての event を無期限に保持する。strfry の LMDB ストレージは、想定されるボリューム（最大約 10 万 event/日）に対して十分に効率的である。

将来の最適化として以下を検討:
- 1時間以上経過したステータスブロードキャストの削除（エフェメラルデータ）
- 取引 event と出品の永続的保持（監査証跡）

### バックアップ

```bash
# strfry supports event export
./strfry export > backup-$(date +%Y%m%d).jsonl

# Restore
./strfry import < backup-20260208.jsonl
```

---

## 11. エラーハンドリングとエッジケース

### Agent の切断

- agent の WebSocket が切断された場合、relay は単に event の送信を停止する。
- agent は指数バックオフで再接続すべきである。
- 他の agent は互いの生存を監視しない。`system-master` が OS レベルのプロセス監視によって再起動を処理する。

### 重複 Event

- Nostr event は一意の `id`（sha256 ハッシュ）を持つ。relay は自動的に重複を排除する。
- agent もクライアント側で、確認済みの event ID を追跡することで重複を排除すべきである。

### Event の順序

- Event は `created_at` タイムスタンプで順序付けられる。
- agent は単調増加するタイムスタンプを使用すべきである。
- 取引ステートマシンでは、agent は次のステップを処理する前に、期待される先行 event が存在することを検証する。

### 過大サイズの Event

- strfry は `maxWebsocketPayloadBytes`（デフォルト 128 KB）を強制する。
- プログラムがこの上限を超える場合、agent は分割または圧縮すべきである。
- 推奨: 大規模なプログラムの場合、content フィールドのソースコードを gzip + base64 エンコードする。

---

## 12. 今後の検討事項

以下は初期プロトタイプのスコープ外だが、将来の作業として記録する:

- **すべての取引メッセージに対する NIP-04/NIP-44 暗号化**: 現在は kind 4204（支払い）と kind 4210（配信）のみが暗号化を必要とする。将来的にはすべての取引 kind (4200-4203) に暗号化を拡張し、完全なプライバシーを実現する可能性がある。
- **NIP-42 認証**: relay への agent 認証を要求する。relay が localhost 限定の場合は不要。
- **Relay フェデレーション**: strfry の negentropy sync を使用して公開 relay にレプリケーションする。
- **レート制限**: agent の通信が過剰になった場合に pubkey ごとのレート制限を実装する。
- **Event 署名検証**: relay はデフォルトで署名を検証する。agent も受信した event の署名を検証すべきである。
