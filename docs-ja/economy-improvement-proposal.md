# Zap Empire 経済改善提案書

**ステータス**: DRAFT
**日付**: 2026-02-08
**対象問題**: 全エージェントが同一の生産能力を持つため、合理的な取引インセンティブが存在しない

---

## 1. 問題の本質

### 1.1 現状の欠陥

現在の Zap Empire 設計では、10体のエージェントが**全く同じテンプレートDB**にアクセスし、**全く同じ8カテゴリ**のプログラムを生成できる。パーソナリティ（conservative, aggressive, specialist, generalist, opportunist）は**価格設定や取引頻度**に影響するが、**生産能力そのもの**には影響しない。

つまり、こういう状況になる:

> 合理的なエージェントAが、エージェントBの `fibonacci-solver` を150 satsで買う理由は何か?
> Aは自分で同じものを0 satsで作れるのに。

パーソナリティによる「好み」は人工的な需要であり、自己利益に基づく合理的な取引動機ではない。`need_score` の `category_gap` や `random_curiosity` が購入を誘導するが、これは本質的に**ランダムな消費**であり、**経済的合理性に基づく貿易**ではない。

### 1.2 現実の経済から学ぶ

実際の経済で取引が成立する根本的理由:

| 原理 | 説明 | 現在のZap Empire |
|---|---|---|
| **比較優位** | 各国は相対的に得意な分野に特化し、他を輸入する | 全員が全カテゴリで同一能力 |
| **資源の非対称性** | 石油は中東、チップはTSMC | テンプレートは全員共有 |
| **時間コスト** | 自分で作るより買った方が早い場合がある | 生成コスト0、即時生成 |
| **品質差** | 専門家の製品は素人より良い | 品質に実質的差異なし |
| **消費需要** | 食料・エネルギーなど生存に必要な財 | プログラムは「あれば良い」程度 |
| **希少性** | 供給が有限で代替不可能 | 無限に生成可能 |

現在の設計は**6つの原理すべてに違反**している。

### 1.3 設計目標

この提案書では、以下の条件を満たす改善メカニズムを提案する:

1. **合理的なエージェントが自発的に取引する**動機が生まれること
2. **実装が現在のアーキテクチャと整合的**であること
3. **経済が自律的に循環**し、外部介入なしで持続すること
4. **ダッシュボードで面白い経済行動が観察**できること
5. **過度に複雑にしない**こと（Phase 1 実装に適した規模）

---

## 2. 提案メカニズム一覧

以下の5つのメカニズムを組み合わせることで、堅牢な取引経済を構築する。

| # | メカニズム | 取引を生む理由 | 難易度 |
|---|---|---|---|
| **M1** | カテゴリ制限（非対称生産能力） | 自分で作れないものは買うしかない | Easy |
| **M2** | コントラクト・システム（外部需要） | 特定カテゴリの組み合わせを集める必要性 | Medium |
| **M3** | 生産コスト（satsを消費） | 買った方が安い場合がある | Easy |
| **M4** | 品質スコアと専門化ボーナス | 専門家の方が良い製品を作る | Medium |
| **M5** | プログラム減価（depreciation） | 継続的な需要が生まれる | Easy |

---

## 3. M1: カテゴリ制限 — 非対称生産能力

### 3.1 なぜ取引が生まれるか

**エージェントが全8カテゴリのうち一部しか生産できない場合、残りのカテゴリのプログラムは他のエージェントから購入するしかない。** これは現実経済における資源の非対称性（比較優位の物理的基盤）に相当する。

### 3.2 設計

各エージェントに **production_categories**（生産可能カテゴリ、3〜5個）を割り当てる:

| Agent | パーソナリティ | 生産可能カテゴリ | 生産不可カテゴリ |
|---|---|---|---|
| user0 (ぼたん) | Conservative | math, text, validators | crypto, utilities, generators, converters, data_structures |
| user1 (わんたん) | Conservative | data_structures, converters, utilities | math, text, crypto, generators, validators |
| user2 (みかたん) | Aggressive | text, generators, converters, utilities | math, data_structures, crypto, validators |
| user3 (ぷりたん) | Aggressive | crypto, validators, math, generators | text, data_structures, utilities, converters |
| user4 (くろたん) | Specialist | math, crypto | text, data_structures, utilities, generators, converters, validators |
| user5 (しろたん) | Specialist | data_structures, text | math, crypto, utilities, generators, converters, validators |
| user6 (あおたん) | Generalist | math, text, data_structures, crypto, utilities | generators, converters, validators |
| user7 (もちたん) | Generalist | generators, converters, validators, utilities, text | math, data_structures, crypto |
| user8 (ぽんたん) | Opportunist | crypto, utilities, generators | math, text, data_structures, converters, validators |
| user9 (りんたん) | Opportunist | converters, validators, data_structures | math, text, crypto, utilities, generators |

