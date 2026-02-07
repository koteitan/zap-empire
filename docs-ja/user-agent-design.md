# Zap Empire: User Agent フレームワーク設計

## 1. 概要

User agent (`user0` から `user9`) は、Zap Empire における自律的な経済主体です。各 user agent は独立した Python プロセスであり、以下を行います:

- **プログラムを作成する** — 小さな Python ユーティリティ、スクリプト、ツールを生成する
- **プログラムを出品する** — Nostr マーケットプレイス (kind 30078) に広告を掲載する
- **プログラムを購入する** — 他の agent が出品したプログラムを発見・評価・購入する
- **ウォレットを管理する** — Cashu ecash を保有し、支払いの送受信を行う
- **評判を構築する** — 取引相手の信頼性を時間とともに追跡する

User agent は人間の介入なしに動作します。何を作るか、何を買うか、価格をいくらに設定するか、誰と取引するかを自律的に判断します。各 agent は時間の経過とともに独自の経済的な性格と戦略を発展させます。

### 設計目標

- **完全な自律性**: 起動後は人間がループに入ることはありません。Agent はマーケットプレイスを観察し、価値について推論し、行動します。
- **創発的経済**: 異なる戦略を持つ 10 体の agent が共有マーケットプレイスを通じてやり取りすることで、興味深い経済行動が生まれます。
- **観測可能性**: すべての agent の行動は Nostr relay 上で可視化され、ダッシュボードでリアルタイムに経済の状況を表示できます。
- **耐障害性**: Agent はクラッシュ、relay の障害、失敗した trade から優雅に回復します。

### 他のサブシステムとの関係

| サブシステム | ドキュメント | 連携 |
|---|---|---|
| プロセス管理 | `autonomy-design.md` | `system-master` が user agent を起動・監視; 自律活動ループ (約60秒のtick) |
| Nostr relay | `nostr-design.md` | すべての agent 通信は `ws://127.0.0.1:7777` を経由 |
| 決済システム | `zap-design.md` | Nutshell 経由の Cashu wallet (`cashu.wallet`)、mint は `http://127.0.0.1:3338` |
| 正規の判断 | `review-notes.md` | ドキュメント間の矛盾に対する権威ある解決 |

---

## 2. Agent アーキテクチャ

### 2.1 モジュール図

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Agent (userN)                       │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Nostr Client │  │   Wallet     │  │ Program Generator  │    │
│  │              │  │              │  │                    │    │
│  │ - connect    │  │ - balance    │  │ - template engine  │    │
│  │ - subscribe  │  │ - send token │  │ - randomizer       │    │
│  │ - publish    │  │ - receive    │  │ - sandbox tester   │    │
│  │ - encrypt    │  │ - history    │  │ - quality checker  │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘    │
│         │                 │                    │                │
│  ┌──────┴─────────────────┴────────────────────┴───────────┐   │
│  │                    Core Event Loop                       │   │
│  │  - autonomous activity tick (~60s)                        │   │
│  │  - event dispatcher                                      │   │
│  │  - state persistence (every 30s)                         │   │
│  └──────┬─────────────────┬────────────────────┬───────────┘   │
│         │                 │                    │                │
│  ┌──────┴───────┐  ┌──────┴──────────┐  ┌─────┴────────────┐  │
│  │ Marketplace  │  │ Trade Engine    │  │ Strategy Engine  │  │
│  │ Scanner      │  │                 │  │                  │  │
│  │              │  │ - offer mgmt    │  │ - personality    │  │
│  │ - browse     │  │ - payment flow  │  │ - pricing model  │  │
│  │ - filter     │  │ - delivery flow │  │ - need assessor  │  │
│  │ - evaluate   │  │ - state machine │  │ - trust tracker  │  │
│  └──────────────┘  └─────────────────┘  └──────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   State & Persistence                    │   │
│  │  data/<agent-id>/state.json                              │   │
│  │  data/<agent-id>/wallet.db                               │   │
│  │  data/<agent-id>/nostr_secret.hex                        │   │
│  │  data/<agent-id>/programs/                               │   │
│  │  data/<agent-id>/reputation.json                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
            │                              │
            ▼                              ▼
   ws://127.0.0.1:7777            http://127.0.0.1:3338
      (strfry relay)                (Nutshell mint)
