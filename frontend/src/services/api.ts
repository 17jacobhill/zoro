import axios from 'axios';

const API_BASE = 'http://localhost:5001/api';

export interface Task {
  task_id: string;
  description: string;
  suggested_type?: string;
  type?: string;
  raw_data?: string;
  messages?: any[];
}

export interface LogEntry {
  type: 'success' | 'error' | 'info';
  message: string;
}

export interface ParseResponse {
  success: boolean;
  tasks: Task[];
  count: number;
  logs?: LogEntry[];
  error?: string;
}

export interface CategorySuggestion {
  task_id: string;
  type: string;
  confidence: number;
}

export interface CategorizeResponse {
  success: boolean;
  suggestions: CategorySuggestion[];
  error?: string;
}

export interface FileSummary {
  path: string;
  lines_changed: string;
  changes: string;
  impact: string;
  substeps_fulfilled: string[];
}

export interface CodeBlock {
  file: string;
  lines: string;
  code: string;
  annotation: string;
}

export interface VerifyResult {
  verdict: 'done' | 'not_done' | 'unclear';
  message: string;
  files_summary: FileSummary[];
  code_blocks: CodeBlock[];
  timestamp: string;
}

export interface DoResult {
  task_sent: string;
  cline_response: string;
  timestamp: string;
}

export interface TestResult {
  test_type: 'unit_test' | 'evidence' | 'manual';
  content: string;
  timestamp: string;
}

export interface EnforcementRecord {
  node_id: string;
  target_kind: 'node' | 'substep' | 'rule';
  target_id: string;
  verify?: VerifyResult;
  do?: DoResult;
  test?: TestResult;
}

export interface SubstepRuleUsed {
  rule_id: string;
  rule_text: string;
  how_used: string;
}

export interface SubstepVerification {
  substep_id: string;
  description: string;
  files_changed: string[];
  code_changes: string;
  rules_used: SubstepRuleUsed[];
  timestamp?: string;
}

export interface RuleAnalysis {
  rule_id: string;
  rule_text: string;
  followed: boolean;
  evidence: string;
  used_in_substeps?: string[];
}

export interface EnforcementResponse {
  success: boolean;
  record?: EnforcementRecord;
  verdict?: string;
  overview?: string;
  rules_analysis?: RuleAnalysis[];
  substep_verifications?: SubstepVerification[];
  files_summary?: FileSummary[];
  code_blocks?: CodeBlock[];
  task_sent?: string;
  test_type?: string;
  content?: string;
  message?: string;  // Keep for backwards compatibility
  error?: string;
}

export type Tag = string;

export interface TagList {
  tags: Tag[];
}

export interface AssignTagsPayload {
  chat_name: string;
  tags: Tag[];
}

export interface RemoveTagsPayload {
  chat_name: string;
  tags: Tag[];
}

export interface TagResponse {
  success: boolean;
  tags?: Tag[];
  error?: string;
}

export interface ChatVisualization {
  chat_id: string;
  name?: string;
  chat_file_path: string;
  status: string;
  last_polled_at?: string;
}

const normalizeTagsResponse = (response: TagResponse): TagResponse => {
  if (response.success && response.tags) {
    const uniqueTags = Array.from(new Set(response.tags));
    const sortedTags = uniqueTags.sort((a, b) => a.localeCompare(b));
    return { ...response, tags: sortedTags };
  }
  return response;
};

