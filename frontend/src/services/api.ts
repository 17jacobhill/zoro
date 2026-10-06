import axios from 'axios';
import type { FileInfo } from '../types/knowledge';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://localhost:5010/api';

export interface ChatVisualization {
  chat_id: string;
  name?: string;
  chat_file_path: string;
  status: string;
  last_polled_at?: string;
}

export interface VisualizationPlanDocument {
  plan: {
    title?: string;
    description?: string;
    items: any[];
  };
  rules_retrieved?: boolean;
  plan_tracking?: Record<string, string>;
}

export const api = {
  getChatVisualizations: async (): Promise<ChatVisualization[]> => {
    const response = await axios.get(`${API_BASE}/chat-visualizations`);
    return response.data;
  },

  getChatVisualization: async (chatId: string): Promise<ChatVisualization> => {
    const response = await axios.get(`${API_BASE}/chat-visualizations/${chatId}`);
    return response.data;
  },

  createChatVisualization: async (): Promise<ChatVisualization> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations`);
    return response.data;
  },

  updateChatVisualization: async (chatId: string, name: string): Promise<ChatVisualization> => {
    const response = await axios.put(`${API_BASE}/chat-visualizations/${chatId}`, { name });
    return response.data;
  },

  startChatVisualization: async (chatId: string): Promise<ChatVisualization> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/start`);
    return response.data;
  },

  pauseChatVisualization: async (chatId: string): Promise<ChatVisualization> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/pause`);
    return response.data;
  },

  pollChatVisualization: async (chatId: string): Promise<{ status: string; content: string | null }> => {
    const response = await axios.get(`${API_BASE}/chat-visualizations/${chatId}/poll`);
    return response.data;
  },

  deleteChatVisualization: async (chatId: string): Promise<void> => {
    await axios.delete(`${API_BASE}/chat-visualizations/${chatId}`);
  },

  getVisualizationPlan: async (
    chatId: string
  ): Promise<{ success: boolean; plan: VisualizationPlanDocument | null }> => {
    const response = await axios.get(`${API_BASE}/chat-visualizations/${chatId}/plan`);
    return response.data;
  },

  bootstrapVisualizationPlan: async (
    chatId: string,
    content?: string
  ): Promise<{
    success: boolean;
    plan: VisualizationPlanDocument | null;
    plan_detected?: boolean;
    rules_applied?: boolean;
    rules_attached_count?: number;
    rule_retrieval_source?: string;
    warnings?: string[];
    error?: string;
  }> => {
    const payload = content ? { content } : {};
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/bootstrap-plan`, payload);
    return response.data;
  },

  prepareVisualizationForPlay: async (
    chatId: string,
    content?: string
  ): Promise<{
    success: boolean;
    plan: VisualizationPlanDocument | null;
    play_action?: 'extract_plan' | 'enrich_plan' | 'sync_chat_only';
    plan_detected?: boolean;
    rules_applied?: boolean;
    rules_attached_count?: number;
    rule_retrieval_source?: string;
    warnings?: string[];
    error?: string;
  }> => {
    const payload = content ? { content } : {};
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/prepare-play`, payload);
    return response.data;
  },

  getRuleNotes: async (chatId: string): Promise<{ success: boolean; notes: Record<string, any>; error?: string }> => {
    const response = await axios.get(`${API_BASE}/chat-visualizations/${chatId}/rule-notes`);
    return response.data;
  },

  updateRuleNotes: async (
    chatId: string,
    notes: Record<string, any>
  ): Promise<{ success: boolean; notes: Record<string, any>; error?: string }> => {
    const response = await axios.put(`${API_BASE}/chat-visualizations/${chatId}/rule-notes`, { notes });
    return response.data;
  },

  getEvidence: async (
    chatId: string
  ): Promise<{ success: boolean; evidence: any[]; error?: string }> => {
    const response = await axios.get(`${API_BASE}/chat-visualizations/${chatId}/evidence`);
    return response.data;
  },

  getSupervision: async (chatId: string): Promise<{
    success: boolean;
    supervision_history: any[];
    token_stats: {
      current_tokens: number;
      last_supervised_tokens: number;
      tokens_since_last: number;
      threshold: number;
      progress_percent: number;
    };
  }> => {
    const response = await axios.get(`${API_BASE}/visualization/supervision/${chatId}`);
    return response.data;
  },

  superviseChatVisualization: async (chatId: string): Promise<{
    supervision: any;
    total_tokens: number;
    supervised_tokens: number;
    remaining_tokens: number;
    all_supervised: boolean;
    error?: string;
  }> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/supervise`);
    return response.data;
  },

  resolveSupervision: async (
    chatId: string,
    timestamp: string
  ): Promise<{ success: boolean; error?: string }> => {
    const response = await axios.post(`${API_BASE}/visualization/supervision/${chatId}/resolve`, { timestamp });
    return response.data;
  },

  getRuleLearning: async (chatId: string): Promise<{
    success: boolean;
    rules: any[];
    analyzed_tokens: number;
    analyzed_from_token?: number;
    analyzed_to_token?: number;
    remaining_tokens?: number;
    total_clean_tokens?: number;
    all_analyzed?: boolean;
    can_analyze_more?: boolean;
    updated_at?: string;
  }> => {
    const response = await axios.get(`${API_BASE}/visualization/rule-learning/${chatId}`);
    return response.data;
  },

  analyzeChatVisualization: async (chatId: string): Promise<{
    success: boolean;
    rules: any[];
    analyzed_tokens: number;
    analyzed_from_token: number;
    analyzed_to_token: number;
    remaining_tokens: number;
    total_clean_tokens: number;
    all_analyzed: boolean;
    updated_at?: string;
  }> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/analyze`);
    return response.data;
  },

  enforceItem: async (chatId: string, itemId: string): Promise<{
    success: boolean;
    enforcement: any;
    error?: string;
  }> => {
    const response = await axios.post(`${API_BASE}/visualization/${chatId}/enforce-item/${itemId}`);
    return response.data;
  },

  getEnforcementHistory: async (chatId: string) => {
    const response = await axios.get(`${API_BASE}/visualization/enforcement-history/${chatId}`);
    return response.data;
  },

  getConfig: async (): Promise<{ success: boolean; config: any }> => {
    const response = await axios.get(`${API_BASE}/config`);
    return response.data;
  },

  getProjectRoot: async (): Promise<{ success: boolean; path?: string; error?: string }> => {
    const response = await axios.get(`${API_BASE}/project-root`);
    return response.data;
  },

  setProjectRoot: async (path: string): Promise<{ success: boolean; path?: string; error?: string }> => {
    const response = await axios.post(`${API_BASE}/project-root`, { path });
    return response.data;
  },

  resolveConflict: async (
    chatId: string,
    itemId: string,
    conflictId: string,
    chosenRuleIndex: number
  ): Promise<{
    success: boolean;
    remaining_conflicts: number;
    item_id: string;
    conflict_id: string;
  }> => {
    const response = await axios.post(
      `${API_BASE}/chat-visualizations/${chatId}/resolve-conflict`,
      {
        item_id: itemId,
        conflict_id: conflictId,
        chosen_rule_index: chosenRuleIndex,
      }
    );
    return response.data;
  },

  fetchPendingFiles: async (): Promise<{
    files: FileInfo[];
    total_pending: number;
    total_pending_files?: number;
    total_pending_chunks?: number;
    total_unprocessed_percent?: number;
  }> => {
    const response = await axios.get(`${API_BASE}/kb/files/unstructured/count`);
    return response.data;
  },

  processKBFiles: async (files: string[]): Promise<{
    success: boolean;
    results: Array<{
      filename: string;
      success: boolean;
      items_added: number;
      newly_added_ids: string[];
      pre_count?: number;
      post_count?: number;
      processed_path?: string;
      error?: string;
    }>;
    total_added: number;
    newly_added_ids: string[];
  }> => {
    const response = await axios.post(`${API_BASE}/kb/process`, { files });
    return response.data;
  },

  importRepoAgents: async (
    filename = 'AGENTS.md'
  ): Promise<{
    success: boolean;
    filename: string;
    items_added: number;
    newly_added_ids: string[];
    replaced_previous_count?: number;
    processed_path?: string;
    message?: string;
    error?: string;
  }> => {
    const response = await axios.post(`${API_BASE}/kb/files/import-agents`, { filename });
    return response.data;
  },

  fetchKBItems: async (filters?: {
    category?: string;
    type?: string;
    search?: string;
    favorites?: boolean;
  }): Promise<{ success: boolean; items: any[]; count: number }> => {
    const params = new URLSearchParams();
    if (filters?.category) params.append('category', filters.category);
    if (filters?.type) params.append('type', filters.type);
    if (filters?.search) params.append('search', filters.search);
    if (filters?.favorites) params.append('favorites', 'true');

    const query = params.toString();
    const response = await axios.get(`${API_BASE}/kb/items${query ? `?${query}` : ''}`);
    return response.data;
  },

  fetchKBCategories: async (): Promise<{ success: boolean; categories: any[] }> => {
    const response = await axios.get(`${API_BASE}/kb/categories`);
    return response.data;
  },

  suggestCategoryMerges: async (): Promise<{ success: boolean; suggestions: any[] }> => {
    const response = await axios.get(`${API_BASE}/kb/categories/suggest-merges`);
    return response.data;
  },

  acceptCategoryMerge: async (
    mergeFrom: string[],
    mergeTo: string
  ): Promise<{ success: boolean; updated_items: number; merge_from: string[]; merge_to: string }> => {
    const response = await axios.post(`${API_BASE}/kb/categories/accept`, {
      merge_from: mergeFrom,
      merge_to: mergeTo,
    });
    return response.data;
  },

  dismissCategoryMerge: async (suggestionId: string): Promise<{ success: boolean; suggestion_id: string }> => {
    const response = await axios.post(`${API_BASE}/kb/categories/dismiss`, {
      suggestion_id: suggestionId,
    });
    return response.data;
  },

  createKBItem: async (data: any): Promise<{ success: boolean; item: any }> => {
    const response = await axios.post(`${API_BASE}/kb/items`, data);
    return response.data;
  },

  updateKBItem: async (itemId: string, data: any): Promise<{ success: boolean; item: any }> => {
    const response = await axios.patch(`${API_BASE}/kb/items/${itemId}`, data);
    return response.data;
  },

  deleteKBItem: async (itemId: string): Promise<{ success: boolean }> => {
    const response = await axios.delete(`${API_BASE}/kb/items/${itemId}`);
    return response.data;
  },

  detectDuplicates: async (category?: string): Promise<{ success: boolean; duplicates: any[] }> => {
    const response = await axios.post(`${API_BASE}/kb/duplicates/detect`, { category });
    return response.data;
  },

  mergeDuplicates: async (
    itemIds: string[],
    mergedContent: string,
    mergedTitle: string,
    mergedConfidence?: number,
    mergedDecay?: number,
    scoringExplanation?: string,
    isConflict?: boolean
  ) => {
    const response = await axios.post(`${API_BASE}/kb/duplicates/merge`, {
      item_ids: itemIds,
      merged_content: mergedContent,
      merged_title: mergedTitle,
      merged_confidence: mergedConfidence,
      merged_decay: mergedDecay,
      scoring_explanation: scoringExplanation,
      is_conflict: isConflict,
    });
    return response.data;
  },

  refineRule: async (data: {
    rule_type: 'rule' | 'doc';
    category: string;
    title: string;
    content: string;
    context: string | null;
    evidence: string | null;
  }): Promise<{
    success: boolean;
    refined?: {
      title: string;
      content: string;
      confidence: number;
      decay: number;
      confidence_reasoning: string;
      decay_reasoning: string;
      context: string | null;
      evidence: string | null;
    };
    error?: string;
  }> => {
    const response = await axios.post(`${API_BASE}/kb/items/refine`, data);
    return response.data;
  },

  getFavorites: async () => {
    const response = await axios.get(`${API_BASE}/kb/favorites`);
    return response.data;
  },

  createManualFavorite: async (data: {
    rule: string;
    reasoning: string;
    category?: string;
    title?: string;
    context?: string | null;
    evidence?: string | null;
    confidence?: number;
    decay?: number;
    confidence_reasoning?: string | null;
    decay_reasoning?: string | null;
    is_strict?: boolean;
    is_testable?: boolean;
  }) => {
    const response = await axios.post(`${API_BASE}/kb/favorites/manual`, data);
    return response.data;
  },

  toggleFavorite: async (itemId: string, isFavorite: boolean) => {
    const response = isFavorite
      ? await axios.post(`${API_BASE}/kb/favorites`, { item_id: itemId })
      : await axios.delete(`${API_BASE}/kb/favorites/${itemId}`);
    return response.data;
  },

  deletePlanItem: async (chatId: string, itemId: string): Promise<{ success: boolean }> => {
    const response = await axios.delete(`${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}`);
    return response.data;
  },

  addPlanItem: async (
    chatId: string,
    data: {
      parent_id?: string;
      title: string;
      description?: string;
      position?: number;
    }
  ): Promise<{ success: boolean; item: any }> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/plan/items`, data);
    return response.data;
  },

  updatePlanItem: async (
    chatId: string,
    itemId: string,
    data: { title?: string; description?: string }
  ): Promise<{ success: boolean; item: any }> => {
    const response = await axios.put(`${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}`, data);
    return response.data;
  },

  movePlanItem: async (
    chatId: string,
    itemId: string,
    direction: 'up' | 'down'
  ): Promise<{ success: boolean; item_id: string; from_index: number; to_index: number }> => {
    const response = await axios.post(
      `${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}/move`,
      { direction }
    );
    return response.data;
  },

  updateVisualizationPlan: async (
    chatId: string,
    data: { title?: string; description?: string }
  ): Promise<{ success: boolean; plan: any }> => {
    const response = await axios.put(`${API_BASE}/chat-visualizations/${chatId}/plan`, data);
    return response.data;
  },

  deletePlanItemRule: async (
    chatId: string,
    itemId: string,
    ruleIndex: number
  ): Promise<{ success: boolean }> => {
    const response = await axios.delete(
      `${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}/rules/${ruleIndex}`
    );
    return response.data;
  },

  addPlanItemRule: async (
    chatId: string,
    itemId: string,
    data: {
      kb_item_id?: string;
      category?: string;
      text?: string;
      context?: string;
      evidence?: string;
      confidence?: number;
      decay?: number;
      confidence_reasoning?: string;
      decay_reasoning?: string;
    }
  ): Promise<{ success: boolean; rule: any }> => {
    const response = await axios.post(
      `${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}/rules`,
      data
    );
    return response.data;
  },

  movePlanItemRule: async (
    chatId: string,
    itemId: string,
    ruleIndex: number,
    data: {
      source_type: 'own' | 'inherited';
      direction: 'up' | 'down' | 'adopt';
      target_item_id?: string;
    }
  ): Promise<{ success: boolean; moved_rule: any; from_item_id: string; to_item_id: string }> => {
    const response = await axios.post(
      `${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}/rules/${ruleIndex}/move`,
      data
    );
    return response.data;
  },

  toggleRuleStrictEnforcement: async (
    chatId: string,
    itemId: string,
    ruleIndex: number,
    enabled: boolean
  ): Promise<{ success: boolean; rule: any }> => {
    const response = await axios.put(
      `${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}/rules/${ruleIndex}/strict-enforcement`,
      { enabled }
    );
    return response.data;
  },

  toggleRuleTestable: async (
    chatId: string,
    itemId: string,
    ruleIndex: number,
    enabled: boolean
  ): Promise<{ success: boolean; rule: any }> => {
    const response = await axios.put(
      `${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}/rules/${ruleIndex}/testable`,
      { enabled }
    );
    return response.data;
  },

  refineSubsteps: async (
    chatId: string,
    itemId: string,
    guidance: string
  ): Promise<{ success: boolean; phase: any; error?: string }> => {
    const response = await axios.post(
      `${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}/refine-substeps`,
      { guidance }
    );
    return response.data;
  },
};
