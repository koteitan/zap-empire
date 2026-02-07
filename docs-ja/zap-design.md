# Zap Empire: Cashu Wallet & 決済システム設計

## 1. 概要

本ドキュメントは、Zap Empire の ecash 決済レイヤーを規定する。すべてのエージェント (user0 から user9、およびシステムエージェント) は Cashu wallet を保持し、決済は Nostr イベント上で送受信される bearer ecash token として行われる。ローカルの Cashu mint が WSL2 上で動作し、外部の Lightning への依存なしに token の発行と償還を提供する。

---

## 2. Cashu Mint のセットアップ

### 2.1 推奨実装: Nutshell (cashu-nutshell)

**Nutshell** (`cashu-nutshell`) を使用する。これは Cashu プロトコル (NUT 仕様) のリファレンス Python 実装であり、最も成熟しており、ドキュメントが充実しており、ローカル環境で最も簡単に動作する。

- **リポジトリ**: `https://github.com/cashubtc/nutshell`
- **言語**: Python 3.10+
- **データベース**: SQLite (ローカル、設定不要)
- **Lightning 不要**: Nutshell はテストおよびローカル利用向けに設計された "fake wallet" バックエンド (`FakeWallet`) をサポートしている。これにより、実際の Lightning ノードなしに token の発行と償還が可能になる。

### 2.2 Mint の設定

```bash
# Install
pip install cashu

# Environment variables (in .env or exported)
MINT_BACKEND_BOLT11_SAT=FakeWallet    # No real Lightning
MINT_LISTEN_HOST=127.0.0.1
MINT_LISTEN_PORT=3338
MINT_PRIVATE_KEY=<random-32-byte-hex>  # Generated once at setup
MINT_DATABASE=data/mint                # SQLite path
```

mint は `http://127.0.0.1:3338` 上で単一プロセスとして動作する。すべてのエージェントがこの単一の mint に接続する。

### 2.3 Mint の起動

```bash
# Start the mint
mint --host 127.0.0.1 --port 3338
```

mint は標準的な Cashu API エンドポイントを公開する:
- `GET  /v1/keys`       - アクティブな keyset の公開鍵
- `GET  /v1/keysets`     - 利用可能な keyset 一覧
- `POST /v1/mint/quote/bolt11`  - mint quote のリクエスト (本環境では fake)
- `POST /v1/mint/bolt11` - token の mint
- `POST /v1/swap`        - token の swap (分割/統合)
- `POST /v1/melt/quote/bolt11` - melt quote のリクエスト
- `POST /v1/melt/bolt11` - token の melt (焼却)
- `POST /v1/checkstate`  - token の使用状態の確認

### 2.4 他の選択肢を採用しない理由

| 選択肢 | 不採用の理由 |
|--------|---------------|
| **Moksha** (Rust) | ドキュメントが少なく、サポートする NUT 仕様が限定的で、スクリプト化が困難 |
| **LNbits + Cashu extension** | スタックが重く、LNbits のセットアップが必要 |
| **カスタム mint** | 不要な複雑さ。Nutshell は十分に実績がある |

---

## 3. エージェントごとの Wallet

### 3.1 Wallet アーキテクチャ

各エージェントは Nutshell のクライアントライブラリ (`cashu.wallet`) を通じて管理される、独立した **Cashu wallet** を持つ。Wallet は以下を含む固有のディレクトリで識別される:

```
data/
  agents/
    user0/
      wallet/
        wallet.db      # SQLite - proofs, keys, transaction history
        wallet.json    # Wallet metadata (mint URL, keyset ID)
      nostr_secret.hex # Nostr keypair (shared with nostr-design)
      nostr_pubkey.hex
      state.json       # Autonomy state checkpoint
    user1/
      wallet/
        ...
    ...
    user9/
      wallet/
        ...
    cashu-mint/
      wallet/
        ...
```

### 3.2 Wallet の初期化

各エージェントは初回起動時に wallet を初期化する:

```python
from cashu.wallet.wallet import Wallet

async def init_wallet(agent_id: str) -> Wallet:
    wallet = await Wallet.with_db(
        url="http://127.0.0.1:3338",
        db=f"data/agents/{agent_id}/wallet/wallet",
        name=agent_id,
    )
    await wallet.load_mint()
    return wallet
```

主な特性:
- **エージェントごとに1つの wallet**: 共有 wallet は存在しない。各エージェントが自身の proof の唯一の管理者である。
- **決定的なパス**: Wallet ディレクトリは `agent_id` から導出され、管理が容易。
- **すべての wallet が同一の mint を参照**: `http://127.0.0.1:3338`。

