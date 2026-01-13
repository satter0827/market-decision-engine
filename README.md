# AI投資判断エンジン market-decision-engine

## 1. 概要

yfinance の日足データを起点に、市場終了後（EOD）に **銘柄候補と発注可能な数値**を自動生成します。
出力は「そのまま発注に使える数値」と「短文説明」をセットにした **Decision Pack** です。

* 対象：日本株・米国株
* 想定保有：14〜90日（スイング）
* 実行：JP/US を別バッチでEOD実行
* 責任：最終判断はユーザー（本ツールは助言ではなく判断支援）

---

## 2. このシステムが解決すること

多くの投資系ツールは「スコア」や「銘柄名」しか出さず、実運用に必要な要素（指値・損切・数量）が揃いません。
本システムは、運用で必要になる最小単位を **発注可能な形**に固定し、再現可能に回せるように設計しています。

* **実行可能性**：Entry/Stop/Target/Size を必ず数値で出す
* **透明性**：判断の核は機械可読（DecisionCore）
* **監査可能性**：短文説明は“翻訳”に限定し、判断基準を増やさない

---

## 3. 出力（Decision Pack）

### DecisionCore（機械可読：発注可能）

* ticker
* buy_signal：YES / YES_HALF / NO
* entry / stop / target_2r / target_3r
* position_size / max_loss / time_stop_days
* p_success / ev_r / uncertainty / plan_score / rank
* plan_args / policy_snapshot_id

### ShortSummary（人間可読：短文）

* profile（固定語彙ラベル）
* strength（1文）
* risk（1文）
* if_then（任意、1文）
* warnings（最大3）

---

## 4. 設計方針

* **判断は数値で完結**：DecisionCoreが主、短文は補助
* **LLMは翻訳器**：数値生成・判断介入は禁止（説明と監査のみ）
* **AI層は非循環**：同一入力→同一出力を原則
* **失敗時は安全側**：不明ならNO、機能劣化時は縮退運用
* **混合リスク対策**：特徴量を用途別に分離

---

## 5. データと特徴量

yfinanceで取れる情報は広く収集しますが、「同列に混ぜない」ため用途別に分割します。

* **features_daily**：OHLCV派生（実行の主役）
  候補抽出・Entry/Stop/Targetの計算はこれだけで完結
* **features_static**：規模・流動性等（補正の主役）
  サイズ調整・見送り判定にのみ使用（価格計算には混ぜない）
* **features_fundamental**：財務・バリュエーション等（評価の拡張）
  ML評価へ段階導入（daily→+static→+fundamental）

---

## 6. パイプライン（全体像）

EODバッチは以下の順で一方向に進みます。

1. Universe確定（市場別）
2. yfinance取得（OHLCV中心）
3. 特徴量生成（daily/static/fundamentalに分離）
4. 市場環境判定（リスクオン/オフ等）
5. 候補抽出（dailyのみ）
6. 計画候補（plan_args）列挙
7. 実行値生成（Entry/Stop/Target/Size：dailyのみ）
8. 補正（staticでサイズ/可否のみ）
9. 信用度推定（ML：段階導入）
10. 最良案選択
11. BUY判定（YES/YES_HALF/NO）
12. 短文生成（LLM：説明と監査のみ）
13. 配信/保存

---

## 7. フェイルセーフ（運用品質）

* LLM障害：DecisionCoreのみ配信
* ML不調：YES→YES_HALF/NOに寄せる（保守運用）
* データ欠損：銘柄除外＋warnings
* フォーマット違反：Linterで強制修正

---

## 8. 運用

* **日次（EOD）**：JP/US別に実行し、上位N銘柄をランキング配信
* **週次/月次**：成績集計→モデル再学習/校正→PlanCatalog/閾値見直し（変更はバージョン管理）

---

## 9. リポジトリ構成（推奨）

* `schemas/`：UserPolicy / DecisionCore / DecisionPack
* `catalog/`：plan_catalog.json / vocabulary.json
* `pipeline/`：各ステップ（loader/features/selector/execution/…）
* `models/`：学習・推論・校正・評価
* `prompts/`：LLM層（validator/labeler/writer/linter）
* `reports/`：メール/Markdown生成

---

## 10. 免責

本ツールは投資助言ではありません。最終判断および損益はユーザーが負います。
