# 販売管理手数料計算エージェント — 引き継ぎドキュメント

このドキュメントは、本プロジェクトのバイブコーディング中に依頼者（Jo）が
Claude Code に出した指示・意思決定を時系列で整理したものです。
引き継ぎ担当者が「なぜこの実装になっているか」を理解するための記録です。

- リポジトリ: https://github.com/KenichiroJo/datarobot-agent-incentive
- ベース: DataRobot 公式テンプレート `datarobot-agent-application`（Agentic Starter / LangGraph）
- 実装期間: 2026-05-21 〜 2026-05-26

---

## 0. プロジェクトの前提（最初の指示文より）

依頼者は `claude_code_prompt_commission_agent_v2.txt` という詳細指示書を提示。
要点:

- **作るもの**: ウォーターサーバー販売代理店向け月次手数料の自動計算 AI エージェント。
  担当者が「売上明細 Excel」と「取引条件マスタ Excel」をアップロード →
  AI が代理店ごとの手数料を計算 → 異常レコードだけ人間が HITL 承認 →
  確定データをダウンロード。
- **守るべきルール**（指示書冒頭）:
  - 起動は `dr run dev` のみ（uvicorn / npm run dev を直接叩かない）
  - ポートは 8080 / 5173 / 8842 / 9000 固定
  - エージェントのメインファイルは `agent/agent/myagent.py`（`MyAgent` クラス）
  - フロントエンドは `@dr-ui` コンポーネントレジストリを使う
  - デプロイは `dr run deploy` のみ
  - 既存ファイルを変更する前に必ず中身を読む
  - 手数料計算は **Pure Python で実装し LLM を使わない**
  - LLM は supervisor ルーティングと explainer の説明生成のみ
  - 全 UI テキストは日本語

---

## 1. 計画フェーズで依頼者が下した決定（AskUserQuestion への回答）

| 質問 | 依頼者の回答 |
|---|---|
| 作業環境 | **ローカルの既存テンプレを修正 → GitHub に push → DataRobot Codespace で pull** |
| 指示書 vs 既存テンプレに差異がある場合 | **既存テンプレ規約を優先** |
| 既存チャット UI | **残して計算画面と共存** |
| 計算ロジックの詳細仕様 | **サンプル Excel を後ほどアップロードするので確認しながら** |

その後の追加指示:
- GitHub リポジトリは `https://github.com/KenichiroJo/datarobot-agent-incentive.git`
- **既存テンプレートを完全に上書きして OK**（force push 許可）
- `.env` は DataRobot Codespace の `dr start` が自動設定する。LLM は DataRobot LLM Gateway
- **バックエンドエージェントの出力は JSON で行う**
- **ファイル出力は Excel 形式で**（指示書の CSV から変更）

---

## 2. サンプルデータ提供（依頼者がアップロード）

3 ファイルを Downloads 経由で提供:

1. `202603売上明細サンプルデータ_商材サーバー_20260518.xlsx`
   — 売上明細 8,149 行 × 192 列（シート `ALL`）
2. `取引条件一覧サンプル_フォーカスタマーズ_20260518.xlsx`
   — 取引条件マスタ 828 行 × 55 列（シート `Sheet1`、フォーカスタマーズ 1 社分）
3. `明細全体像_260519.xlsx`
   — 業務フロー全体図（テキストボックスの図形）。
   我々のエージェントが担当するのは「明細統合・手数料計算」工程と判明。

### 計算方針の決定（依頼者の回答）
- 売上明細に既存の計算済み値があるが、**マスタを参照して再計算する**
  （現在の業務も必ずマスタを参照しているため）。

---

## 3. 実装の主要な意思決定（指示書 vs 実装の差異）

依頼者が「既存テンプレ規約を優先」と決めたため、指示書の記述を以下のように読み替え:

| 項目 | 指示書 | 実際の実装 | 理由 |
|---|---|---|---|
| API prefix | `/api/commission/...` | `/api/v1/commission/...` | 既存 chat/auth ルーターに合わせた |
| ルーター配置 | `fastapi_server/routers/commission.py` | `fastapi_server/app/api/v1/commission.py` | 既存階層構造 |
| UI ライブラリ | `@dr-ui` | 既存 `components/ui/`（Radix UI ラッパー）| `@dr-ui` は DataRobot の shadcn レジストリで、パッケージとしては存在しない |
| 状態管理 | React Context のみ | Zustand + immer + React Query | 既にテンプレに導入済み |
| 計算ロジックの配置 | `agent/agent/tools/` | **`fastapi_server/app/commission_engine/`** | 後述の依存衝突を回避するため |
| LLM 利用 | supervisor / explainer で使用 | **LLM 不使用のルールベース** | 後述の依存衝突を回避するため |

---

## 4. 途中で発生した問題と依頼者の対応

### 問題 1: GitHub リポジトリに既存テンプレートが入っていた
→ 依頼者が「**完全に上書きして OK**」と判断。force push で対応。

### 問題 2: openai バージョン衝突（Codespace の install で発覚）
- `datarobot-genai[langgraph]>=0.15.53` が `openai>=2.0` を要求
- 既存 `core` パッケージは `openai<2` を要求 → 解決不能
- **対応**: `datarobot-genai` 依存を削除し、`langgraph` + `langchain-core` を直接依存に。
  LangGraph の supervisor / explainer ノードを LLM 不使用のルールベースに書き換え
  （手数料計算自体は元々 Pure Python なので影響なし）。
- 結果として「計算は fastapi_server プロセスで完結、agent パッケージは
  既存チャット用 MyAgent のまま」という構成に。

### 問題 3: Taskfile が見つからない
→ `Taskfile.yml` は `dr task compose` で生成する動的ファイル（.gitignore 対象）。
  Codespace で `dr task compose` を実行して解決。

### 問題 4: 計算が進まない（SSE が届かない）
- React StrictMode のダブルマウントで `AbortController.abort()` が
  SSE 接続を即座に中断していた。
- **対応**: CalculatePage の AbortController を削除し fire-and-forget に変更。

---

## 5. 動作確認後に依頼者が出した改善指示

### 5-1. 計算結果の検証依頼
「これ合ってる？」→ 数字の内部整合性を確認（8,149 = 自動完了 61 + HITL 8,088、
合計 2,390,750 円）。フォーカスタマーズ 1 社分のみマスタにあるためヒット率 0.7%。

### 5-2. UI 改善 4 点（まとめて依頼）
1. **計算インサイトの自然言語説明** → `lib/commission-insight.ts` で生成、ResultPage に表示
2. **KPI ラベル修正**「HITL 確定」→「HITL 対象」（実態は未確定のため）
3. **商材別件数の意味を tooltip で説明**（件数=全レコード, 合計=ヒット分のみ）
4. **ResultPage のデフォルトフィルタを「すべて」に変更**（ReviewPage 未経由でも明細表示）

### 5-3. チュートリアル機能の追加依頼
「エージェントを開いたときにチュートリアルを出したい。画面が遷移して、
操作すべき場所が明るく、他はグレイアウトする、かっこいい感じ」
→ **driver.js** を採用。
  - `lib/tour-steps.ts`（ツアー定義）
  - `components/tutorial/useTutorialTour.ts`（フック）
  - `components/tutorial/TutorialLauncher.tsx`（起動ボタン）
  - 各ページに `data-tour="..."` 属性を付与
  - 初回自動起動 + localStorage で完了フラグ管理 + サイドバーに再起動ボタン

---

## 6. 現在の実装状態

### バックエンド（fastapi_server）
- `app/commission_engine/` — Pure Python 計算ロジック + LangGraph グラフ（6 ノード）
  - `excel_parser.py` — parse_sales_excel / parse_master_excel（複合キー生成）
  - `commission_calculator.py` — 10 ステップのルールエンジン
  - `anomaly_detector.py` — HITL 対象抽出
  - `report_generator.py` — 取引先別 / 商材別集計
  - `graph.py` — supervisor/data_parser/calculator/hitl_review/approve/explainer
  - `schemas.py` / `state.py`
- `app/commission/` — session_store / graph_driver / schemas（API 層）
- `app/api/v1/commission.py` — 6 エンドポイント
- `tests/test_commission_calculator.py` — 8 単体テスト