### 3.3 システムエージェントの Wallet

システムエージェント (relay、autonomy framework など) も手数料の受領や報酬の配布のために wallet を持つが、同じ wallet 構造に従う。

---

## 4. 初期 Token 配布

### 4.1 Minting 戦略

`FakeWallet` を使用するため、実際の Lightning invoice を支払うことなく token を mint できる。ブートストラップスクリプトが初期経済を構築する。

### 4.2 ブートストラッププロセス

```
1. Start the mint
2. For each agent (user0-user9):
   a. Create mint quote (FakeWallet auto-marks it as paid)
   b. Mint tokens for the requested amount
   c. Store proofs in agent's wallet DB
3. Log the initial distribution
```

### 4.3 初期残高

| エージェント | 初期残高 (sats) | 根拠 |
|-----------|------------------------|-----------|
| user0-user9 | 各 10,000 | 公平な競争のための平等な初期資本 |
| system-mint-admin | 100,000 | 報酬、バウンティ、緊急流動性のための準備金 |

**初期供給量合計**: 200,000 sats (ユーザー10人 x 10,000 + 100,000 準備金)

### 4.4 ブートストラップスクリプト (擬似コード)

```python
async def bootstrap_economy():
    for i in range(10):
        agent_id = f"user{i}"
        wallet = await init_wallet(agent_id)

        # Request mint quote
        quote = await wallet.request_mint(amount=10_000)

        # FakeWallet: quote is auto-paid, mint tokens immediately
        proofs = await wallet.mint(amount=10_000, quote_id=quote.quote)

        print(f"{agent_id}: minted {sum(p.amount for p in proofs)} sats")
```

### 4.5 インフレなしポリシー

ブートストラップ後、**新たな token は mint されない**。経済は閉鎖系である。Token はエージェント間の取引を通じて循環する。system-mint-admin は、明示的なバウンティ/報酬プログラム (システムイベントとして追跡) を通じてのみ準備金から流動性を注入できる。

---

## 5. Zap フロー: プログラムへの支払い

### 5.1 ハイレベルフロー

`nostr-design.md` に沿ったカスタムイベント kind を使用する。取引交渉イベント (4200-4203) はパブリックである。Cashu token の転送 (4204) およびプログラムの配信 (4210) は、bearer token とソースコードをそれぞれ含むため NIP-04 暗号化される。

```
Agent A (buyer)                    Nostr Relay                    Agent B (seller)
     |                                 |                               |
     |  1. Browse marketplace          |                               |
     |  (read kind:30078 listings)     |                               |
     |<------- program listings -------|------- publish listing ------>|
     |                                 |                               |
     |  2. Send trade offer            |                               |
     |--- kind:4200 Trade Offer ------>|-------- kind:4200 ---------> |
     |  "buy program X for 500 sats"   |                               |
     |                                 |                               |
     |                                 |  3. Seller accepts offer      |
     |<------ kind:4201 --------------|<------ kind:4201 Accept ------|
     |  "accepted, send 500 sats"      |                               |
     |                                 |                               |
     |  4. Buyer creates Cashu token   |                               |
     |  (locally, from own wallet)     |                               |
     |                                 |                               |
     |  5. Send token via Nostr        |                               |
     |--- kind:4204 Payment (enc) ---->|-------- kind:4204 ---------> |
     |  {cashu token, payment_id=abc}  |                               |
     |                                 |                               |
     |                                 |  6. Seller redeems token      |
     |                                 |  (swap at mint)               |
     |                                 |                               |
     |                                 |  6b. system-cashu publishes   |
     |                                 |      kind:9735 zap receipt    |
     |                                 |                               |
     |                                 |  7. Seller delivers program   |
     |<------ kind:4210 (enc) --------|<------ kind:4210 Delivery ----|
     |  {program source code}          |                               |
     |                                 |                               |
     |  8. Buyer confirms trade        |
     |--- kind:4203 Complete --------->|-------- kind:4203 ---------> |
```

### 5.2 ステップごとの詳細

#### ステップ 4: Token の作成 (買い手側)

買い手は自身の wallet の proof から Cashu token を作成する:

```python
async def create_payment(wallet: Wallet, amount: int) -> str:
    # Select proofs that cover the amount
    # Swap to get exact denomination if needed
    proofs = await wallet.select_to_send(amount)

    # Serialize as Cashu token (cashuA... format)
    token = await wallet.serialize_proofs(proofs)

    # Mark these proofs as pending (not yet confirmed received)
    return token  # e.g., "cashuAeyJ0b2..."
```

token は自己完結型の bearer instrument である。これを所持する者は誰でも償還できる。

#### ステップ 5: Token の転送 (kind 4204 -- NIP-04 暗号化)

Cashu token 文字列は kind 4204 (Trade Payment) イベントとして送信される。token は bearer instrument であり、傍受した者が誰でも償還できるため、`content` は NIP-04 暗号化される。

```json
{
  "kind": 4204,
  "pubkey": "<buyer_pubkey>",
  "tags": [
    ["p", "<seller_pubkey>"],
    ["e", "<accept-event-id>", "", "reply"],
    ["offer_id", "offer-uuid-5678"]
  ],
  "content": "<NIP-04 encrypted>{\"token\":\"cashuAeyJ0b2...\",\"payment_id\":\"abc123\",\"amount\":500,\"memo\":\"Purchase: program_X\"}"
}
```

売り手が token の償還に成功した後、`cashu-mint` プロセス (`system-cashu` ロールとして動作) が kind **9735** の zap receipt を公開し、relay 上で支払いを確認する。

#### ステップ 6: Token の償還 (売り手側)

```python
async def receive_payment(wallet: Wallet, token_str: str) -> int:
    # Swap token proofs for fresh proofs owned by this wallet
    amount = await wallet.receive(token_str)

    # amount > 0 means success, token was valid and not double-spent
    return amount
```

mint は proof がまだ使用されていないことを検証し、売り手に新しい proof を発行する。この処理はアトミックであり、token が既に使用済みであれば swap は失敗する。

### 5.3 Nostr イベント Kind (nostr-design.md に準拠)

| Kind | 名前 | 暗号化 | 説明 |
|------|------|------------|-------------|
| 30078 | Program Listing | なし (パブリック) | マーケットプレイスのリスト (NIP-78 アプリ固有データ) |
| 4200 | Trade Offer | なし (パブリック) | 買い手がプログラムの購入を提案 |
| 4201 | Trade Accept | なし (パブリック) | 売り手がオファーを承諾 |
| 4202 | Trade Reject | なし (パブリック) | 売り手がオファーを拒否 |
| 4204 | Trade Payment | **NIP-04 暗号化** | 買い手が Cashu token を売り手に送信 |
| 4210 | Program Delivery | **NIP-04 暗号化** | 売り手がプログラムのソースコードを買い手に送信 |
| 4203 | Trade Complete | なし (パブリック) | 買い手が受領を確認し取引を完了 |
| 9735 | Zap Receipt | なし (パブリック) | system-cashu が公開する支払い確認 |

### 5.4 Trade Payment イベントスキーマ (kind 4204)

kind 4204 イベントの NIP-04 暗号化コンテンツ:

```json
{
  "token": "cashuAeyJ0b2...",
  "payment_id": "<uuid>",
  "amount": 500,
  "memo": "Purchase: program_X"
}
```

他のすべての取引イベント (4200-4203, 4210) は `nostr-design.md` セクション 6 で定義されたスキーマに従う。決済モジュールは Cashu token の作成/償還を担当し、取引プロトコルが Nostr イベントのライフサイクルを管理する。

---

## 6. Token の額面

### 6.1 Cashu の額面戦略

Cashu はデフォルトで 2 のべき乗の額面を使用する。各 proof (token 単位) は 2 のべき乗の値を持つ:

```
1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192
```

### 6.2 実用上の影響

- **500 sats** の支払いは次の proof で表現される: `256 + 128 + 64 + 32 + 16 + 4 = 500`
- Wallet は mint の `/v1/swap` エンドポイントを通じて分割と統合を自動的に処理する。
- **額面の手動管理は不要** -- Nutshell が内部で処理する。

### 6.3 推奨される単一 Token の上限

10,000 sats の初期残高と想定される取引規模に対して:

| 取引種別 | 想定範囲 |
|-----------------|----------------|
| シンプルなユーティリティプログラム | 50 - 200 sats |
| 複雑なプログラム | 200 - 2,000 sats |
| プレミアム/レアプログラム | 2,000 - 5,000 sats |
| バウンティ報酬 | 500 - 5,000 sats |

8,192 を超える単一の額面は不要である。

---

## 7. 不正防止と二重支払い防止

### 7.1 Cashu の組み込み保護

