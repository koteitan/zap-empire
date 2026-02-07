# Zap Empire 設計ドキュメント（日本語版）

Nostr + Cashu ecash を用いた自律エージェント経済システム「Zap Empire」の設計ドキュメント集です。

---

## ドキュメント一覧

### システム設計

| ドキュメント | 内容 |
|---|---|
| [自律フレームワーク設計](./autonomy-design.md) | プロセス管理、heartbeat、ライフサイクル、クラッシュリカバリ、zapctl CLI |
| [Nostr リレー＆クライアント設計](./nostr-design.md) | strfry リレー、event kind 定義、取引プロトコル、Web ダッシュボード |
| [Cashu Wallet＆決済システム設計](./zap-design.md) | Nutshell mint、ウォレット管理、Zap 支払いフロー、エスクロー |

### ユーザーエージェント設計

| ドキュメント | 内容 |
|---|---|
| [ユーザーエージェントフレームワーク設計](./user-agent-design.md) | user0-9 のアーキテクチャ、プログラム生成、取引エンジン、経済戦略 |

### レビュー・統合

| ドキュメント | 内容 |
|---|---|
| [クロスレビューノート](./review-notes.md) | 設計間の不整合 12 件の検出と解決、正規 event kind テーブル、エージェント一覧 |

---

## システム概要

```
system-master (プロセス監督)
├── system-relay    ... Nostr リレーサーバー (strfry, ws://127.0.0.1:7777)
├── system-mint     ... Cashu mint (Nutshell, http://127.0.0.1:3338)
├── system-cashu    ... Zap レシート発行 (kind 9735)
├── system-escrow   ... エスクロー決済
└── user0 ~ user9   ... 取引エージェント（プログラム生成・売買）
```

## 取引フロー

```
出品 (30078) → オファー (4200) → 承諾 (4201) → 支払い (4204, 暗号化)
→ Zap レシート (9735) → プログラム配信 (4210, 暗号化) → 完了 (4203)
```

## 技術スタック

- **言語**: Python
- **Nostr リレー**: strfry (C++/LMDB)
- **Cashu mint**: Nutshell (Python)
- **環境**: WSL2 ローカル

---

英語版: [docs/](../docs/)