export const api = {
  parseChat: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API_BASE}/parse`, formData);
    return response.data;
  },

  categorize: async (tasks: any[]) => {
    const response = await axios.post(`${API_BASE}/categorize`, { tasks });
    return response.data;
  },

  analyzeBatch: async (tasks: any[], chat: string, userName: string = 'User') => {
    const response = await axios.post(`${API_BASE}/analyze-batch`, { 
      tasks, 
      chat,
      user_name: userName 
    });
    return response.data;
  },

  getChats: async () => {
    const response = await axios.get(`${API_BASE}/chats`);
    return response.data;
  },

  getCategorizedTasks: async (chat: string) => {
    const response = await axios.get(`${API_BASE}/categorized-tasks?chat=${chat}`);
    return response.data;
  },

  saveCategorizedTasks: async (chat: string, tasks: any[]) => {
    const response = await axios.post(`${API_BASE}/categorized-tasks`, { chat, tasks });
    return response.data;
  },

  getAnalyzedTasks: async (chat: string) => {
    const response = await axios.get(`${API_BASE}/analyzed-tasks?chat=${chat}`);
    return response.data;
  },

  saveAnalyzedTasks: async (chat: string, analyzedTasks: any[]) => {
    const response = await axios.post(`${API_BASE}/analyzed-tasks`, { 
      chat,
      analyzed_tasks: analyzedTasks 
    });
    return response.data;
  },

  getAssistantChats: async () => {
    const response = await axios.get(`${API_BASE}/assistant-chats`);
    return response.data;
  },

  getPlan: async (chatId: string) => {
    const response = await axios.get(`${API_BASE}/plan/${chatId}`);
    return response.data;
  },

  deleteLearnerChat: async (chatId: string) => {
    const response = await axios.delete(`${API_BASE}/learner-chats/${chatId}`);
    return response.data;
  },

  deleteAssistantChat: async (chatId: string) => {
    const response = await axios.delete(`${API_BASE}/assistant-chats/${chatId}`);
    return response.data;
  },

  updateRule: async (chat: string, taskId: string, ruleId: string, updates: any) => {
    const response = await axios.patch(
      `${API_BASE}/learner-chats/${chat}/tasks/${taskId}/rules/${ruleId}`,
      updates
    );
    return response.data;
  },

  deleteRule: async (chat: string, taskId: string, ruleId: string) => {
    const response = await axios.delete(
      `${API_BASE}/learner-chats/${chat}/tasks/${taskId}/rules/${ruleId}`
    );
    return response.data;
  },

  deletePlanNode: async (chatId: string, nodeId: string) => {
    const response = await axios.delete(
      `${API_BASE}/plan/${chatId}/nodes/${nodeId}`
    );
    return response.data;
  },

  deletePlanNodeRule: async (chatId: string, nodeId: string, ruleId: string) => {
    const response = await axios.delete(
      `${API_BASE}/plan/${chatId}/nodes/${nodeId}/rules/${ruleId}`
    );
    return response.data;
  },

  addPlanNodeRule: async (chatId: string, nodeId: string, payload: { name: string; description: string; source: string; rule_id?: string }) => {
    const response = await axios.post(
      `${API_BASE}/plan/${chatId}/nodes/${nodeId}/rules`,
      payload
    );
    return response.data;
  },

  addPlanNodeSubstep: async (chatId: string, nodeId: string, text: string) => {
    const response = await axios.post(
      `${API_BASE}/plan/${chatId}/nodes/${nodeId}/substeps`,
      { text }
    );
    return response.data;
  },

  deletePlanNodeSubstep: async (chatId: string, nodeId: string, substepId: string) => {
    const response = await axios.delete(
      `${API_BASE}/plan/${chatId}/nodes/${nodeId}/substeps/${substepId}`
    );
    return response.data;
  },

  getChatRecommendations: async (params?: { chat_id?: string; limit?: number; path?: string }) => {
    const response = await axios.get(`${API_BASE}/chat-recommendations`, {
      params,
    });
    return response.data;
  },

  appendAssistantPlanAudit: async (payload: {
    chat_id: string;
    node_id: string;
    who?: string;
    action: string;
    details?: string;
  }) => {
    const response = await axios.post(`${API_BASE}/assistant/plan/audit`, payload);
    return response.data;
  },

  getEnforcementRecord: async (
    chatId: string,
    nodeId: string,
    targetKind: string,
    targetId: string
  ) => {
    const response = await axios.get(
      `${API_BASE}/enforcement/${chatId}/${nodeId}/${targetKind}/${targetId}`
    );
    return response.data;
  },

  postEnforcementVerify: async (payload: {
    chat_id: string;
    node_id: string;
    target_kind: string;
    target_id: string;
  }) => {
    const response = await axios.post(`${API_BASE}/enforcement/verify`, payload);
    return response.data;
  },

  postEnforcementTest: async (payload: {
    chat_id: string;
    node_id: string;
    target_kind: string;
    target_id: string;
  }) => {
    const response = await axios.post(`${API_BASE}/enforcement/test`, payload);
    return response.data;
  },

  getLearnerTags: async (): Promise<TagResponse> => {
    try {
      const response = await axios.get<TagResponse>(`${API_BASE}/learner/tags`);
      return normalizeTagsResponse(response.data);
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Failed to get learner tags',
      };
    }
  },

  getLearnerChatTags: async (chatName: string): Promise<TagResponse> => {
    try {
      const response = await axios.get<TagResponse>(`${API_BASE}/learner/chats/${chatName}/tags`);
      return normalizeTagsResponse(response.data);
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Failed to get learner chat tags',
      };
    }
  },

  assignLearnerTags: async (chatName: string, tags: Tag[]): Promise<TagResponse> => {
    try {
      const payload: AssignTagsPayload = { chat_name: chatName, tags };
      const response = await axios.post<TagResponse>(`${API_BASE}/learner/tags/assign`, payload);
      return normalizeTagsResponse(response.data);
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Failed to assign learner tags',
      };
    }
  },

  removeLearnerTags: async (chatName: string, tags: Tag[]): Promise<TagResponse> => {
    try {
      const payload: RemoveTagsPayload = { chat_name: chatName, tags };
      const response = await axios.delete<TagResponse>(`${API_BASE}/learner/tags/remove`, { data: payload });
      return normalizeTagsResponse(response.data);
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Failed to remove learner tags',
      };
    }
  },

  getTags: async (): Promise<TagResponse> => {
    try {
      const response = await axios.get<TagResponse>(`${API_BASE}/tags`);
      return normalizeTagsResponse(response.data);
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Failed to get tags',
      };
    }
  },

  getChatTags: async (chatName: string): Promise<TagResponse> => {
    try {
      const response = await axios.get<TagResponse>(`${API_BASE}/chats/${chatName}/tags`);
      return normalizeTagsResponse(response.data);
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Failed to get chat tags',
      };
    }
  },

  assignTags: async (chatName: string, tags: Tag[]): Promise<TagResponse> => {
    try {
      const payload: AssignTagsPayload = { chat_name: chatName, tags };
      const response = await axios.post<TagResponse>(`${API_BASE}/tags/assign`, payload);
      return normalizeTagsResponse(response.data);
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Failed to assign tags',
      };
    }
  },

  removeTags: async (chatName: string, tags: Tag[]): Promise<TagResponse> => {
    try {
      const payload: RemoveTagsPayload = { chat_name: chatName, tags };
      const response = await axios.delete<TagResponse>(`${API_BASE}/tags/remove`, { data: payload });
      return normalizeTagsResponse(response.data);
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Failed to remove tags',
      };
    }
  },

  markProcessed: async (filename: string) => {
    const response = await axios.post(`${API_BASE}/mark-processed`, { filename });
    return response.data;
  },

  getEnforcementV2Record: async (
    chatId: string,
    nodeId: string,
    targetId: string
  ) => {
    const response = await axios.get(
      `${API_BASE}/enforcement/v2/${chatId}/${nodeId}/${targetId}`
    );
    return response.data;
  },

  listRequirementsV2: async (payload: {
    chat_id: string;
    node_id: string;
    target_id: string;
  }) => {
    const response = await axios.post(`${API_BASE}/enforcement/v2/list-requirements`, payload);
    return response.data;
  },

  addRequirementV2: async (payload: {
    chat_id: string;
    node_id: string;
    target_id: string;
    description: string;
    category: string;
  }) => {
    const response = await axios.post(`${API_BASE}/enforcement/v2/add-requirement`, payload);
    return response.data;
  },

  deleteRequirementV2: async (payload: {
    chat_id: string;
    node_id: string;
    target_id: string;
    requirement_id: string;
  }) => {
    const response = await axios.post(`${API_BASE}/enforcement/v2/delete-requirement`, payload);
    return response.data;
  },

  verifyRequirementsV2: async (payload: {
    chat_id: string;
    node_id: string;
    target_id: string;
    requirements: any[];
  }) => {
    const response = await axios.post(`${API_BASE}/enforcement/v2/verify`, payload);
    return response.data;
  },

  testRequirementsV2: async (payload: {
    chat_id: string;
    node_id: string;
    target_id: string;
    requirements: any[];
  }) => {
    const response = await axios.post(`${API_BASE}/enforcement/v2/test`, payload);
    return response.data;
  },

  verifyStepV2: async (chatId: string, nodeId: string) => {
    const response = await axios.post(`${API_BASE}/enforcement/v2/verify-step`, {
      chat_id: chatId,
      node_id: nodeId,
    });
    return response.data;
  },

  getFavorites: async () => {
    try {
      const response = await axios.get(`${API_BASE}/kb/favorites`);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || error.message || 'Failed to get favorites');
    }
  },

  toggleFavorite: async (itemId: string, isFavorite: boolean) => {
    try {
      const response = await axios.post(`${API_BASE}/kb/items/${itemId}/favorite`, {
        is_favorite: isFavorite
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || error.message || 'Failed to toggle favorite');
    }
  },

  addManualFavorite: async (data: { rule: string; reasoning: string; confidence?: number; decay?: number }) => {
    try {
      const response = await axios.post(`${API_BASE}/favorites/manual`, data);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || error.message || 'Failed to add manual favorite');
    }
  },

  searchRules: async (query: string) => {
    try {
      const response = await axios.get(`${API_BASE}/rules/search`, {
        params: { q: query }
      });
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || error.message || 'Failed to search rules');
    }
  },

  addRule: async (chat: string, taskId: string, ruleData: any) => {
    const response = await axios.post(
      `${API_BASE}/learner-chats/${chat}/tasks/${taskId}/rules`,
      ruleData
    );
    return response.data;
  },

  getTask: async (chat: string, taskId: string) => {
    const response = await axios.get(
      `${API_BASE}/learner-chats/${chat}/tasks/${taskId}`
    );
    return response.data;
  },

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

  updateChatVisualization: async (chatId: string, name: string): Promise<ChatVisualization> => {
    const response = await axios.put(`${API_BASE}/chat-visualizations/${chatId}`, { name });
    return response.data;
  },

  analyzeChatVisualization: async (chatId: string): Promise<{ 
    rules: Array<{ category: string; text: string; evidence: string }>; 
    total_clean_tokens: number;
    analyzed_tokens: number;
    remaining_tokens: number;
    all_analyzed: boolean;
  }> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/analyze`);
    return response.data;
  },

  saveRulesToMarkdown: async (rules: Array<{ category: string; text: string; evidence: string }>, chatId: string): Promise<{ success: boolean; message: string; file_path: string }> => {
    const response = await axios.post(`${API_BASE}/rules/save`, { rules, chat_id: chatId });
    return response.data;
  },

  getVisualizationPlan: async (chatId: string): Promise<{ success: boolean; plan: any | null }> => {
    const response = await axios.get(`${API_BASE}/chat-visualizations/${chatId}/plan`);
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

  getRuleLearning: async (chatId: string): Promise<{
    success: boolean;
    rules: any[];
    analyzed_tokens: number;
  }> => {
    const response = await axios.get(`${API_BASE}/visualization/rule-learning/${chatId}`);
    return response.data;
  },

  resolveSupervision: async (chatId: string, timestamp: string): Promise<{ success: boolean }> => {
    const response = await axios.post(`${API_BASE}/visualization/supervision/${chatId}/resolve`, {
      timestamp
    });
    return response.data;
  },

  superviseChatVisualization: async (chatId: string): Promise<{
    supervision: any;
    total_tokens: number;
    supervised_tokens: number;
    remaining_tokens: number;
    all_supervised: boolean;
  }> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/supervise`);
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

  extractPlan: async (chatId: string, manualContent?: string): Promise<{ success: boolean; plan: any; file_path: string }> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/extract-plan`, 
      manualContent ? { content: manualContent } : {}
    );
    return response.data;
  },

  retrieveRulesForPlan: async (chatId: string): Promise<{ success: boolean; plan: any }> => {
    const response = await axios.post(`${API_BASE}/chat-visualizations/${chatId}/retrieve-rules`);
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
        chosen_rule_index: chosenRuleIndex
      }
    );
    return response.data;
  },

  fetchPendingFiles: async (): Promise<{ files: any[], total_pending: number }> => {
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

  processFiles: async (files: string[]): Promise<{ success: boolean; results: any[]; total_added: number }> => {
    const response = await axios.post(`${API_BASE}/kb/process`, { files });
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
    
    const response = await axios.get(`${API_BASE}/kb/items?${params}`);
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

  fetchKBCategories: async (): Promise<{ success: boolean; categories: any[] }> => {
    const response = await axios.get(`${API_BASE}/kb/categories`);
    return response.data;
  },

  suggestCategoryMerges: async (): Promise<{ success: boolean; suggestions: any[] }> => {
    const response = await axios.get(`${API_BASE}/kb/categories/suggest-merges`);
    return response.data;
  },

  acceptCategoryMerge: async (data: { merge_from: string[]; merge_to: string }): Promise<{ success: boolean }> => {
    const response = await axios.post(`${API_BASE}/kb/categories/accept`, data);
    return response.data;
  },

  dismissCategoryMerge: async (suggestionId: string): Promise<{ success: boolean }> => {
    const response = await axios.post(`${API_BASE}/kb/categories/dismiss`, { suggestion_id: suggestionId });
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
      is_conflict: isConflict
    });
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

  simpleEnforceRule: async (
    chatId: string,
    itemId: string,
    ruleIndex: number
  ): Promise<{ success: boolean; verification: any; error?: string }> => {
    const response = await axios.post(
      `${API_BASE}/chat-visualizations/${chatId}/plan/items/${itemId}/rules/${ruleIndex}/simple-enforce`
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
};
