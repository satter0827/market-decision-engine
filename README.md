# market-decision-engine  
AI投資判断エンジン（EOD・日次・判断支援）

## 1. 概要

`market-decision-engine` は、**yfinance の日足データを起点に、市場終了後（EOD）に実行される投資判断支援エンジン**です。  
銘柄ごとに **発注可能な数値（Entry / Stop / Target / Size）** を機械可読な形で生成し、人間が最終判断するための材料を提供します。

本プロジェクトは「予測」や「自動売買」を目的とせず、  
**再現可能で監査可能な“判断材料”を安定して出すこと**を目的に設計されています。

- 対象市場：日本株 / 米国株
- 実行単位：市場別 EOD（日次バッチ）
- 想定保有期間：おおむね 2〜12週（スイング）
- 最終判断・発注：ユーザー責任（本ツールは助言ではありません）

---

## 2. このシステムが提供する価値

多くの投資系ツールは「銘柄名」「スコア」「強弱」までで止まり、  
**実運用に必要な数値（指値・損切・数量）を揃えてくれません**。

本システムは、運用で本当に必要になる最小単位を次の形で固定します。

- **発注可能性**  
  Entry / Stop / Target / Size を必ず数値で出す
- **判断の透明性**  
  判断の核は機械可読（DecisionCore）に限定
- **説明の統制**  
  短文説明は「翻訳・要約」に限定し、判断基準を増やさない
- **再現性**  
  同一入力 → 同一出力（EOD・非循環パイプライン）

---

## 3. 出力形式：Decision Pack

1銘柄ごとに **Decision Pack** を生成します。  
これは「発注に使える数値」と「人間が読むための短文」を分離した成果物です。

### 3.1 DecisionCore（機械可読・発注可能）

判断の本体。  
LLMはこの内容を**変更できません**。

- ticker
- buy_signal：`YES` / `YES_HALF` / `NO`
- entry / stop / target_2r / target_3r
- position_size / max_loss / time_stop_days
- plan_score / rank
- （段階導入）p_success / ev_r / uncertainty
- plan_args
- policy_snapshot_id

### 3.2 ShortSummary（人間可読・短文）

DecisionCoreの内容を**説明するための翻訳**。

- profile（固定語彙ラベル）
- strength（1文）
- risk（1文）
- if_then（任意、1文）
- warnings（最大3）

※ 短文は新しい判断基準を追加しません。

---

## 4. 設計原則（重要）

このプロジェクトは、以下の原則を**意図的に強く制限**しています。

- **判断は数値で完結**  
  DecisionCore が主。自然言語は補助
- **LLMは翻訳器**  
  数値生成・売買判断への介入は禁止
- **一方向パイプライン**  
  EODで完結。自己更新・循環なし
- **失敗時は安全側**  
  不明・不整合は `NO` または `YES_HALF`
- **混合リスクを構造で防ぐ**  
  特徴量を用途別に分離（後述）

これらは性能よりも **運用安定性・説明可能性・監査性** を優先した設計判断です。

---

## 5. データと特徴量の扱い

yfinance から取得できる情報は広く使いますが、  
**同列に混ぜない** ことを最優先します。

### features_daily
- 日足OHLCV派生
- 候補抽出・Entry / Stop / Target の唯一の根拠

### features_static
- 規模・流動性など
- サイズ調整・見送り判定にのみ使用
- 価格計算には混ぜない

### features_fundamental
- 財務・バリュエーション
- ML評価に段階導入
- 欠損前提（なくても動く設計）

---

## 6. パイプライン概要（EOD・一方向）

EODバッチは以下の順で一方向に進みます。

1. Universe確定（市場別）
2. yfinance データ取得
3. 特徴量生成（daily / static / fundamental 分離）
4. 市場環境判定（regime）
5. 候補抽出（dailyのみ）
6. plan_args 列挙
7. 実行値生成（Entry / Stop / Target / Size）
8. 補正（static・regimeでサイズ/可否のみ）
9. （任意）ML評価
10. 最良案選択
11. BUY判定（YES / YES_HALF / NO）
12. 短文生成（LLM）
13. 出力整形（CLI / ファイル等）

---

## 7. フェイルセーフ設計

本システムは「落ちない」より「誤ってYESを出さない」を優先します。

- LLM障害：DecisionCoreのみ出力
- ML不調：保守化（YES→YES_HALF→NO）
- データ欠損：銘柄スキップ＋warnings
- 契約違反：市場バッチ停止

---

## 8. 実行形態

- **CLI / バッチ前提**
- 永続DB・UIは持たない（外出し）
- `pipeline.eod.run()` を将来 API から呼べる構造