Cashu は mint を通じて二重支払いを本質的に防止する:

1. **すべての proof は一意の secret を持つ**: proof が償還 (swap) されると、mint はその secret を「使用済み」として記録する。
2. **受信時の swap**: Agent B が Agent A から token を受信すると、Agent B は即座に mint で新しい proof に swap する。Agent A が同じ token を他の場所で既に使用していた場合、swap は失敗する。
3. **アトミック swap**: mint の swap 操作はアトミックであり、swap 内のすべての proof が有効かつ未使用であるか、操作全体が失敗するかのどちらかである。

### 7.2 追加のローカルセーフガード

すべてのエージェントがローカル環境を共有するため、以下を追加する:

#### 7.2.1 即時償還ポリシー

エージェントは受信した token を (受信ハンドラ内で) **即座に**償還しなければならない。他のエージェントからの未償還 token を保持してはならない。これにより二重支払い試行のウィンドウを最小化する。

```python
async def on_payment_received(message):
    token = message["token"]
    try:
        amount = await wallet.receive(token)  # Swap immediately
        await send_delivery(message["payment_id"])
    except Exception as e:
        await send_error(message["payment_id"], "Payment failed: token invalid or already spent")
```

#### 7.2.2 Pending Proof の追跡

買い手は送信した proof をローカルの wallet DB で「pending」としてマークする。売り手が受領を確認すると、proof は買い手の wallet から削除される。売り手が失敗を報告した場合、買い手は proof の回収を試みることができる (まだ使用されていない場合)。

#### 7.2.3 トランザクションログ

すべての決済イベントは以下の情報とともに記録される:
- タイムスタンプ
- 送信者/受信者のエージェント ID
- 金額
- Payment ID
- Token hash (プライバシーのため token 全体ではない)
- ステータス: `pending`, `confirmed`, `failed`

### 7.3 脅威モデル (ローカル環境)

| 脅威 | 対策 |
|--------|-----------|
| エージェントが同じ token を 2 人の売り手に送信 | Mint が 2 回目の swap を拒否 (二重支払い防止) |
| エージェントが支払い成功にもかかわらず失敗と主張 | Nostr 上のトランザクションレシートが証拠となる |
| エージェントが自身の wallet DB を改ざん | Mint が信頼の源泉であり、偽造された proof は検証を通過しない |
| Mint 運営者の不正 | ローカル環境では単一運営者リスクを許容。mint は信頼されたシステムコンポーネントである |

---

## 8. 会計とトランザクション履歴

### 8.1 エージェントごとの台帳

各 wallet の SQLite データベースはローカルのトランザクション台帳を管理する:

```sql
-- Automatically managed by Nutshell
CREATE TABLE proofs (
    id TEXT PRIMARY KEY,
    amount INTEGER,
    secret TEXT,
    C TEXT,           -- blinded signature
    keyset_id TEXT,
    reserved BOOLEAN, -- marked for pending send
    send_id TEXT,
    time_reserved TIMESTAMP
);

-- Custom extension for Zap Empire
CREATE TABLE zap_transactions (
    id TEXT PRIMARY KEY,          -- payment_id (UUID)
    timestamp DATETIME,
    direction TEXT,               -- 'incoming' or 'outgoing'
    counterparty TEXT,            -- agent ID
    amount INTEGER,
    memo TEXT,
    program_id TEXT,              -- if payment is for a program
    token_hash TEXT,              -- SHA256 of the token string
    status TEXT,                  -- 'pending', 'confirmed', 'failed'
    nostr_event_id TEXT           -- reference to the Nostr event
);
```

### 8.2 残高照会

```python
async def get_balance(wallet: Wallet) -> dict:
    balance = wallet.available_balance  # Sum of unspent, unreserved proofs
    pending = wallet.balance - wallet.available_balance  # Reserved proofs
    return {
        "available": balance,
        "pending_outgoing": pending,
        "total": wallet.balance,
    }
```

### 8.3 グローバル会計 (システムレベル)

システム会計エージェント (または mint admin) はグローバル経済を検証できる:

```python
async def audit_economy():
    total_minted = await mint.get_total_minted()
    total_burned = await mint.get_total_burned()
    circulating = total_minted - total_burned

    # Sum all agent balances
    agent_sum = sum(await get_balance(w) for w in all_wallets)

    # These should match (within rounding of pending transactions)
    assert circulating == agent_sum
```

### 8.4 パブリックトランザクションレシート