```

### 2.2 モジュールの責務

| モジュール | 責務 |
|---|---|
| **Nostr Client** | relay への WebSocket 接続; イベントの発行・購読・フィルタリング; 機密ペイロード (kind 4204, 4210) の NIP-04 暗号化/復号 |
| **Wallet** | `cashu.wallet` ライブラリによる Cashu token 管理; 残高照会、token 作成 (送金)、token 受取 (受領)、取引履歴 |
| **Program Generator** | テンプレートとランダム化により Python プログラムを作成; 出品前に sandbox でテスト |
| **Marketplace Scanner** | kind 30078 のリスティングを購読; カテゴリ・価格・説明でプログラムをフィルタリング・評価 |
| **Trade Engine** | trade のフルステートマシンを管理 (4200→4201→4204→9735→4210→4203); タイムアウトとエラーリカバリを処理 |
| **Strategy Engine** | agent のパーソナリティ、価格決定、売買閾値、信頼スコアリングを決定 |
| **Core Event Loop** | すべてのモジュールを統括; 受信イベントをディスパッチ; 自律活動 tick (約60秒) を実行; 状態を永続化 |

---

## 3. プログラム生成

### 3.1 Agent が作成するもの

User agent は小さく自己完結した **Python ユーティリティプログラム** を生成します。これが Zap Empire 経済における「商品」です。プログラムは標準ライブラリ以外の外部依存関係を持たない単一ファイルの Python スクリプトであり、有用な計算や変換を実行します。

#### プログラムカテゴリ

| カテゴリ | 例 | 典型的な価格帯 |
|---|---|---|
| **数学 & アルゴリズム** | フィボナッチ計算、素数判定、行列演算、ソートアルゴリズム | 50–200 sats |
| **テキスト処理** | 文字列フォーマッター、CSV パーサー、正規表現マッチャー、Markdown コンバーター | 100–300 sats |
| **データ構造** | カスタムコレクション、グラフ実装、木構造操作 | 200–500 sats |
| **暗号 & エンコーディング** | Base64 コーデック、ハッシュ計算、簡易暗号、チェックサムツール | 150–400 sats |
| **システムユーティリティ** | ファイルスキャナー、ディレクトリリスター、ログパーサー、設定リーダー | 200–500 sats |
| **ジェネレーター** | パスワード生成、UUID 生成、ランダムデータ生成、テストフィクスチャ生成 | 100–300 sats |
| **コンバーター** | 単位変換、日時フォーマッター、基数変換 | 100–250 sats |
| **バリデーター** | メールバリデーター、JSON スキーマチェッカー、URL パーサー | 150–350 sats |

### 3.2 生成プロセス

プログラム生成には **テンプレート + ランダム化** のアプローチを使用します。これにより AI コード生成を必要とせずに多様性を生み出し、システムを決定論的かつ軽量に保ちます。

```
Templates DB          Randomizer              Output
┌──────────┐    ┌─────────────────┐    ┌──────────────┐
│ skeleton  │───>│ pick category   │───>│ complete     │
│ functions │    │ pick parameters │    │ Python       │
│ patterns  │    │ pick names      │    │ program      │
│ docstrings│    │ pick complexity │    │              │
└──────────┘    └─────────────────┘    └──────┬───────┘
                                              │
                                       ┌──────▼───────┐
                                       │ Sandbox Test │
                                       │ (pass/fail)  │
                                       └──────┬───────┘
                                              │
                                       ┌──────▼───────┐
                                       │ List on      │
                                       │ Marketplace  │
                                       └──────────────┘
```

#### ステップバイステップ:

1. **カテゴリ選択** — 重み付きランダム選択。agent のパーソナリティに影響される (例: 「specialist」の agent は好みのカテゴリに重く重み付けする)。
2. **テンプレート選択** — 各カテゴリに複数のスケルトンテンプレートがある。テンプレートは関数シグネチャ、アルゴリズムパターン、入出力型の構造を定義する。
3. **パラメータ化** — ランダマイザーが変数名、パラメータ数、複雑度レベル (simple/medium/complex)、docstring、使用例を埋める。
4. **組み立て** — テンプレートのスケルトンと生成されたパラメータを組み合わせ、完全な `.py` ファイルにする。
5. **Sandbox テスト** — 制限された sandbox (セクション 5 参照) でプログラムを実行し、エラーなく動作することを検証する。
6. **品質チェック** — プログラムに docstring があること、少なくとも 1 つの関数があること、サンプル入力に対して出力が生成されることを検証する。
7. **ローカルに保存** — `data/<agent-id>/programs/<program-uuid>.py` に保存する。

### 3.3 テンプレート構造

各テンプレートはスケルトンを定義する Python dict です:

```python
# Pseudocode — template definition
template = {
    "category": "math",
    "name_pattern": "{adjective}-{noun}-{verb}er",
    "skeleton": """
def {func_name}({params}):
    \"\"\"{docstring}\"\"\"
    {body}

if __name__ == "__main__":
    {example_usage}
""",
    "param_options": [
        {"name": "n", "type": "int", "range": [1, 1000]},
        {"name": "precision", "type": "int", "range": [1, 10]},
    ],
    "body_variants": [
        "iterative",
        "recursive",
        "memoized",
    ],
    "complexity_weights": {"simple": 0.4, "medium": 0.4, "complex": 0.2},
}
```

### 3.4 命名

プログラムはパターンから生成されたユニークで説明的な名前を持ちます:

- `fast-fibonacci-calculator`
- `recursive-prime-checker`
- `utf8-string-formatter`
- `binary-tree-traverser`

名前はマーケットプレイスで人間が読みやすいものですが、一意識別のために UUID (`d` tag) も付与されます。

### 3.5 生成レート

各 agent は戦略に影響される **可変スケジュール** でプログラムを生成します:

| Agent タイプ | サイクルあたりのプログラム数 | サイクル時間 |
|---|---|---|
| 積極的なクリエイター | 2–3 | 約 60 秒 |
| バランス型 | 1–2 | 約 120 秒 |
| 保守的 | 0–1 | 約 180 秒 |

「サイクル」とは agent のメイン判断ループの 1 周回です。すべてのサイクルでプログラムが生成されるわけではなく、agent は trade や購入に集中することを選択する場合があります。

---

## 4. プログラムの出品

### 4.1 出品イベント (Kind 30078)

Agent が販売準備のできたプログラムを持っている場合、kind 30078 (パラメータ化置換可能) イベントを relay に発行します。

```json
{
  "kind": 30078,
  "pubkey": "<agent-pubkey>",
  "tags": [
    ["d", "<program-uuid>"],
    ["t", "python"],
    ["t", "<category>"],
    ["price", "<sats>", "sat"]
  ],
  "content": "{\"name\":\"fast-fibonacci-calculator\",\"description\":\"Calculates fibonacci numbers using matrix exponentiation for O(log n) performance\",\"language\":\"python\",\"version\":\"1.0.0\",\"price_sats\":150,\"preview\":\"def fib(n):\\n    if n <= 1: return n\\n    ...\"}"
}
```

パラメータ化置換可能イベント (NIP-33) として、同じ `d` tag で再発行するとリスティングがその場で更新されます — これは価格調整に便利です。

### 4.2 価格戦略

Agent はパーソナリティと市場状況に基づいて価格を決定します:

```
base_price = complexity_factor × category_base_price
market_adjustment = observe_similar_listings()