### フロントエンド（frontend_web）
- `pages/commission/` — Dashboard / Upload / Calculate / Review / Result
- `components/commission/` — Stepper / KpiCard / DropZone / AnomalyTable / FloatingApprovePanel
- `components/tutorial/` — チュートリアル（driver.js）
- `api/commission/` — api-requests / hooks / types
- `stores/commissionStore.ts` — Zustand
- `lib/commission-insight.ts` — インサイト生成

---

## 7. 未確定・要対応事項（次の担当者へ）

1. **計算式の細部は MVP 推定**。実運用の業務 Excel マクロと突合して検証が必要。
   特に以下は暫定仕様:
   - 戻入ロジック: 「ファイル区分に "初回" を含む → 戻入スキップ」
   - QI 分割: 「QI 適用範囲 ÷ 分割計上期間」で月按分
   - 25/37ヶ月以降継続、PAP/PAS/PH の発動条件
2. **マスタは複数社分の統合が前提**。サンプルはフォーカスタマーズ 1 社のみで
   ヒット率 0.7%。実運用では全代理店のマスタをマージして投入する。
3. **LLM 連携は未実装**（依存衝突回避のため見送り）。explainer の自然言語生成を
   LLM 化する余地あり。
4. **セッションはインメモリ**（プロセス再起動で消失）。本番化時は sqlmodel テーブルへ移行。
5. **`dr run deploy` は未実施**。動作確認は Codespace の `dr run dev` まで。
6. **HITL 異常閾値は固定 100,000 円**。商材別に動的化する余地あり。
7. **大容量時のトレース圧縮**: 2 万行超では確定済み（異常なし）レコードの
   `calculation_trace` を末尾 1 行に圧縮している（メモリ対策）。HITL 対象は全保持。
8. **アップロード上限**: コード側はストリーミングで対応済みだが、DataRobot の
   notebook プロキシに固有のリクエストサイズ上限がある場合は別途要確認。

---

## 8. 起動手順（Codespace）

```sh
cd ~/storage/datarobot-agent-incentive
git pull origin main
dr task compose                      # Taskfile.yaml 生成（初回のみ）
dr task run agent:install
dr task run fastapi_server:install
dr task run frontend_web:install
dr run dev
```

---

## 9. 大容量ファイル対応（2026-06 追加実装）

**背景**: 138MB 以降の xlsx で「supervisor 完了」の直後に固まる事象。原因は
data_parser 工程で ①openpyxl のメモリ肥大 + ②同期パースがイベントループを塞ぎ
SSE 進捗が流れないこと。

**対応（`fastapi_server` のみ、計算式は不変）**:
- **パーサを openpyxl `read_only` ストリーミングに変更**（`pandas.read_excel` を廃止）。
  さらに計算に不要な列を捨て、`raw` も保持しない → メモリを大幅削減。
  `excel_parser.py` の `parse_sales_excel/parse_master_excel` は `progress_cb` 対応。
- **パース・計算を別スレッド実行**（`graph_driver.py` の `_run_blocking_with_progress`、
  `run_in_executor` + thread-safe `asyncio.Queue`）→ イベントループを塞がず、
  行数ベースの進捗が SSE でリアルタイムに流れる。
- **アップロードをチャンク書き込み**（`session_store.add_file_streaming`）→
  数百 MB を一度に RAM へ載せない。
- **アーキテクチャ変更**: 計算パスから **LangGraph を撤去**。interrupt/checkpointer は
  ハング要因かつ大容量スレッド処理と相性が悪いため、`run_calculate` が
  パース→計算→異常検知→集計を直接オーケストレーションし、結果をセッションストアへ
  直書き。HITL 承認は `commission_engine/hitl.py::apply_hitl_decisions` で
  計算結果へ直接適用する方式に簡素化。`graph.py`/`state.py` は削除。
  （※元指示書の「LangGraph 6 ノード」設計からは意図的に逸脱。ロバスト性を優先）

**検証済み**: サンプル（3.2MB / 8,149 行）で従来と完全一致
（マスタ 828 / ヒット 61 / 合計 ¥2,390,750）、パース 1.1 秒。
300MB 級の実地確認は Codespace で要実施。

ブラウザで frontend URL（`/notebook-sessions/.../ports/5173`）を開く。
