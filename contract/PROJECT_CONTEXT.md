# PROJECT_CONTEXT: market-decision-engine

このファイルは、ChatGPT 等の支援ツールに「本プロジェクトの前提（憲法）」として渡すための **最小・固定コンテキスト** です。  
仕様・設計・実装・テスト・生成物は、本書の制約に反してはなりません（矛盾がある場合は **コード > 本書 > その他ドキュメント** の順で正とします。現時点ではコードが未実装のため、本書と `documents/` を正とします）。

---

## 1. プロジェクト目的（What / Why）

`market-decision-engine` は、**EOD（日次・市場終了後）**に実行される **投資判断支援エンジン**です。  
yfinance の日足データを起点に、銘柄ごとに **発注可能な数値**（Entry / Stop / Target / Size）を機械可読な形で生成し、人間が最終判断するための材料（Decision Pack）を提供します。

### 目的
- 再現可能（同一入力 → 同一出力）で監査可能な判断材料を安定して出す
- 「スコア」だけでなく **実運用に必要な数値**を揃える
- 失敗時は安全側に倒れ、誤って YES を出しにくい構造を維持する

### 対象
- 市場：日本株（JP） / 米国株（US）
- データ粒度：日足（EOD）
- 想定保有期間：概ね 2〜12 週（スイング中心）
- 実行形態：CLI / バッチ（UI・永続 DB は持たない。外出し）

---

## 2. 非目的（Must Not）

本システムは「予測」や「自動売買」を目的としません。以下は **禁止**です。

- LLM が数値（Entry/Stop/Target/Size 等）を生成・変更すること
- LLM が売買判断（YES/NO 等）を独自に変更すること
- ティック/分足など高頻度データ前提の分析
- ニュース/SNS/板情報等の外部データ利用（初期段階）
- 証券会社 API による自動発注

---

## 3. 成果物（Decision Pack）と契約

1銘柄ごとに **Decision Pack** を生成します。  
「数値の核」と「人間向け短文」を分離し、短文が判断基準を増やさないよう制御します。

### 3.1 DecisionCore（機械可読・発注可能）
- LLM は **変更不可**
- 発注に必要な数値と、判断の核（buy_signal 等）を含む

代表フィールド（契約の核）:
- ticker
- buy_signal: `YES` / `YES_HALF` / `NO`
- entry / stop / target_2r / target_3r
- position_size / max_loss / time_stop_days
- plan_score / rank
- （段階導入）p_success / ev_r / uncertainty
- plan_args
- policy_snapshot_id

### 3.2 ShortSummary（人間可読・短文）
- DecisionCore の内容を **翻訳・要約** するだけ（新しい判断基準を追加しない）
- フォーマット・語彙を統制（最大3 warnings など）

---

## 4. 設計原則（Invariants）

1. **判断は数値で完結**（DecisionCore が主。自然言語は補助）
2. **LLM は翻訳器**（数値生成・判断介入は禁止）
3. **一方向パイプライン**（EODで完結、自己更新・循環なし）
4. **同一入力 → 同一出力**（決定論を優先）
5. **失敗時は安全側**（不明・不整合は `NO` もしくは `YES_HALF`、あるいは銘柄スキップ）
6. **Feature 分離**（daily / static / fundamental を用途別に混ぜない）
7. **最終責任は人間**（投資助言ではない）

---

## 5. Feature 分離ルール（最重要）

- `features_daily`（OHLCV 由来）
  - 候補抽出・Entry/Stop/Target の **唯一の根拠**
- `features_static`（規模・流動性等）
  - **サイズ調整**・見送り判定にのみ使用
  - 価格計算（Entry/Stop/Target）には混ぜない
- `features_fundamental`（財務等）
  - ML 評価の段階導入に使用
  - 欠損前提（無くても動く）

---

## 6. パイプライン（EOD・一方向）の基本形

1. Universe 確定（市場別）
2. yfinance データ取得
3. 特徴量生成（daily/static/fundamental 分離）
4. 市場環境判定（regime）
5. 候補抽出（daily のみ）
6. plan_args 列挙
7. 実行値生成（Entry/Stop/Target/Size：決定論）
8. 補正（static・regime で **可否/サイズのみ**）
9. （任意）ML 評価
10. 最良案選択
11. BUY 判定（YES/YES_HALF/NO）
12. 短文生成（LLM）
13. 出力整形（CLI / ファイル等）

---

## 7. フェイルセーフ（縮退の基本）

- LLM 障害：DecisionCore のみ出力（ShortSummary は省略/テンプレ）
- ML 不調：保守化（YES → YES_HALF → NO）
- データ欠損：銘柄スキップ + warnings
- 契約違反：市場バッチ停止（致命的）

---

## 8. 実装規約（抜粋・守るべきこと）

- Python >= 3.11
- black / isort / ruff / mypy（strict 相当）を CI で強制
- Pydantic（v2）を契約の第一選択（`extra="forbid"`, `frozen=True` 推奨）
- 例外メッセージは英語（ログ/CI の一貫性）
- Import 依存方向を厳守（例：execution は daily 以外を参照禁止、llm は DecisionCore 改変禁止）

---

## 9. 段階リリース（M1 → M9）

- M1：最小の Decision Pack 出力（cli / data / features(daily) / execution / decision / reports）
- M2：risk / utils / logging 等の運用品質
- M3+：regime / models / llm 等を段階導入（縮退可能であること）

---

## 10. 参照すべき一次資料（本リポジトリ内）

- `README.md`（概要と設計原則の要点）
- `documents/010_*`（要件定義）
- `documents/020_*`（外部設計）
- `documents/030_*`（内部設計）
- `documents/031_*`（推奨ディレクトリ構成）
- `documents/040_*`（パイプライン設計）
- `documents/050_*`（データ設計）
- `documents/060_*`（フェイルセーフ）
- `documents/070_*`（用語集）
- `documents/080_ADR.md`（意思決定ログ）

---

## 11. ChatGPT への依頼テンプレ（推奨）

作業依頼時は、以下を先頭に付けてください。

- 「本回答は PROJECT_CONTEXT に準拠すること」
- 「LLM は翻訳器。DecisionCore の数値/判断基準を増やさないこと」
- 「Feature 分離原則を破らないこと（daily/static/fundamental）」
- 「失敗時は安全側（NO/YES_HALF/スキップ）を優先すること」