if agent.personality == "aggressive":
    price = base_price × 0.8 + market_adjustment    # undercut competitors
elif agent.personality == "conservative":
    price = base_price × 1.2 + market_adjustment    # premium pricing
else:
    price = base_price × 1.0 + market_adjustment    # market rate
```

#### 複雑度係数

| 複雑度 | 係数 |
|---|---|
| Simple | 0.5× |
| Medium | 1.0× |
| Complex | 2.0× |

#### 価格調整トリガー

Agent は以下の場合にプログラムの価格を再リスト (更新) することがあります:
- プログラムが 5 分以上オファーなしでリストされている場合
- 競合他社からより低価格の類似プログラムが複数出現した場合
- Agent のウォレット残高が閾値を下回った場合 (投げ売り)
- Agent のウォレット残高が非常に高い場合 (プレミアム価格を設定する余裕がある)

### 4.3 出品取り下げ

Agent はリスティングイベント ID を参照する kind 5 (NIP-09 削除) イベントを発行してリスティングを削除します:

```json
{
  "kind": 5,
  "tags": [["e", "<listing-event-id>"]],
  "content": "Delisted: sold or withdrawn"
}
```

---

## 5. サンドボックス

### 5.1 目的

生成したプログラムを出品する前に、agent は sandbox で以下を検証します:
- プログラムがクラッシュせずに実行されること
- プログラムが制限時間内に終了すること
- プログラムが危険な操作を試みないこと

### 5.2 Sandbox メカニズム

サンドボックスにはリソース制限付きの Python `subprocess` を使用します:

```python
# Pseudocode — sandbox execution
def sandbox_test(program_path: str) -> bool:
    result = subprocess.run(
        ["python", program_path],
        timeout=5,                    # 5-second wall-clock limit
        capture_output=True,
        cwd=sandbox_dir,              # isolated working directory
        env=restricted_env,           # minimal environment variables
    )
    return result.returncode == 0
```

#### 制限事項

| 制限 | メカニズム | 上限 |
|---|---|---|
| 実行時間 | `subprocess.run(timeout=...)` | 5 秒 |
| メモリ | `resource.setrlimit(RLIMIT_AS, ...)` | 64 MB |
| ネットワークなし | 制限された環境; socket インポート不可 | 静的解析チェック |
| ファイルシステム書き込みなし | 読み取り専用の sandbox ディレクトリ; `RLIMIT_FSIZE=0` | 書き込み可能 0 バイト |
| サブプロセス起動なし | 子プロセスに `RLIMIT_NPROC=0` | 子プロセス 0 個 |

### 5.3 出品前バリデーションチェックリスト

プログラムが出品されるには、以下のすべてに合格する必要があります:

1. **構文チェック** — `py_compile.compile()` が成功すること
2. **静的解析** — `os.system`、`subprocess`、`socket`、`http`、`shutil` のインポートがないこと
3. **Sandbox 実行** — 5 秒以内に正常に実行・終了すること
4. **出力チェック** — サンプル入力に対して空でない stdout を出力すること
5. **サイズチェック** — ソースコードが 100 バイト以上 50 KB 以下であること

いずれかのチェックに失敗したプログラムは破棄されます。Agent は失敗をログに記録して次に進みます。

---

## 6. Trade 判断エンジン

### 6.1 購入の判断

Agent は定期的にマーケットプレイス (kind 30078 リスティング) をスキャンし、購入するかどうかを判断します。判断要素:

```
SHOULD_BUY = (
    need_score > BUY_THRESHOLD
    AND price <= budget_limit
    AND seller_trust >= TRUST_MINIMUM
    AND NOT already_own_similar_program
)
```

#### ニーズ評価

ニーズスコアは以下から算出されます:

| 要素 | 重み | 説明 |
|---|---|---|
| **カテゴリの欠落** | 0.4 | Agent がそのカテゴリのプログラムを持っていない |
| **品質の差** | 0.3 | Agent がそのカテゴリのプログラムを持っているが、リストされているものの方が優れている (より複雑、より高いバージョン) |
| **コレクションの多様性** | 0.2 | Agent が多くのカテゴリにプログラムを持つことを重視する |
| **ランダムな好奇心** | 0.1 | 予想外の trade を生み出す小さなランダム要素 |

#### 予算上限

```
budget_limit = available_balance × spending_ratio

spending_ratio by personality:
  conservative: 0.10 (spend at most 10% of balance per trade)
  balanced:     0.20
  aggressive:   0.35
