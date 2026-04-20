const CLINE_BASE = 'http://localhost:48820';

export interface ClineExecuteResponse {
  verdict: 'done' | 'not_done' | 'unclear';
  message: string;
  tracking_commands?: string[];
  action_text?: string;
}

export const clineApi = {
  executeStep: async (chatId: string, stepId: string, nodeData?: any): Promise<ClineExecuteResponse> => {
    const response = await fetch(`${CLINE_BASE}/execute-step`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        chat_id: chatId, 
        step_id: stepId,
        node: nodeData  // Send full node data including rules
      })
    });
    
    if (!response.ok) {
      throw new Error(`Cline API error: ${response.statusText}`);
    }
    
    return response.json();
  },

  executeRule: async (chatId: string, stepId: string, ruleId: string, nodeData?: any): Promise<ClineExecuteResponse> => {
    const response = await fetch(`${CLINE_BASE}/execute-rule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        chat_id: chatId, 
        step_id: stepId, 
        rule_id: ruleId,
        node: nodeData  // Send full node data
      })
    });
    
    if (!response.ok) {
      throw new Error(`Cline API error: ${response.statusText}`);
    }
    
    return response.json();
  },

  executeSubstep: async (chatId: string, stepId: string, substepId: string, nodeData?: any): Promise<ClineExecuteResponse> => {
    const response = await fetch(`${CLINE_BASE}/execute-substep`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        chat_id: chatId, 
        step_id: stepId, 
        substep_id: substepId,
        node: nodeData  // Send full node data
      })
    });
    
    if (!response.ok) {
      throw new Error(`Cline API error: ${response.statusText}`);
    }
    
    return response.json();
  },

  executeTask: async (taskText: string, context?: { chatId?: string; nodeId?: string; targetId?: string }): Promise<any> => {
    const response = await fetch(`${CLINE_BASE}/execute-task`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        task: taskText,
        context: context || {}
      })
    });
    
    if (!response.ok) {
      throw new Error(`Cline API error: ${response.statusText}`);
    }
    
    return response.json();
  },

  generateTests: async (
    verificationResult: any,
    context: { chatId: string; nodeId: string; targetId: string }
  ): Promise<any> => {
    const response = await fetch(`${CLINE_BASE}/generate-tests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        verificationResult,
        context
      })
    });
    
    if (!response.ok) {
      throw new Error(`Cline API error: ${response.statusText}`);
    }
    
    return response.json();
  }
};
