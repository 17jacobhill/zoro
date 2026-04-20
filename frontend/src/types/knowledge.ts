export interface KnowledgeItem {
  item_id: string;
  type: 'rule' | 'doc';
  category: string;
  title: string;
  content: string;
  context?: string | null;
  evidence?: string | null;
  confidence?: number;
  decay?: number;
  confidence_reasoning?: string | null;
  decay_reasoning?: string | null;
  source_file: string;
  usage_count: number;
  is_favorite: boolean;
  is_strict?: boolean;
  is_testable?: boolean;
  created_at: string;
}

export interface DuplicateSuggestion {
  suggestion_id: string;
  item_ids: string[];
  items: KnowledgeItem[];
  similarity_score: number;
  reasoning: string;
  suggested_merged: string;
  merged_title?: string;
  merged_context?: string | null;
  merged_evidence?: string | null;
  is_conflict?: boolean;
  merged_confidence?: number;
  merged_decay?: number;
  scoring_explanation?: string;
  dismissed: boolean;
}

export interface FileInfo {
  filename: string;
  total_items: number;
  processed: number;
  pending: number;
  path: string;
}

export interface MergeSuggestion {
  suggestion_id: string;
  merge_from: string[];
  merge_to: string;
  reasoning: string;
  dismissed: boolean;
}

export interface Category {
  name: string;
  item_count: number;
}

export interface ProcessResult {
  filename: string;
  success: boolean;
  items_added?: number;
  error?: string;
}