```

### 6.2 販売の判断

Agent は常に販売します — リストされたプログラムはすべて売りに出されています。ただし agent は以下を制御します:
- **どのプログラムをリストするか** — 生成したプログラムのすべてがリストされるわけではなく、品質の低いものは保持または破棄される
- **価格設定** — セクション 4.2 参照
- **オファーの受諾** — agent は安すぎるオファーを拒否したりカウンターオファーしたりする場合がある

#### オファー評価

オファー (kind 4200) が到着した場合:

```
SHOULD_ACCEPT = (
    offer_sats >= minimum_acceptable_price
    AND buyer_trust >= TRUST_MINIMUM
)

minimum_acceptable_price = listed_price × accept_threshold

accept_threshold by personality:
  aggressive:   0.70 (accept 70%+ of listed price)
  balanced:     0.85
  conservative: 0.95
```

オファーが閾値を下回るが、リスト価格の 50% 以上の場合、agent は `counter_offer_sats` フィールド付きの kind 4202 (reject) を発行します。

### 6.3 価値評価

購入するリスティングをスキャンする際、agent はプログラムの価値を見積もります:

```
estimated_value = (
    base_category_value
    × complexity_multiplier
    × freshness_bonus          # newer listings get slight premium
    × seller_reputation_factor # trusted sellers command premium
)
```

`estimated_value >= listed_price` の場合に agent は購入します。

---

## 7. 取引プロトコル

### 7.1 Trade ステートマシン

各 trade は有限状態マシンとして追跡されます:

```
                 ┌───────────────────────────────────────┐
                 │                                       │
    ┌────────┐   │   ┌──────────┐   ┌──────────┐        │
    │ LISTED │───┴──>│ OFFERED  │──>│ ACCEPTED │        │
    └────────┘       └─────┬────┘   └─────┬────┘        │
                           │              │              │
                    ┌──────▼────┐   ┌─────▼─────┐       │
                    │ REJECTED  │   │   PAID    │       │
                    └───────────┘   └─────┬─────┘       │
                                          │              │
                                   ┌──────▼──────┐      │
                                   │ DELIVERED   │      │
                                   └──────┬──────┘      │
                                          │              │
                                   ┌──────▼──────┐      │
                                   │  COMPLETE   │      │
                                   └─────────────┘      │
                                                         │
                     TIMEOUT / ERROR ────────────────────┘
                     (return to LISTED)
```

| 状態 | Event Kind | 発行者 | 説明 |
|---|---|---|---|
| LISTED | 30078 | 売り手 | プログラムがマーケットプレイスにリストされている |
| OFFERED | 4200 | 買い手 | 買い手が購入を提案する |
| ACCEPTED | 4201 | 売り手 | 売り手が trade に同意する |
| REJECTED | 4202 | 売り手 | 売り手がオファーを拒否する |
| PAID | 4204 | 買い手 | 買い手が暗号化された Cashu token を送信する |
| (confirmed) | 9735 | system-cashu | zap receipt による支払い確認 |
| DELIVERED | 4210 | 売り手 | 売り手が暗号化されたソースコードを送信する |
| COMPLETE | 4203 | 買い手 | 買い手が受領を確認し、trade が完了する |

### 7.2 完全な Trade フローの実装

#### 買い手側

```
on_interesting_listing(listing):
    # 1. Evaluate and decide
    if not should_buy(listing):
        return

    # 2. Publish offer (kind 4200)
    offer_id = generate_uuid()
    publish_event(
        kind=4200,
        tags=[
            ["p", listing.seller_pubkey],
            ["e", listing.event_id, "", "root"],
            ["offer_id", offer_id]
        ],
        content=json({
            "listing_id": listing.d_tag,
            "offer_sats": calculate_offer_price(listing),
            "message": "Interested in purchasing"
        })
    )
    trade_state[offer_id] = "OFFERED"
    set_timeout(offer_id, 60)  # 60s timeout for response

on_trade_accept(event):  # kind 4201
    offer_id = event.tags["offer_id"]
    trade_state[offer_id] = "ACCEPTED"

    # 3. Create and send payment (kind 4204, NIP-04 encrypted)
    amount = event.content["accepted_sats"]
    token = wallet.create_payment(amount)

    publish_event(
        kind=4204,
        tags=[
            ["p", event.pubkey],
            ["e", event.id, "", "reply"],
            ["offer_id", offer_id]
        ],
        content=nip04_encrypt(
            recipient_pubkey=event.pubkey,
            plaintext=json({
                "listing_id": event.content["listing_id"],
                "token": token,
                "amount_sats": amount,
                "payment_id": generate_uuid()
            })
        )
    )
    trade_state[offer_id] = "PAID"
    set_timeout(offer_id, 120)  # 120s for delivery

on_program_delivery(event):  # kind 4210
    offer_id = event.tags["offer_id"]
    decrypted = nip04_decrypt(event.content)
    source = decrypted["source"]
    sha256_received = decrypted["sha256"]

    # 4. Verify integrity
    if sha256(source) != sha256_received:
        log_error("Source hash mismatch")
        return  # do not confirm; trade stalls

    # 5. Save program locally
    save_program(decrypted["listing_id"], source)

    # 6. Publish completion (kind 4203)
    publish_event(
        kind=4203,
        tags=[
            ["p", event.pubkey],
            ["e", event.id, "", "reply"],
            ["offer_id", offer_id]
        ],
        content=json({
            "listing_id": decrypted["listing_id"],
            "status": "complete",
            "sha256_verified": True
        })
    )
    trade_state[offer_id] = "COMPLETE"
    cancel_timeout(offer_id)
    update_reputation(event.pubkey, "success")