**設計原則**:
- Specialist は2カテゴリのみ（少ないが高品質 — M4と連動）
- Generalist は5カテゴリ（広いが平均品質）
- 他は3〜4カテゴリ
- **各カテゴリは最低2エージェントが生産可能**（独占を防止、競争を確保）
- **どのエージェントも全8カテゴリはカバーできない**（取引必須）

### 3.3 実装方法

**変更ファイル**: `config/agents.json`, `src/user/personality.py`, `src/user/program_generator.py`（新規）

#### 3.3.1 `config/agents.json` にカテゴリ追加

```json
{
  "id": "user0",
  "name": "ぼたん",
  "strategy": "Conservative",
  "production_categories": ["math", "text", "validators"],
  "tick_interval": 60,
  "restart_policy": "on-failure"
}
```

#### 3.3.2 `src/user/personality.py` 更新

```python
AGENT_CONFIG = {
    0: {
        "name": "ぼたん",
        "personality": "conservative",
        "production_categories": ["math", "text", "validators"],
    },
    # ... 各エージェント
}
```

#### 3.3.3 `src/user/program_generator.py` にカテゴリ制限ロジック追加

```python
def generate_program(self) -> Optional[Program]:
    """生産可能カテゴリからのみプログラムを生成する。"""
    allowed = self.agent_config["production_categories"]
    category = self.strategy.select_category(allowed_categories=allowed)
    template = self.templates[category].random_template()
    # ... 既存の生成ロジック
```

### 3.4 難易度: **Easy**

- 設定値の追加とフィルタリングのみ
- 既存のテンプレートエンジン設計とそのまま互換
- agents.json と personality.py の更新で完了

---

## 4. M2: コントラクト・システム — 外部需要の創出

### 4.1 なぜ取引が生まれるか

**コントラクト（contract）は「特定カテゴリの組み合わせ」を集めると報酬がもらえるクエストである。** エージェントは自分で作れないカテゴリのプログラムをマーケットプレイスで購入しなければコントラクトを達成できない。これにより:

1. **明確な購買動機**: 「mathとcryptoとvalidatorsのプログラムを集めて500 sats報酬」
2. **カテゴリ間の相互依存**: M1のカテゴリ制限と相乗効果
3. **経済への通貨注入**: コントラクト報酬がマネーサプライを補充し、経済を循環させる

### 4.2 設計

#### コントラクトの構造

```python
@dataclass
class Contract:
    contract_id: str                # UUID
    required_categories: list[str]  # 例: ["math", "crypto", "validators"]
    reward_sats: int                # 達成報酬（例: 500）
    deadline_ticks: int             # 有効期限（tick数）
    difficulty: str                 # "easy" (2カテゴリ), "medium" (3), "hard" (4-5)
```

#### コントラクト発行者: `system-master`

`system-master` が定期的にコントラクトを Nostr イベント（**kind 4310**: Contract Announcement）として発行する。

```json
{
  "kind": 4310,
  "tags": [
    ["d", "<contract-uuid>"],
    ["t", "contract"]
  ],
  "content": "{\"required_categories\":[\"math\",\"crypto\",\"validators\"],\"reward_sats\":500,\"deadline_ticks\":30,\"difficulty\":\"medium\"}"
}
```

#### コントラクト達成フロー

1. エージェントがコントラクトを閲覧（kind 4310 を subscribe）
2. 要求カテゴリの各プログラムを自分のインベントリで確認
3. 不足カテゴリはマーケットプレイスで購入（M1により必ず不足がある）
4. 全カテゴリ揃ったら `system-master` に達成申請（**kind 4311**: Contract Submission）
5. `system-master` が検証し、報酬を Cashu トークンで支払い（**kind 4312**: Contract Reward）
6. 提出されたプログラムは「消費」される（インベントリから除去 — M5と連動）

#### コントラクト難易度と報酬

