import type { SummaryReport } from '@/api/commission/types';

/**
 * サマリ JSON から自然言語の計算インサイトを生成する (LLM 不使用、テンプレート整形)。
 *
 * 出力は段落のリスト。ResultPage の「インサイト」カードに表示する。
 */
export function generateInsight(summary: SummaryReport): string[] {
  const lines: string[] = [];
  const rate = (summary.auto_completion_rate * 100).toFixed(1);
  const topPartner = summary.by_partner[0];
  const topProduct = summary.by_product[0];
  const yen = (n: number): string => n.toLocaleString('ja-JP') + ' 円';
  const num = (n: number): string => n.toLocaleString('ja-JP');

  // 1. 概要
  lines.push(
    `売上明細 ${num(summary.total_records)} 件を取引条件マスタと突合した結果、` +
      `${num(summary.auto_completed)} 件 (${rate}%) が自動計算されました。` +
      `合計手数料は ${yen(summary.total_commission_amount)} です。`
  );

  // 2. トップ取引先
  if (topPartner && topPartner.total > 0) {
    lines.push(
      `自動計算された手数料はすべて「${topPartner.name}」分で、${topPartner.count} 件 / ${yen(topPartner.total)} を計上しました。` +
        `これはアップロードした取引条件マスタにこの取引先のみが登録されていたためです。`
    );
  }

  // 3. HITL の説明
  if (summary.hitl_pending > 0) {
    lines.push(
      `残り ${num(summary.hitl_pending)} 件はマスタキー不一致または高額アラート (>100,000 円) として ` +
        `HITL (Human-in-the-Loop / 人間確認) 対象になりました。` +
        `マスタにない取引先分や計算結果が閾値を超えるレコードを担当者が個別判断します。` +
        `自動完了率を引き上げるには、他の代理店分の取引条件マスタを統合してから再計算してください。`
    );
  }

  // 4. 計算フロー
  lines.push(
    `計算は以下の手順で実行されました。` +
      `(1) 売上明細の各行から複合キー「取引先コード + 申込月 YYYYMMDD + 商材 + 決済方法」を生成。` +
      `(2) 取引条件マスタを同じキーで Lookup し、ヒットしたら該当行のマスタ値を取得。` +
      `(3) ヒットしたレコードに対し 10 ステップのルールエンジンを順次適用: ` +
      `基本コミッション → ボリュームインセン → 特別コミッション① ② → 25/37ヶ月以降継続 → 紹介制度 → PAP/PAS/PH → QI 分割計上 → 口振初回手数料 → 戻入条件。` +
      `戻入は「ファイル区分が初回出荷ではない」かつ「配送個数が 12 本未満 / 24 本未満」の条件で全額 / 半額のマイナス計上。` +
      `(4) 各ステップの加算金額と判定根拠を calculation_trace に日本語で記録し、明細行をクリックすると展開表示。` +
      `(5) 異常検知ルール (マスタ未ヒット、合計 100,000 円超過、計算エラー) で HITL 対象を抽出。`
  );

  // 5. 商材別の特徴
  if (topProduct && topProduct.total > 0) {
    lines.push(
      `商材別では「${topProduct.name}」が最大の ${yen(topProduct.total)} を計上 ` +
        `(全 ${num(topProduct.count)} 件中、マスタヒット分のみが金額として集計)。` +
        `件数列には「マスタにヒットしなかった同商材の出荷件数」も含まれるため、件数と金額は単純比例しません。`
    );
  }

  // 6. 推奨アクション
  lines.push(
    `次のステップ: ` +
      `(a) HITL タブで未確定レコードを承認 / 却下 / 手動入力で確定、` +
      `(b) 確定後 Excel ダウンロードで明細とサマリの 2 シート構成ファイルを取得、` +
      `(c) 計算ロジックを業務 Excel マクロと突合して差異があれば commission_calculator.py の該当ステップを調整。`
  );

  return lines;
}