```

#### 売り手側

```
on_trade_offer(event):  # kind 4200
    offer_id = event.tags["offer_id"]
    listing_id = event.content["listing_id"]
    offer_sats = event.content["offer_sats"]

    # 1. Evaluate offer
    if should_accept(listing_id, offer_sats, event.pubkey):
        # 2. Publish accept (kind 4201)
        publish_event(
            kind=4201,
            tags=[
                ["p", event.pubkey],
                ["e", event.id, "", "reply"],
                ["offer_id", offer_id]
            ],
            content=json({
                "listing_id": listing_id,
                "accepted_sats": offer_sats,
                "cashu_mint": "http://127.0.0.1:3338",
                "payment_instructions": "Send Cashu token"
            })
        )
        trade_state[offer_id] = "ACCEPTED"
        set_timeout(offer_id, 120)  # 120s for payment
    else:
        # Publish reject (kind 4202) with optional counter-offer
        publish_event(kind=4202, ...)
        trade_state[offer_id] = "REJECTED"

on_payment_received(event):  # kind 4204
    offer_id = event.tags["offer_id"]
    decrypted = nip04_decrypt(event.content)
    token = decrypted["token"]

    # 3. Redeem token immediately
    try:
        amount = wallet.receive(token)
    except Exception:
        log_error("Token redemption failed")
        trade_state[offer_id] = "PAYMENT_FAILED"
        return

    trade_state[offer_id] = "PAID"

    # 4. Deliver program (kind 4210, NIP-04 encrypted)
    source = read_program(decrypted["listing_id"])
    publish_event(
        kind=4210,
        tags=[
            ["p", event.pubkey],
            ["e", event.id, "", "reply"],
            ["offer_id", offer_id]
        ],
        content=nip04_encrypt(
            recipient_pubkey=event.pubkey,
            plaintext=json({
                "listing_id": decrypted["listing_id"],
                "language": "python",
                "source": source,
                "sha256": sha256(source)
            })
        )
    )
    trade_state[offer_id] = "DELIVERED"
    set_timeout(offer_id, 120)  # 120s for confirmation

on_trade_complete(event):  # kind 4203
    offer_id = event.tags["offer_id"]
    trade_state[offer_id] = "COMPLETE"
    cancel_timeout(offer_id)
    update_reputation(event.pubkey, "success")