| 難易度 | 要求カテゴリ数 | 報酬範囲 | 発行頻度 |
|---|---|---|---|
| Easy | 2 | 200–400 sats | 毎5 tick |
| Medium | 3 | 400–800 sats | 毎10 tick |
| Hard | 4–5 | 800–1500 sats | 毎20 tick |

#### 経済バランス

- **報酬合計は生産コスト（M3）+ 購入コストを上回る**設計にする
- ただし**早い者勝ち**（1コントラクトにつき最初の達成者のみ報酬）で競争を生む
- コントラクト報酬がマネーサプライの唯一の追加注入源（初期10,000 sats/agent以外）

### 4.3 実装方法

**新規ファイル**: `src/contracts/manager.py`, `src/contracts/generator.py`
**変更ファイル**: `src/user/strategy.py`（新規）, `config/constants.json`, Nostr event kinds テーブル

#### 4.3.1 `config/constants.json` に追加

```json
{
  "contract_easy_interval_ticks": 5,
  "contract_medium_interval_ticks": 10,
  "contract_hard_interval_ticks": 20,
  "contract_easy_reward_range": [200, 400],
  "contract_medium_reward_range": [400, 800],
  "contract_hard_reward_range": [800, 1500]
}
```

#### 4.3.2 新規 Nostr イベント種別

| Kind | Name | Description |
|---|---|---|
| `4310` | Contract Announcement | system-master がコントラクト発行 |
| `4311` | Contract Submission | エージェントが達成申請 |
| `4312` | Contract Reward | system-master が報酬支払い |

#### 4.3.3 エージェント側の意思決定ロジック

```python
# strategy.py
def select_action(self, state):
    # 既存の優先度に「コントラクト追求」を追加
    active_contracts = self.scan_contracts()
    achievable = self.evaluate_contracts(active_contracts)

    if achievable:
        best = max(achievable, key=lambda c: c.expected_profit)
        missing = self.missing_categories(best)
        if missing:
            return Action.BUY_FOR_CONTRACT(contract=best, categories=missing)
        else:
            return Action.SUBMIT_CONTRACT(contract=best)
    # ... 既存のロジック
```

### 4.4 難易度: **Medium**

- 新規モジュール（コントラクトマネージャー）の追加が必要
- system-master にコントラクト発行ロジックを追加
- 新規 Nostr event kinds 3つ
- エージェントの意思決定ロジックに統合

---

## 5. M3: 生産コスト — Make or Buy の判断

### 5.1 なぜ取引が生まれるか

**プログラム生成に sats コストがかかる場合、「自分で作るコスト」と「マーケットで買うコスト」の比較が生まれる。** 生産コスト > 市場価格なら、買った方が合理的。これは現実経済の「make or buy decision」そのものである。

さらに:
- **Specialist はフォーカスカテゴリの生産コストが低い**（効率的生産）
- **Generalist は全カテゴリ生産可能だがコストが高い**（器用貧乏）
- **Aggressive は大量生産でコスト低減**（規模の経済）

### 5.2 設計

#### 基本生産コスト

```python
BASE_PRODUCTION_COST = {
    "math": 80,
    "text": 60,
    "data_structures": 120,
    "crypto": 100,
    "utilities": 70,
    "generators": 50,
    "converters": 60,
    "validators": 90,
}
```

#### パーソナリティ別コスト係数

```python
PRODUCTION_COST_MULTIPLIER = {
    "conservative": 1.0,    # 標準
    "aggressive": 0.7,      # 大量生産で効率化
    "specialist": {
        "focus": 0.4,       # 専門カテゴリは大幅に安い
        "other": 1.5,       # 専門外は割高（M1で生産不可の場合は無関係）
    },
    "generalist": 1.2,      # 広く浅くのためやや割高
    "opportunist": 0.9,     # やや効率的
}
```

#### 具体例

くろたん（Specialist: math, crypto）が math プログラムを作る場合:
- 生産コスト = 80 (base) × 0.4 (specialist focus) = **32 sats**
- 市場価格が50 satsなら → 自分で作った方が安い（作る）

あおたん（Generalist）が math プログラムを作る場合:
- 生産コスト = 80 (base) × 1.2 (generalist) = **96 sats**
- 市場でくろたんが50 satsで売っていれば → 買った方が安い（買う）

**これが比較優位の実現である。**

#### コスト支払い

生産コストはプログラム生成時にウォレットから差し引かれる（「計算リソース使用料」として）。差し引かれた sats は **burn**（消滅）する。これにより:

1. 無限生産の防止
2. マネーサプライの自然なデフレ圧力（M2のコントラクト報酬でバランス）
3. 「作るか買うか」の合理的判断

### 5.3 実装方法

**変更ファイル**: `config/constants.json`, `src/user/personality.py`, `src/user/program_generator.py`, `src/wallet/manager.py`

#### 5.3.1 `config/constants.json` に追加

```json
{
  "base_production_cost": {
    "math": 80, "text": 60, "data_structures": 120, "crypto": 100,
    "utilities": 70, "generators": 50, "converters": 60, "validators": 90
  }
}
```

#### 5.3.2 `src/user/personality.py` に追加

```python
PERSONALITIES = {
    "specialist": {
        # ... 既存フィールド
        "production_cost_focus": 0.4,
        "production_cost_other": 1.5,
    },
    "aggressive": {
        # ... 既存フィールド
        "production_cost_multiplier": 0.7,
    },
    # ...
}
```

#### 5.3.3 生産時のコスト計算と差し引き

```python
# program_generator.py
def generate_program(self) -> Optional[Program]:
    category = self.strategy.select_category(allowed_categories=self.allowed)
    cost = self.calculate_production_cost(category)

    if cost > self.wallet.balance:
        return None  # 資金不足で生産不可

    # コスト支払い（burn）
    self.wallet.deduct(cost)  # 内部的に残高を減算

    program = self._build_program(category)
    program.production_cost = cost  # 原価記録（価格設定の参考に）
    return program
```

### 5.4 難易度: **Easy**

- 設定値の追加と簡単な計算ロジック
- ウォレットからの差し引き（burn）は `WalletManager` に小さな変更
- 既存アーキテクチャとの高い互換性

---

## 6. M4: 品質スコアと専門化ボーナス

### 6.1 なぜ取引が生まれるか

**Specialistが作った専門カテゴリのプログラムは、Generalistが作った同カテゴリのプログラムより品質が高い場合、品質を求めるエージェントは購入する動機がある。** コントラクト（M2）が品質ボーナスを提供すれば、高品質プログラムへの実需が生まれる。

### 6.2 設計

#### 品質スコアの定義

プログラムに **quality_score**（0.0〜1.0）を付与する:

```python
quality_score = base_quality × specialization_bonus × complexity_factor × random_variance
```

| 要因 | 計算 |
|---|---|
| `base_quality` | 0.5（全エージェント共通ベース） |
| `specialization_bonus` | Specialist のフォーカスカテゴリ: ×1.8、それ以外: ×1.0 |
| `complexity_factor` | simple: ×0.7, medium: ×1.0, complex: ×1.3 |
| `random_variance` | ×(0.85〜1.15) ランダム |

#### 具体例

| 生産者 | カテゴリ | 複雑度 | 品質スコア |
|---|---|---|---|
| くろたん（Specialist math） | math | complex | 0.5 × 1.8 × 1.3 × ~1.0 = **~1.17 → 1.0** |
| あおたん（Generalist） | math | complex | 0.5 × 1.0 × 1.3 × ~1.0 = **~0.65** |
| みかたん（Aggressive） | text | medium | 0.5 × 1.0 × 1.0 × ~1.0 = **~0.50** |

#### 品質がもたらす実質的差異

1. **コントラクト報酬ボーナス**: 提出プログラムの平均品質が高いほどボーナス報酬

```python
quality_bonus = base_reward × (avg_quality - 0.5) × 0.5
# 例: 報酬500 sats、平均品質0.8 → ボーナス = 500 × 0.3 × 0.5 = 75 sats追加
```

2. **マーケットプレイスでの差別化**: 品質スコアがリスティングに表示され、購入判断に影響

3. **品質劣化防止**: 高品質プログラムはM5（depreciation）の劣化速度が遅い

### 6.3 実装方法

**変更ファイル**: `src/user/program_generator.py`, `src/user/personality.py`, `src/user/marketplace.py`（新規）

#### 6.3.1 Nostr リスティングに品質情報を追加

```json
{
  "kind": 30078,
  "tags": [
    ["d", "<program-uuid>"],
    ["t", "python"],
    ["t", "<category>"],
    ["price", "<sats>", "sat"],
    ["quality", "0.85"]
  ],
  "content": "{\"name\":\"...\",\"quality_score\":0.85,...}"
}
```

#### 6.3.2 購入判断に品質を組み込む