取引確認には 2 つの補完的なイベント kind を使用する:

1. **Kind 9735 (Zap Receipt)**: `cashu-mint` プロセス (`system-cashu` ロール) が Cashu token の swap 確認後に公開する。これが支払い証明となる。完全なイベントスキーマは `nostr-design.md` セクション 6.7 を参照。

2. **Kind 4203 (Trade Complete)**: 買い手が配信されたプログラムを受領・検証した後に公開する。これにより取引ライフサイクルが完了する。完全なイベントスキーマは `nostr-design.md` セクション 6.6 を参照。

これら 2 つのイベントが合わさることで、パブリックな監査証跡が形成される: kind 9735 は支払いが行われたことを証明し、kind 4203 は買い手が配信を確認したことを証明する。

---

## 9. Escrow メカニズム

### 9.1 Escrow の概要

高額な取引のために、オプションの escrow メカニズムにより、プログラムが配信・検証された場合にのみ買い手が支払うことを保証する。

### 9.2 Escrow モジュール (cashu-mint 内)

Escrow は `cashu-mint` プロセス内のモジュールとして実装され、独立したエージェントではない。`cashu-mint` プロセス (`system-cashu` としても動作) は mint の swap/redeem API に直接アクセスできるため、escrow ロジックの自然な配置場所である。取引中、専用の escrow wallet に token を保持する:

```
Buyer                  cashu-mint (escrow)        Seller
  |                        |                        |
  |  1. Lock payment       |                        |
  |--- cashu token ------->|                        |
  |                        |  (redeems & holds)     |
  |                        |                        |
  |  2. Notify seller      |                        |
  |                        |--- "payment locked" -->|
  |                        |                        |
  |                        |  3. Deliver program    |
  |<------- program -------|<--- program + proof ---|
  |                        |                        |
  |  4. Buyer confirms     |                        |
  |--- "confirm" --------->|                        |
  |                        |                        |
  |                        |  5. Release payment    |
  |                        |--- cashu token ------->|
  |                        |                        |
```

### 9.3 Escrow フローの詳細

#### ステップ 1: 買い手が支払いをロック

```json
{
  "type": "escrow_lock",
  "payment_id": "abc123",
  "token": "cashuA...",
  "amount": 500,
  "seller": "<seller_pubkey>",
  "program_id": "<event_id>",
  "timeout_minutes": 60
}
```

escrow モジュールは token を**即座に償還**する (cashu-mint の escrow wallet 内の新しい proof に swap)。これにより資金が実在し、ロックされていることが保証される。

#### ステップ 2-3: 売り手が配信

売り手がプログラムを買い手に送信する。買い手はそれを検査できる。

#### ステップ 4: 買い手が確認または異議申立て

- **確認**: 買い手が escrow エージェントに `{"type": "escrow_release", "payment_id": "abc123"}` を送信する。
- **異議申立て**: 買い手が `{"type": "escrow_dispute", "payment_id": "abc123", "reason": "..."}` を送信する。紛争解決は cashu-mint の運営者が処理する (現時点では手動)。

#### ステップ 5: リリース

escrow モジュールは保持している proof から該当金額の新しい token を作成し、売り手に送信する。

### 9.4 タイムアウト保護

買い手がタイムアウト (デフォルト: 60 分) 内に確認も異議申立てもしない場合、escrow モジュールは支払いを売り手に**自動的にリリース**する。これにより買い手が売り手の資金を無期限にロックすることを防止する。

### 9.5 Escrow 手数料

escrow モジュールは支払いから小額の手数料 (例: 1% または最低 1 sat) を差し引く:

```
Buyer pays: 500 sats
Escrow fee: 5 sats (1%)
Seller receives: 495 sats
```

### 9.6 Escrow の利用場面

| シナリオ | Escrow を使用するか |
|----------|---------|
| 少額の購入 (< 100 sats) | いいえ -- 直接支払い |
| 未知のエージェントとの初回取引 | はい -- 推奨 |
| 信頼済みエージェントとのリピート取引 | 任意 |
| 高額の購入 (> 1000 sats) | はい -- 強く推奨 |

Escrow は常にオプトインである。買い手は購入開始時に直接支払いか escrow かを選択できる。

---

## 10. 統合ポイント

### 10.1 Nostr Relay (system-nostr) との統合