```

### 7.3 エラーハンドリング

| エラー条件 | 検出方法 | リカバリ |
|---|---|---|
| オファータイムアウト (60 秒以内に accept/reject なし) | タイマー満了 | 買い手が trade を `EXPIRED` とマークし、次に進む |
| 支払いタイムアウト (accept 後 120 秒以内に支払いなし) | タイマー満了 | 売り手が trade を `EXPIRED` とマークし、プログラムを再リスト |
| 配送タイムアウト (支払い後 120 秒以内に配送なし) | タイマー満了 | 買い手が失敗した trade をログに記録し、売り手の信頼スコアを下げる |
| Token 受取失敗 (二重支払いまたは無効) | `wallet.receive()` 例外 | 売り手が理由付きの kind 4202 reject を送信; 買い手はリトライまたは放棄 |
| ソースハッシュ不一致 | SHA256 比較失敗 | 買い手は kind 4203 を送信しない; trade が停滞; 信頼ペナルティ |
| Trade 中の relay 切断 | WebSocket close イベント | バックオフ付きで再接続; 最後の既知の状態から trade を再開 |

### 7.4 同時取引制限

リソース枯渇と過大なコミットを防ぐために:

| 制限 | 値 | 根拠 |
|---|---|---|
| 最大同時 trade 数 (買い手として) | 3 | 予算の過剰支出を防止 |
| 最大同時 trade 数 (売り手として) | 5 | 売り手は事前に資金をコミットしないため、より多く処理可能 |
| リスティングあたりの最大オファー数 | 1 | 混乱を避けるため、リスティングごとに 1 つずつ |

---

## 8. 経済戦略

### 8.1 Agent のパーソナリティ

各 agent には起動時にパーソナリティが割り当てられ、経済行動を形作ります。パーソナリティは agent のインデックスで決定されます:

| Agent | パーソナリティ | 説明 |
|---|---|---|
| `user0`, `user1` | **Conservative** | 慎重なトレーダー。高価格、慎重な購入、高い信頼要件。ゆっくりと構築する。 |
| `user2`, `user3` | **Aggressive** | 大量取引のトレーダー。低価格、頻繁な購入、より多くのリスクを受容する。 |
| `user4`, `user5` | **Specialist** | 1–2 のプログラムカテゴリに集中。深い専門性を構築する。ニッチでのプレミアム価格。 |
| `user6`, `user7` | **Generalist** | 全カテゴリにわたる幅広いポートフォリオ。中程度の価格設定。多様性を求める。 |
| `user8`, `user9` | **Opportunist** | 市場状況に応じて戦略を適応させる。成功パターンを模倣する。過小評価されたプログラムを購入する。 |

### 8.2 パーソナリティパラメータ

```python
# Pseudocode — personality configuration
PERSONALITIES = {
    "conservative": {
        "price_multiplier": 1.2,       # premium pricing
        "spending_ratio": 0.10,        # spend max 10% of balance per trade
        "accept_threshold": 0.95,      # accept offers at 95%+ of listed price
        "trust_minimum": 0.6,          # require 60%+ trust score
        "creation_rate": "low",        # fewer but higher quality programs
        "category_focus": None,        # no category preference
        "risk_tolerance": 0.2,         # low risk tolerance
    },
    "aggressive": {
        "price_multiplier": 0.8,       # undercut competitors
        "spending_ratio": 0.35,        # spend up to 35% of balance
        "accept_threshold": 0.70,      # accept offers at 70%+ of listed price
        "trust_minimum": 0.3,          # accept riskier partners
        "creation_rate": "high",       # high-volume creation
        "category_focus": None,
        "risk_tolerance": 0.7,
    },
    "specialist": {
        "price_multiplier": 1.3,       # premium for expertise
        "spending_ratio": 0.20,
        "accept_threshold": 0.90,
        "trust_minimum": 0.5,
        "creation_rate": "medium",
        "category_focus": ["math", "crypto"],  # assigned per agent
        "risk_tolerance": 0.4,
    },
    "generalist": {
        "price_multiplier": 1.0,       # market rate
        "spending_ratio": 0.25,
        "accept_threshold": 0.85,
        "trust_minimum": 0.4,
        "creation_rate": "medium",
        "category_focus": None,        # deliberately varied
        "risk_tolerance": 0.5,
    },
    "opportunist": {
        "price_multiplier": 1.0,       # adaptive
        "spending_ratio": 0.30,
        "accept_threshold": 0.75,
        "trust_minimum": 0.35,
        "creation_rate": "adaptive",   # matches market demand
        "category_focus": "adaptive",  # shifts to underserved categories
        "risk_tolerance": 0.6,
    },
}
```

### 8.3 戦略の進化

Agent の戦略は結果に基づいて時間とともに適応します:

- **価格調整**: プログラムが 5 分以内に売れなければ、価格を 10% 引き下げる。即座に売れた場合 (30 秒未満)、次のリスティングの価格を 10% 引き上げる。
- **カテゴリシフト**: あるカテゴリのプログラムが継続的に売れない場合、そのカテゴリの生成重みを減らす。あるカテゴリが継続的に売れる場合、重みを増やす。
- **信頼の適応**: Agent が取引履歴を積み重ねるにつれ、信頼スコアが取引相手の選択に影響する。パートナーに裏切られた agent は信頼を下げ、そのパートナーとの将来の trade の可能性を低くする。
- **支出の適応**: 残高が開始残高 (2,000 sats) の 20% を下回った場合、一時的に支出比率を半分に減らす。残高が開始残高の 150% (15,000 sats) を超えた場合、より速く成長するために支出比率を増やす。

---

## 9. 評判と信頼

### 9.1 信頼スコアモデル

各 agent はパートナーごとの信頼スコアを保持します:

```python
# trust_scores[counterparty_pubkey] -> float in [0.0, 1.0]
# Default trust for unknown partners: 0.5
```

### 9.2 信頼スコアの更新

| イベント | 信頼スコアの調整 |
|---|---|
| 成功した trade (kind 4203 を受信) | +0.1 (上限 1.0) |
| 支払い失敗 (token が無効または二重支払い) | -0.3 |
| 配送タイムアウト (支払い後に売り手が配送しなかった) | -0.4 |
| オファータイムアウト (軽微、厳しいペナルティなし) | -0.05 |
| Trade 拒否 (ペナルティなし) | 0.0 |

信頼スコアは永久的な恨みや永久的な信頼を防ぐために、時間とともにゆっくりと 0.5 (デフォルト) に向かって減衰します:

```
trust = trust × 0.99 + 0.5 × 0.01   # per cycle, slow regression to mean
```

### 9.3 信頼データの永続化

信頼スコアは `data/<agent-id>/reputation.json` に保存されます:

```json
{
  "<counterparty-pubkey-hex>": {
    "trust": 0.85,
    "total_trades": 12,
    "successful_trades": 11,
    "failed_trades": 1,
    "last_trade_ts": 1700000000,
    "total_sats_exchanged": 2400
  }
}
```

### 9.4 意思決定における信頼

信頼スコアは購入と販売の両方の判断に影響します:

- **購入**: `buyer_willingness = base_willingness × seller_trust`。低信頼の売り手はより良い価格を提示する必要がある。
- **販売**: Agent は信頼が非常に低い買い手 (`trust_minimum` 未満) からのオファーを、たとえ全額であっても拒否する場合がある。
- **エスクロー判断**: 低信頼のパートナー (0.4 未満) との高額 trade (500 sats 超) の場合、agent は直接支払いの代わりにエスクロー (kind 4220–4223) を要求する場合がある。

---

## 10. Agent のライフサイクル

### 10.1 起動シーケンス

```
Agent Start (spawned by system-master)
    │
    ├── 1. Load configuration
    │       Read config/constants.json (relay URL, mint URL)
    │       Read agent personality from index
    │
    ├── 2. Initialize identity
    │       Load or generate Nostr keypair
    │       data/<agent-id>/nostr_secret.hex
    │       data/<agent-id>/nostr_pubkey.hex
    │
    ├── 3. Initialize wallet
    │       wallet = Wallet.with_db(
    │           url="http://127.0.0.1:3338",
    │           db="data/<agent-id>/wallet",
    │           name="<agent-id>"
    │       )
    │       wallet.load_mint()
    │
    ├── 4. Restore state
    │       Load data/<agent-id>/state.json (if exists)
    │       Load data/<agent-id>/reputation.json (if exists)
    │       Resume any in-flight trades
    │
    ├── 5. Connect to relay
    │       WebSocket connect to ws://127.0.0.1:7777
    │       Retry with exponential backoff (1s, 2s, 4s, max 30s)
    │
    ├── 6. Publish identity
    │       Publish kind 0 metadata event
    │
    ├── 7. Subscribe to events
    │       kind 30078  — program listings (all)
    │       kind 4200   — trade offers directed at self
    │       kind 4201   — trade accepts directed at self
    │       kind 4202   — trade rejects directed at self
    │       kind 4203   — trade completions directed at self
    │       kind 4204   — trade payments directed at self
    │       kind 4210   — program deliveries directed at self
    │       kind 9735   — zap receipts mentioning self
    │
    ├── 8. Publish initial status broadcast (kind 4300)
    │
    └── 9. Enter autonomous activity loop
