export interface RuleNoteRecord {
  note_key: string;
  chat_id: string;
  note_text: string;
  rule_kb_item_id?: string | null;
  rule_text?: string;
  plan_item_id?: string | null;
  evidence_record_id?: string | null;
  verification_timestamp?: string | null;
  verification_index?: number | null;
  source?: string;
  verdict?: string | null;
  explanation?: string;
  created_at?: string;
  updated_at?: string;
}

interface RuleNoteKeyInput {
  source: string;
  itemId?: string | null;
  ruleKbItemId?: string | null;
  ruleText?: string;
  evidenceRecordId?: string | null;
  timestamp?: string | null;
  index?: number;
}

function sanitize(value: string): string {
  const s = (value || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return s || "na";
}

function hashText(input: string): string {
  let hash = 2166136261;
  const text = input || "";
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

export function createRuleNoteKey(input: RuleNoteKeyInput): string {
  if (input.evidenceRecordId) {
    return `rn__evidence__${sanitize(input.evidenceRecordId)}`;
  }
  const source = sanitize(input.source || "rule-verification");
  const item = sanitize(input.itemId || "no-item");
  const rulePart = input.ruleKbItemId ? sanitize(input.ruleKbItemId) : `txt-${hashText(input.ruleText || "")}`;
  const ts = sanitize(input.timestamp || "no-ts");
  const idx = String(input.index ?? 0);
  return `rn__${source}__${item}__${rulePart}__${ts}__${idx}`;
}

export function toRuleNoteRecord(
  chatId: string,
  noteKey: string,
  noteText: string,
  meta: Omit<RuleNoteRecord, "note_key" | "chat_id" | "note_text">
): RuleNoteRecord {
  return {
    note_key: noteKey,
    chat_id: chatId,
    note_text: noteText,
    ...meta,
  };
}