```python
# strategy.py の need_score 計算
need_score = (
    category_gap_weight * category_gap          # 0.3
    + quality_gap_weight * quality_gap            # 0.3 (高品質プログラムへの需要)
    + contract_need_weight * contract_need        # 0.3 (コントラクト達成のため)
    + random_curiosity_weight * random.random()   # 0.1
)
```

### 6.4 難易度: **Medium**

- 品質スコア計算自体は単純
- Nostr リスティングのスキーマ変更
- コントラクトシステムとの連携が必要

---

## 7. M5: プログラム減価（Depreciation）

### 7.1 なぜ取引が生まれるか

**プログラムが時間経過で品質劣化する場合、一度買っただけでは不十分で、定期的に新しいプログラムを調達する必要がある。** これにより:

1. **継続的な需要**: 一回きりの取引ではなく、繰り返し購入が必要
2. **経済の循環**: 買って満足→需要消滅、というデッドロックを防ぐ
3. **コントラクト達成の動的制約**: 古いプログラムでは品質要件を満たせない

### 7.2 設計

#### 減価メカニズム

各プログラムの `quality_score` は時間経過で減少する:

```python
# 毎tick（~60秒）
quality_score = quality_score × decay_rate

decay_rate = {
    "base": 0.998,        # ベース: 1tickあたり0.2%劣化
    "high_quality": 0.999, # 高品質（>=0.8）: 劣化が遅い
    "low_quality": 0.995,  # 低品質（<0.4）: 劣化が速い
}
```

#### 減価のタイムライン

| 初期品質 | 50% に達する tick数 | 実時間（60秒/tick） |
|---|---|---|
| 1.0 (高品質) | ~693 ticks | ~11.5時間 |
| 0.65 (中品質) | ~346 ticks | ~5.8時間 |
| 0.5 (低品質) | ~139 ticks | ~2.3時間 |

#### 廃棄閾値

品質スコアが **0.1未満**になったプログラムは自動的にインベントリから削除される（ゴミプログラムの蓄積防止）。

#### コントラクトとの連動

コントラクト提出時、プログラムの**現在の品質スコア**が **0.3未満**だと提出不可。つまり古いプログラムでコントラクトを達成するには、新しいプログラムへの入れ替えが必要。

### 7.3 実装方法

**変更ファイル**: `src/user/agent.py`（新規）, `src/user/strategy.py`

#### 7.3.1 tick ごとの減価処理

```python
# agent.py の activity_loop 内
async def apply_depreciation(self):
    for program in self.inventory:
        if program.quality_score >= 0.8:
            rate = 0.999
        elif program.quality_score < 0.4:
            rate = 0.995
        else:
            rate = 0.998
        program.quality_score *= rate

        # 廃棄
        if program.quality_score < 0.1:
            self.inventory.remove(program)
            self.log(f"Discarded {program.name} (quality too low)")
```

#### 7.3.2 state.json に品質情報を永続化

```json
{
  "programs": [
    {
      "uuid": "abc-123",
      "name": "fast-fibonacci-calculator",
      "category": "math",
      "quality_score": 0.72,
      "created_at": 1700000100,
      "production_cost": 32
    }
  ]
}
```

### 7.4 難易度: **Easy**

- tick ごとの単純な乗算処理
- state.json のスキーマに `quality_score` フィールド追加
- 既存の activity_loop に自然に統合可能

---

## 8. メカニズム相互作用の全体像

### 8.1 経済循環ダイアグラム

```
        ┌─────────────────────────────────────────────────────┐
        │              system-master                           │
        │  コントラクト発行 (kind 4310)                         │
        │  報酬支払い (kind 4312)  ←── 通貨注入                │
        └───────────┬─────────────────────────┬───────────────┘
                    │ コントラクト              │ 報酬 (sats)
                    ▼                          │
        ┌───────────────────────┐              │
        │   エージェント (user0-9)│◀─────────────┘
        │                       │
        │ 1. コントラクト確認    │
        │    → 必要カテゴリ特定   │
        │                       │
        │ 2. 自分で作れる？      │
        │    YES → 生産 ────────┼──→ sats消費（burn）=デフレ圧力
        │    (M1: カテゴリ制限)  │     (M3: 生産コスト)
        │    NO → 購入 ─────────┼──→ マーケットプレイスで取引
        │                       │
        │ 3. 品質は十分？        │
        │    (M4: 品質スコア)    │
        │    低い → より高品質を  │
        │    購入する必要あり     │
        │                       │
        │ 4. 手持ちが劣化？      │
        │    (M5: depreciation)  │
        │    → 入替需要が発生     │
        │                       │
        │ 5. コントラクト達成    │
        │    → 報酬獲得 ─────────┼──→ sats注入 = インフレ圧力
        │    → プログラム消費    │     (経済バランス)
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────────┐
        │          マーケットプレイス (Nostr)          │
        │                                           │
        │  出品: 自分の得意カテゴリのプログラム         │
        │        (Specialist = 高品質 + 低コスト)      │
        │                                           │
        │  購入: 自分で作れない/作ると高いプログラム    │
        │        (比較優位に基づく合理的取引)           │
        │                                           │
        │  価格発見: 需要と供給の相互作用              │
        └───────────────────────────────────────────┘
```

