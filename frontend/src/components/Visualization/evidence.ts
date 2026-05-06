export interface EvidenceArtifact {
  file_path?: string;
  line_range?: string;
  code_snippet?: string;
  annotation?: string;
}

export interface EvidenceTest {
  name?: string;
  command?: string;
  result?: string;
  output?: string;
  test_file?: string;
  test_code?: string;
  enabled?: boolean;
}

export interface EvidenceRecord {
  record_id: string;
  chat_id: string;
  item_id?: string | null;
  rule_kb_item_id?: string | null;
  rule_category: string;
  rule_text: string;
  rule_source: string;
  source_title: string;
  is_inherited: boolean;
  source: string;
  explanation: string;
  detected_evidence: string;
  item_detected_evidence?: string;
  artifacts: EvidenceArtifact[];
  tests?: EvidenceTest | null;
  verdict: string;
  timestamp: string;
  record_index: number;
  raw_rule_result?: Record<string, unknown> | null;
}

export function normalizeRuleText(value: string): string {
  return (value || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

export function makeEvidenceRuleKey(ruleLike: { rule_kb_item_id?: string | null; kb_item_id?: string | null; rule_text?: string; text?: string; content?: string }): string {
  const kbItemId = ruleLike.rule_kb_item_id || ruleLike.kb_item_id;
  if (kbItemId) return `kb:${kbItemId}`;
  return `txt:${normalizeRuleText(ruleLike.rule_text || ruleLike.text || ruleLike.content || '')}`;
}

export function getRuleVerificationRecordsForItem(
  evidence: EvidenceRecord[],
  itemId: string,
  ruleLike: { kb_item_id?: string | null; rule_kb_item_id?: string | null; text?: string; rule_text?: string; content?: string }
): EvidenceRecord[] {
  const targetKey = makeEvidenceRuleKey(ruleLike);
  return evidence.filter(
    (record) =>
      record.source === 'rule-verification' &&
      String(record.item_id || '') === String(itemId) &&
      makeEvidenceRuleKey(record) === targetKey
  );
}

export function getLatestAutoEnforcementForItem(
  evidence: EvidenceRecord[],
  itemId: string
): { lastEnforced: string; detectedEvidence: string; records: EvidenceRecord[] } | null {
  const autoRecords = evidence.filter(
    (record) => record.source === 'auto-enforcement' && String(record.item_id || '') === String(itemId)
  );
  if (!autoRecords.length) return null;

  const lastEnforced = autoRecords.reduce((latest, record) =>
    String(record.timestamp || '') > latest ? String(record.timestamp || '') : latest,
  '');
  const records = autoRecords.filter((record) => String(record.timestamp || '') === lastEnforced);
  const detectedEvidence =
    records.find((record) => (record.item_detected_evidence || '').trim())?.item_detected_evidence ||
    records.find((record) => (record.detected_evidence || '').trim())?.detected_evidence ||
    '';
  return { lastEnforced, detectedEvidence, records };
}