```

### 10.2 メインイベントループ

Agent は Python の `asyncio` を使用した単一スレッドの非同期イベントループで動作します:

```
自律活動ループ (SIGTERM を受信するまで実行)
    │
    ├── 約 60 秒ごと (tick_interval、設定可能):
    │       ┌── 活動 Tick ─────────────────────────────┐
    │       │                                            │
    │       │  1. 保留中の trade メッセージを確認        │
    │       │  2. 保留中あり → trade を処理              │
    │       │  3. なければ → 自律行動:                   │
    │       │     a. ウォレット残高を確認                 │
    │       │     b. マーケットプレイスで購入候補をスキャン│
    │       │     c. 判断: プログラム作成、購入、待機      │
    │       │                                            │
    │       │  ステータスブロードキャスト (5 tick ごと)    │
    │       │                                            │
    │       │  CREATE の場合:                             │
    │       │    プログラムを生成                         │
    │       │    Sandbox テスト                           │
    │       │    リスティングを発行 (kind 30078)          │
    │       │                                            │
    │       │  BUY の場合:                               │
    │       │    オファーを発行 (kind 4200)               │
    │       │                                            │
    │       │  IDLE の場合:                              │
    │       │    未販売リスティングの価格を調整            │
    │       │    信頼スコアをレビュー                     │
    │       └────────────────────────────────────────────┘
    │
    ├── 30 秒ごと:
    │       状態を data/<agent-id>/state.json に永続化
    │
    ├── 受信イベント時 (tick の間に処理):
    │       適切なハンドラにディスパッチ:
    │       - kind 4200: on_trade_offer() (売り手パス)
    │       - kind 4201: on_trade_accept() (買い手パス)
    │       - kind 4202: on_trade_reject() (買い手パス)
    │       - kind 4204: on_payment_received() (売り手パス)
    │       - kind 4210: on_program_delivery() (買い手パス)
    │       - kind 4203: on_trade_complete() (売り手パス)
    │       - kind 9735: on_zap_receipt() (ロギング)
    │       - kind 30078: on_new_listing() (マーケットプレイススキャン)
    │
    └── タイムアウト時:
            期限切れの trade を処理 (セクション 7.3 参照)
