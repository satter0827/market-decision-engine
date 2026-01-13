| 大リリース（Major） | 目的（外面の節目） | 小リリース（Minor） | DoD（使える状態） | 主な機能 |
| - | - | - | - | - |
| M1 | **CLIで発注可能な数値が出る** | m1.1 最小E2E | CLIで「銘柄・YES/NO・Entry/Stop/Size」が出る | Universe固定 / yfinance OHLCV / features_daily最小 / Candidate最小 / Execution最小 / 画面出力 |
| | | m1.2 発注パック固定 | Target(2R/3R), MaxLoss, TimeStop が出る | DecisionCore拡張 / 丸め・単位（概念） |
| | | m1.3 実行設定（UserPolicy最小） | policyで閾値・リスク%を変えられる | UserPolicy(JSON)最小 + バリデーション |
| M2 | **落ちない・残る（運用土台）** | m2.1 例外耐性 | 欠損で落ちず銘柄単位で継続 | 欠損/異常値検出 / 銘柄スキップ / warnings |
| | | m2.2 キャッシュ | 再実行が速い | キャッシュ層 / 更新判定 |
| | | m2.3 保存 | Decision Packが日次でファイル保存される | JSON/CSV/Parquet保存 / 実行メタ保存 |
| M3 | **候補抽出の品質を上げる（daily強化）** | m3.1 features_daily拡充 | 候補が安定して“それっぽい” | RS/レンジ位置/ギャップ頻度など |
| | | m3.2 Candidate強化 | 上位Nがより再現性ある条件で選ばれる | ブレイク＋出来高＋除外条件 |
| | | m3.3 ランキング（ルール） | ルールスコアで並ぶ | plan_score（ルール合成） / tie-break |
| M4 | **市場環境で新規を制御できる** | m4.1 Regime導入 | リスクオフ時に新規が抑制される | 指数トレンド/ボラ判定 |
| | | m4.2 Regime連動 | YES→NO/YES_HALFへ寄せる | ルール連動（簡易） |
| M5 | **事故率低減：static補正と制約** | m5.1 static最小 | 低流動性/小型でサイズが落ちる/NO | marketCap/avgVolume/sector取得 |
| | | m5.2 Risk/Sizing Adjuster | Entry/Stopは変えずサイズ/可否だけ補正 | SizeModifier / Eligibility |
| | | m5.3 ポートフォリオ制約 | 同時保有数・集中上限が効く | PortfolioPolicy / YES→YES_HALF導入 |
| M6 | **読む負担を減らす（説明の外面改善）** | m6.1 LLM要約 | 最大3文＋If-Thenが付く | AI Layer（翻訳器） |
| | | m6.2 固定語彙profile | 読むべき観点が揃う | vocabulary / profileラベル |
| | | m6.3 Linter強化 | 規約違反が出ない | フォーマット監査・テンプレ化 |
| M7 | **信用度（ML）を段階導入できる** | m7.1 ML v1（dailyのみ） | p_success/ev_r/uncertaintyが出る | 学習/推論分離 / 縮退運用 |
| | | m7.2 ML v2（+static） | 安定性が上がる | 入力拡張 / 校正（最低限） |
| | | m7.3 fundamental条件付き | 追加しても壊れない | 欠損管理 / asof不明は除外 |
| M8 | **改善ループ（週次/月次の外側運用）** | m8.1 週次サマリ | 勝率/EV/DD/分布が出る | 集計レポート |
| | | m8.2 ヘルス監視 | 劣化が検知できる | ドリフト/校正監視 |
| | | m8.3 再学習手順化 | 更新が追跡できる | 版管理 / 再学習パイプライン |
| M9（任意） | **通知（メール）** | m9.1 メール送信 | EOD後に届く | テンプレ/添付 |
| | | m9.2 配信最適化 | 見やすい | サマリ+添付形式 |