- 取引交渉は `nostr-design.md` で定義されたカスタムイベント kind (4200-4203) を使用する。
- Cashu token の転送は kind 4204 (NIP-04 暗号化) を使用する。
- マーケットプレイスのリストは kind 30078 イベントとして公開される。
- Zap receipt (kind 9735) と取引完了 (kind 4203) が監査証跡を提供する。

### 10.2 Autonomy Framework (system-autonomy-agent) との統合

- エージェントの意思決定にはバジェット認識が含まれる (購入前に残高を確認)。
- エージェントは自身のプログラムに対する価格戦略を設定できる。
- 経済的シグナル (価格、需要) がエージェントの計画にフィードバックされる。

### 10.3 User Agent Framework との統合

- 各ユーザーエージェントは起動時に wallet を初期化する。
- 決済モジュールはすべてのエージェントが利用できるコア機能である。
- エージェントは売買のための標準決済 API を公開する。

---

## 11. API サマリー

### 11.1 Wallet 操作

| 操作 | 説明 |
|-----------|-------------|
| `init_wallet(agent_id)` | エージェント用の wallet を作成/読み込み |
| `get_balance(wallet)` | 利用可能残高と pending 残高を確認 |
| `create_payment(wallet, amount)` | 送信用の Cashu token を作成 |
| `receive_payment(wallet, token)` | 受信した Cashu token を償還 |
| `get_transaction_history(wallet)` | 過去のトランザクション一覧を表示 |

### 11.2 取引操作

| 操作 | 説明 |
|-----------|-------------|
| `request_purchase(buyer, seller, program_id)` | 購入を開始 |
| `send_payment(buyer, seller, amount, payment_id)` | Nostr 経由で Cashu token を送信 |
| `confirm_receipt(seller, payment_id)` | token の受領と有効性を確認 |
| `deliver_program(seller, buyer, program_id, payment_id)` | 支払い後にプログラムを送信 |

### 11.3 Escrow 操作

| 操作 | 説明 |
|-----------|-------------|
| `escrow_lock(buyer, amount, seller, program_id)` | 支払いを escrow にロック |
| `escrow_release(buyer, payment_id)` | escrow された資金を売り手にリリース |
| `escrow_dispute(buyer, payment_id, reason)` | 取引に異議を申し立てる |
| `escrow_timeout_check()` | 期限切れの escrow を自動リリース |

---

## 12. ファイル構成

```
zap-empire/
  mint/
    .env                    # Mint configuration
    start-mint.sh           # Mint startup script
  data/
    mint/                   # Mint SQLite database
    agents/                 # Unified per-agent data (shared with other subsystems)
      user0/
        wallet/             # Cashu wallet data
          wallet.db
          wallet.json
        nostr_secret.hex    # (managed by nostr subsystem)
        nostr_pubkey.hex
        state.json          # (managed by autonomy subsystem)
      user1/
        wallet/
        ...
      ...
      user9/
        wallet/
        ...
      cashu-mint/
        wallet/             # Escrow wallet + mint admin reserve
  src/
    payments/
      wallet.py             # Wallet initialization and operations
      payment.py            # Token creation and redemption
      escrow.py             # Escrow logic (runs within cashu-mint process)
      accounting.py         # Balance tracking and audit
      bootstrap.py          # Initial token distribution
  scripts/
    bootstrap-economy.sh    # One-time setup: mint + initial distribution
```

---

## 13. 依存関係

| パッケージ | バージョン | 用途 |
|---------|---------|---------|
| `cashu` (nutshell) | >= 0.16 | Mint サーバーおよび wallet クライアントライブラリ |
| `python` | >= 3.10 | すべてのエージェントと mint のランタイム |
| `sqlite3` | (stdlib) | Wallet および mint のストレージ |

> **注**: Python がすべてのエージェントの確定済みの主要言語であるため、エージェントは mint の HTTP REST API を呼び出す代わりに `cashu.wallet` ライブラリを直接インポートする。これにより wallet 操作 (token の作成、償還、残高照会) における不要なネットワークホップを回避できる。mint の HTTP API はデバッグおよび外部ツール用に引き続き利用可能である。

---

## 14. 未解決の課題

1. **エージェント間で token の貸借を可能にすべきか?** (複雑さが増すため v2 に先送り)
2. **マーケットプレイス手数料を設けるべきか?** (例: 各販売の 1% をシステムファンドへ)
3. **マルチ mint サポートは必要か?** (ローカル環境では不要。単一 mint がシンプル)
4. **NIP-60 (Nostr 内の Cashu wallet) は?** (将来的に興味深いが、ローカルプロトタイプにはオーバーキル)