---

## 9. ディレクトリ構成（要点）

- `pipeline/`：EOD一方向オーケストレーション
- `schemas/`：DecisionCore / UserPolicy 等の契約
- `features/`：daily / static / fundamental 分離
- `execution/`：発注可能数値の生成（決定論）
- `risk/`：補正・制約（価格不変）
- `decision/`：最終判断生成
- `llm/`：翻訳・監査のみ
- `cli/`：CLIエントリポイント

詳細はディレクトリ構成ドキュメントを参照してください。

---

## 10. 免責

本ツールは投資助言を行いません。  
最終的な投資判断および損益の責任は、すべて利用者に帰属します。

了解しました。
README に **「11. 使い方（Usage）」** を追加する形で、**現状の実態（CLI / EOD / 永続化なし / 翻訳LLMは任意）に厳密に沿った使用例**を記載します。

以下は **そのまま README.md に追記できる第11章**です。

---

## 11. 使い方（Usage）

本プロジェクトは **CLI / バッチ実行** を前提としています。  
UI・自動発注・DBは持たず、EODで判断材料を生成します。

以下は最小構成（M1〜M2相当）での利用例です。

---

### 11.1 事前準備

#### Python環境
```bash
python >= 3.11
````

#### 依存関係のインストール

```bash
pip install -e .
```

（または poetry / uv / conda 等、任意の方法）

---

### 11.2 最小実行（JP市場・EOD）

最も基本的な実行例です。
Universe・ポリシーはデフォルトを使用します。

```bash
python -m market_decision_engine.cli.main run \
  --market JP \
  --asof 2024-12-27
```

#### 出力例（標準出力・要約）

```text
[RUN] market=JP asof=2024-12-27 run_id=20241227_JP_001

RANK  TICKER   SIGNAL     ENTRY    STOP     SIZE
--------------------------------------------------
1     7203.T  YES        2890     2740     100
2     9984.T  YES_HALF   6240     6030      50
3     6758.T  NO         -        -         -

[SUMMARY]
processed=420
skipped=37
YES=4 YES_HALF=3 NO=356
degraded=false
```

※ 実際の表示形式は `reports/formatter.py` に依存します。

---

### 11.3 UserPolicy を指定して実行

リスク許容度や閾値を変更したい場合は、
JSON 形式の UserPolicy を指定します。

```bash
python -m market_decision_engine.cli.main run \
  --market JP \
  --asof 2024-12-27 \
  --policy ./policies/conservative.json
```

#### UserPolicy 例（最小）

```json
{
  "risk_per_trade_pct": 0.5,
  "max_positions": 5,
  "min_plan_score": 0.6,
  "allow_yes_half": true
}
```

* policy は validation され、`policy_snapshot_id` が付与されます
* 同一 policy_snapshot を使う限り、判断条件は固定されます

---

### 11.4 米国市場（US）を実行する場合

JP / US は完全に独立したバッチとして実行されます。

```bash
python -m market_decision_engine.cli.main run \
  --market US \
  --asof 2024-12-27
```

---

### 11.5 出力をファイルに保存する（任意）

運用上必要な場合のみ、Decision Pack をファイル出力できます
（永続DBは持ちません）。

```bash
python -m market_decision_engine.cli.main run \
  --market JP \
  --asof 2024-12-27 \
  --output ./outputs/
```

例：

```text
outputs/
└── 2024-12-27/
    └── JP/
        ├── run_meta.json
        └── decision_packs.jsonl
```

---

### 11.6 LLM 要約を有効にする（任意）

LLM は **翻訳・要約専用**です。
有効にしても DecisionCore の数値は変わりません。

```bash
export OPENAI_API_KEY=xxxx

python -m market_decision_engine.cli.main run \
  --market JP \
  --asof 2024-12-27 \
  --enable-llm
```

* LLM が失敗した場合でも実行は継続します
* ShortSummary が省略されるだけで、DecisionCore は必ず出力されます

---

### 11.7 想定される運用フロー（例）

```text
毎営業日 EOD
  ↓
CLIで JP / US を実行
  ↓
Decision Pack を確認
  ↓
自分の証券口座で発注
```

週次・月次では以下を別系で実施します。

* 成績集計
* plan_catalog / 閾値の見直し
* （任意）ML再学習

※ これらは日次パイプラインの外側で行います。

---

### 11.8 本ツールが「やらないこと」

以下は **意図的に対象外**です。

* 自動発注
* リアルタイム売買
* 分足・ティック分析
* LLMによる売買判断
* DB前提の状態管理

これらをやらないことで、
再現性・説明可能性・運用安全性を優先しています。