### 8.2 メカニズム間のシナジー

| 組み合わせ | 効果 |
|---|---|
| **M1 + M2** | カテゴリ制限があるため、コントラクトの要求カテゴリに対して必ず「買わなければならない」ものがある |
| **M1 + M3** | 生産可能カテゴリでも、コスト比較により買った方が得な場合がある（Specialist vs Generalist） |
| **M2 + M3** | コントラクト報酬 > (生産コスト + 購入コスト) の設計により、経済活動が利益を生む |
| **M2 + M5** | 減価によりコントラクト達成に「鮮度の高い」プログラムが必要、繰り返し調達が必要 |
| **M3 + M4** | Specialist は低コスト + 高品質で生産 → マーケットに高品質プログラムを安く供給 |
| **M4 + M5** | 高品質プログラムは劣化が遅い → 高品質品により高い価格を支払う合理的理由 |

### 8.3 マネーフロー分析

```
[通貨注入源]                    [通貨消滅源]
─────────────                  ─────────────
コントラクト報酬                 プログラム生産コスト（burn）
(+200〜+1500 sats/contract)    (-32〜-144 sats/program)

初期配布
(10,000 sats × 10 agents)
```

**均衡条件**: コントラクト報酬の総量 ≈ 生産コストの総量 + 取引摩擦

具体的に:
- 10エージェントが平均5 tick/programで生産 → ~120プログラム/時間
- 平均生産コスト ~70 sats → **8,400 sats/時間の通貨消滅**
- コントラクト発行: easy(12/時間×300) + medium(6/時間×600) + hard(3/時間×1150) = **10,650 sats/時間の通貨注入**
- **差分 +2,250 sats/時間**のインフレ → 経済成長に対応

パラメータ調整で均衡をチューニング可能。

---

## 9. エージェント別の経済的役割

改善後の各エージェントタイプが経済においてどう振る舞うか:

### Conservative（ぼたん、わんたん）
- **少ないカテゴリで慎重に生産**、高品質を目指す
- **高価格設定**で利益率重視
- コントラクトは**easy〜medium**を確実に達成
- 不足カテゴリは**信頼できるパートナーからのみ購入**

### Aggressive（みかたん、ぷりたん）
- **低コスト大量生産**でマーケットを席巻
- **安価な出品**で薄利多売
- コントラクトを**素早く達成**して報酬を積む
- 品質より**速度と量**で勝負

### Specialist（くろたん、しろたん）
- **2カテゴリのみだが最高品質・最低コスト**で生産
- マーケットプレイスの**品質リーダー**
- 高品質プログラムに**プレミアム価格**を付ける
- コントラクト達成には**多くの購入が必要**（2カテゴリしか作れないため）
- だが報酬の品質ボーナスで高い利益を得る

### Generalist（あおたん、もちたん）
- **5カテゴリと最も広い生産範囲**
- **自給率が高い**ため購入コストが低い
- ただし**品質は平均的**でプレミアム価格は取れない
- コントラクト達成に必要な購入が少ない → **手堅い利益**

### Opportunist（ぽんたん、りんたん）
- **市場の需給を観察して戦略を適応**
- 品薄カテゴリのプログラムを**安く買って高く売る**（転売）
- コントラクト報酬が高い時に**積極的に参加**
- **裁定取引（arbitrage）**を行うマーケットメイカー的役割

---

## 10. 実装ロードマップ

### Phase 1: 基盤メカニズム（推奨: 最初に実装）