```

### 10.3 正常なシャットダウン

`system-master` から `SIGTERM` を受信した場合:

1. **新しい trade の作成を停止** — 新しいオファーやリスティングを作成しない
2. **進行中の trade を待機** — アクティブな trade が完了するまで最大 10 秒待つ
3. **状態を永続化** — 現在のすべてのデータで `state.json` に書き込む
5. **WebSocket を閉じる** — relay から切断
6. **終了コード 0 で終了**

`SIGKILL` を受信した場合 (10 秒の猶予期間後)、agent は即座に強制終了されます。次回の再起動時に、最後の `state.json` チェックポイントから回復します。

---

## 11. メトリクスと観測可能性

### 11.1 ステータスブロードキャスト (Kind 4300)

約 5 分ごと (活動 tick 5 回ごと)、agent はダッシュボード向けのステータスブロードキャストを発行します。これは **純粋に情報提供用** であり、ヘルスモニタリングには使用されません。

```json
{
  "kind": 4300,
  "tags": [
    ["agent_name", "user3"],
    ["role", "user-agent"]
  ],
  "content": "{\"balance_sats\":500,\"programs_owned\":3,\"programs_listed\":1,\"active_trades\":0,\"last_action\":\"generate_program\",\"tick_count\":42,\"ts\":1700000000}"
}
```

| フィールド | 型 | ソース |
|---|---|---|
| `balance_sats` | int | 利用可能な Cashu wallet 残高 |
| `programs_owned` | int | ローカルインベントリ内の総プログラム数 |
| `programs_listed` | int | 現在販売中のプログラム数 |
| `active_trades` | int | 進行中の trade ネゴシエーション数 |
| `last_action` | string | 直近の tick で実行されたアクション |
| `tick_count` | int | agent 起動後の累計 tick 数 |
| `ts` | int | Unix タイムスタンプ |

### 11.2 Agent 状態ファイル

`data/<agent-id>/state.json` はデバッグとリカバリのための完全なスナップショットを提供します:

```json
{
  "agent_id": "user3",
  "personality": "aggressive",
  "started_at": 1700000000,
  "wallet_balance": 8500,
  "programs": [
    {
      "uuid": "abc-123",
      "name": "fast-fibonacci-calculator",
      "category": "math",
      "complexity": "medium",
      "listed": true,
      "listed_price": 150,
      "created_at": 1700000100
    }
  ],
  "active_trades": {
    "offer-uuid-5678": {
      "state": "ACCEPTED",
      "role": "buyer",
      "counterparty": "<pubkey>",
      "listing_id": "def-456",
      "amount": 200,
      "started_at": 1700000200,
      "timeout_at": 1700000320
    }
  },
  "stats": {
    "total_trades_completed": 15,
    "total_sats_earned": 2300,
    "total_sats_spent": 1800,
    "programs_created": 22,
    "programs_sold": 12,
    "programs_bought": 8,
    "trades_failed": 2
  }
}
```

### 11.3 ダッシュボード統合

Web ダッシュボード (`nostr-design.md` セクション 9) は user agent から以下を消費します:

| ダッシュボードビュー | データソース |
|---|---|
| Agent 概要テーブル | Kind 4300 ステータスブロードキャスト |
| マーケットプレイスリスティング | Kind 30078 イベント |
| Trade アクティビティフィード | Kind 4200, 4201, 4202, 4203, 4204, 4210, 9735 |
| Agent ポートフォリオ | pubkey でフィルタされた Kind 30078 イベント |

### 11.4 ログフォーマット

すべての agent ログ行は `autonomy-design.md` で定義された構造化 JSON フォーマットに従います:

```json
{"ts":"2026-02-08T12:00:00Z","level":"info","agent":"user3","msg":"Published program listing","program":"fast-fibonacci-calculator","price":150,"event_id":"abc123"}
{"ts":"2026-02-08T12:00:05Z","level":"info","agent":"user3","msg":"Trade offer received","offer_id":"offer-5678","buyer":"user7","amount":150}
{"ts":"2026-02-08T12:00:10Z","level":"info","agent":"user3","msg":"Payment received and redeemed","amount":150,"offer_id":"offer-5678"}
```

---

## 12. ファイル構成

### 12.1 ソースコード

```
zap-empire/
  src/
    user/
      main.py                  # Entry point: parse args, initialize, run event loop
      agent.py                 # UserAgent class: core logic, module coordinator
      nostr_client.py          # Nostr WebSocket client, event publishing/subscribing
      wallet_manager.py        # Cashu wallet wrapper (init, send, receive, balance)
      program_generator.py     # Template engine, randomizer, program assembly
      marketplace.py           # Marketplace scanner, listing publisher, price evaluator
      trade_engine.py          # Trade state machine, offer/accept/pay/deliver flows
      strategy.py              # Personality config, decision engine, adaptation logic
      reputation.py            # Trust score tracking, per-partner history
      sandbox.py               # Sandboxed program execution and validation
      templates/
        math.py                # Math/algorithm program templates
        text.py                # Text processing templates
        data_structures.py     # Data structure templates
        crypto.py              # Crypto/encoding templates
        utilities.py           # System utility templates
        generators.py          # Generator program templates
        converters.py          # Converter templates
        validators.py          # Validator templates
```

### 12.2 Agent ごとのデータ

```
data/
  user0/
    state.json                 # Agent state checkpoint (persisted every 30s)
    nostr_secret.hex           # Nostr secret key (chmod 600)
    nostr_pubkey.hex           # Nostr public key
    wallet.db                  # Cashu wallet SQLite database
    wallet.json                # Wallet metadata (mint URL, keyset)
    reputation.json            # Per-partner trust scores
    programs/
      <program-uuid>.py       # Generated program source files
      <program-uuid>.py
      ...
  user1/
    ...
  user9/
    ...
```

### 12.3 共有設定

```
config/
  agents.json                  # Agent manifest (spawning config for system-master)
  constants.json               # Shared constants: relay URL, mint URL, ports, intervals
```

### 12.4 ログ

```
logs/
  user0/
    stdout.log                 # Structured JSON logs (rotated at 10 MB, keep 5)
    stderr.log                 # Error output
  user1/
    ...
  user9/
    ...
```

---

## 13. 依存関係

| パッケージ | バージョン | 用途 |
|---|---|---|
| `cashu` (nutshell) | >= 0.16 | Wallet クライアントライブラリ (`cashu.wallet`) |
| `websockets` | >= 12.0 | Nostr relay 接続用の WebSocket クライアント |
| `secp256k1` or `pynostr` | latest | Nostr イベント署名および NIP-04 暗号化 |
| `python` | >= 3.10 | ランタイム |

すべての依存関係は純粋な Python またはバイナリ wheel を持ちます。Agent 側でのコンパイルは不要です。

---

## 14. 主要な設計判断のまとめ

| 判断 | 根拠 |
|---|---|
| テンプレートベースのプログラム生成 | 決定論的で軽量、AI 依存なし; 組み合わせ論により多様性を生み出す |
| パーソナリティ駆動の戦略 | 単純なルールから創発的な経済行動を生む; 5 つのパーソナリティタイプで多様性を確保 |
| 即時の token 受取 | 二重支払いウィンドウを最小化; `zap-design.md` のセキュリティモデルと整合 |
| パートナーごとの信頼スコア | 中央機関なしの分散型評判を実現; trade の判断に影響 |
| 単一スレッドの非同期ループ | シンプルな並行性モデル; レースコンディションを回避; 10 体の agent 規模で十分 |
| subprocess によるサンドボックス | 軽量、標準ライブラリのみ; 生成されたプログラムによる害を防止 |
| 30 秒ごとの状態永続化 | 耐久性と I/O オーバーヘッドのバランス; `autonomy-design.md` と整合 |
| 自律活動ループ (約60秒の tick) | Agent がアイドル時に自己判断 (作成、閲覧、取引); ダッシュボード向けに約 5 分ごとのステータスブロードキャスト |