| 順番 | メカニズム | 難易度 | 所要変更 |
|---|---|---|---|
| 1 | **M1: カテゴリ制限** | Easy | `agents.json`, `personality.py` に `production_categories` 追加。`program_generator.py` でフィルタリング |
| 2 | **M3: 生産コスト** | Easy | `constants.json` に `base_production_cost` 追加。生成時にウォレットから差し引き |
| 3 | **M5: 減価** | Easy | `agent.py` の activity_loop に毎tick の `quality_score` 減衰処理追加 |

この3つだけで**比較優位に基づく基本的な取引動機**が成立する。

### Phase 2: 需要エンジン

| 順番 | メカニズム | 難易度 | 所要変更 |
|---|---|---|---|
| 4 | **M2: コントラクト** | Medium | `src/contracts/` 新規モジュール。system-master に発行ロジック。新規 Nostr kinds 3つ |
| 5 | **M4: 品質スコア** | Medium | `program_generator.py` に品質計算。リスティングに品質情報追加。コントラクトに品質ボーナス |

### Phase 3: チューニング

- 経済パラメータの調整（生産コスト、コントラクト報酬、減価率）
- ダッシュボードに経済指標（GDP、インフレ率、取引量）を追加
- ログ分析でバランスを検証

---

## 11. 変更対象ファイル一覧

| ファイル | 変更内容 | メカニズム |
|---|---|---|
| `config/agents.json` | `production_categories` フィールド追加 | M1 |
| `config/constants.json` | `base_production_cost`, コントラクト設定追加 | M2, M3 |
| `src/user/personality.py` | `production_categories`, `production_cost_*` 追加 | M1, M3 |
| `src/user/program_generator.py` (新規) | カテゴリ制限、生産コスト計算、品質スコア計算 | M1, M3, M4 |
| `src/user/strategy.py` (新規) | コントラクト評価、make-or-buy 判断、品質重視購入 | M2, M3, M4 |
| `src/user/agent.py` (新規) | activity_loop に減価処理追加 | M5 |
| `src/user/marketplace.py` (新規) | 品質情報付きリスティング | M4 |
| `src/contracts/manager.py` (新規) | コントラクト発行・検証・報酬 | M2 |
| `src/contracts/generator.py` (新規) | ランダムコントラクト生成 | M2 |
| `docs/nostr-design.md` | kind 4310-4312 追加 | M2 |

---

## 12. 成功指標

改善の効果を測定する指標:

| 指標 | 目標 | 測定方法 |
|---|---|---|
| **取引頻度** | 1エージェントあたり毎時3回以上の購入 | kind 4203 (Trade Complete) のカウント |
| **カテゴリ多様性** | 各エージェントが平均6+カテゴリのプログラムを保有 | state.json のプログラム一覧分析 |
| **マネー循環速度** | 1時間あたり初期供給量の20%以上が移動 | kind 4204 (Trade Payment) の合計額 |
| **経済持続性** | 12時間後もすべてのエージェントが残高 > 0 | status broadcast (kind 4300) |
| **コントラクト達成率** | 発行コントラクトの60%以上が達成される | kind 4312 (Contract Reward) / kind 4310 |
| **Specialist プレミアム** | Specialist の平均売却価格が Generalist の1.3倍以上 | リスティングデータの統計分析 |

---

## 13. まとめ

### 核心的な回答

> **「なぜ合理的なエージェントAは、エージェントBからプログラムを購入するのか？」**

改善後の回答:

1. **Aはそのカテゴリのプログラムを作れない**（M1: カテゴリ制限）
2. **Aが自分で作るとBから買うより高くつく**（M3: 生産コスト + 比較優位）
3. **Bの方が高品質なプログラムを作る**（M4: 専門化ボーナス）
4. **Aはコントラクト達成のために今すぐそのプログラムが必要**（M2: 外部需要）
5. **Aの手持ちプログラムが劣化して使い物にならない**（M5: 減価）

これら5つの理由のうち、**少なくとも2〜3が同時に適用される**設計になっており、取引は「ランダムな好奇心」ではなく**経済的合理性に基づく自発的行動**となる。

### 設計哲学

- **シンプルなルールから複雑な経済行動が創発する**
- **パラメータ調整で経済バランスをチューニング可能**
- **既存のアーキテクチャ（Nostr + Cashu + テンプレート生成）を最大限活用**
- **実装は段階的に行い、Phase 1 の3メカニズムだけでも最低限の経済が成立する**
