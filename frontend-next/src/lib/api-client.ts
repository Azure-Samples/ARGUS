/**
 * Backend API Client for ARGUS Frontend
 * 
 * This client provides type-safe methods for interacting with the ARGUS backend API.
 */

// Document types
export interface DocumentState {
  file_landed?: boolean
  ocr_completed?: boolean
  gpt_extraction_completed?: boolean
  gpt_evaluation_completed?: boolean
  gpt_summary_completed?: boolean
  processing_completed?: boolean
  error?: boolean
}

export interface DocumentProperties {
  blob_name?: string
  blob_size?: number
  request_timestamp?: string
  num_pages?: number
  dataset?: string
  total_time?: number
  total_time_seconds?: number
}

export interface DocumentExtractedData {
  ocr_output?: string | Record<string, unknown>[]
  gpt_output?: Record<string, unknown>
  gpt_evaluation?: Record<string, unknown>
  gpt_summary?: string
  gpt_extraction_output?: Record<string, unknown>
}

export interface Document {
  id: string
  partitionKey?: string
  properties?: DocumentProperties
  state?: DocumentState
  extracted_data?: DocumentExtractedData
  errors?: string | string[]
  timestamp?: string
  // Additional fields that may be present at root level
  created_at?: string
  processing_time?: number
  num_pages?: number
  total_time_seconds?: number
  // OCR and summary data at root level
  ocr_text?: string
  summary?: string
  gpt_output?: Record<string, unknown>
  gpt_evaluation?: Record<string, unknown>
  // Model configuration
  model_input?: Record<string, unknown>
  processing_options?: Record<string, boolean>
}

export interface DocumentsResponse {
  documents: Document[]
  count: number
}

// Configuration types
export interface ProcessingOptions {
  include_ocr?: boolean
  include_images?: boolean
  enable_summary?: boolean
  enable_evaluation?: boolean
  ocr_provider?: "azure" | "mistral"
}

export interface DatasetConfig {
  system_prompt?: string
  model_prompt?: string
  output_schema?: Record<string, unknown>
  example_schema?: Record<string, unknown>
  max_pages_per_chunk?: number
  processing_options?: ProcessingOptions
}

export interface Configuration {
  id?: string
  partitionKey?: string
  datasets: Record<string, DatasetConfig>
}

// Chat types
export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

export interface ChatRequest {
  document_id: string
  message: string
  chat_history?: ChatMessage[]
}

export interface ChatResponse {
  response: string
  finish_reason?: string
  usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

// MCP types
export interface MCPTool {
  name: string
  description: string
}

export interface MCPInfo {
  name: string
  description: string
  version: string
  transport: string
  endpoints: {
    mcp: string
  }
  tools: MCPTool[]
  configuration_example: {
    mcpServers: {
      argus: {
        url: string
      }
    }
  }
}

// Settings types
export interface OpenAISettings {
  openai_endpoint?: string
  openai_key?: string
  deployment_name?: string
  ocr_provider?: string
  mistral_endpoint?: string
  mistral_key?: string
  mistral_model?: string
  note?: string
}

export interface ConcurrencySettings {
  enabled?: boolean
  current_max_runs?: number
  trigger_concurrency?: number
  workflow_name?: string
  subscription_id?: string
  resource_group?: string
  logic_app_name?: string
  error?: string
}

// Dataset types
export interface DatasetInfo {
  name: string
  system_prompt_preview?: string
  schema_fields?: string[]
  max_pages_per_chunk?: number
}

export interface DatasetsResponse {
  datasets: DatasetInfo[]
}

export interface CreateDatasetRequest {
  dataset_name: string
  system_prompt: string
  output_schema: Record<string, unknown>
  max_pages_per_chunk?: number
}

export interface CreateDatasetResponse {
  success: boolean
  dataset_name: string
  message: string
  configuration: {
    system_prompt_length: number
    output_schema_fields: string[]
    max_pages_per_chunk: number
  }
}

// Health check types
export interface HealthResponse {
  status: string
  timestamp?: string
  services?: {
    storage?: string
    cosmos_db?: string
  }
}

// Upload types
export interface UploadUrlResponse {
  upload_url: string
  method: string
  headers: Record<string, string>
  filename: string
  dataset: string
  blob_path: string
  expires_in: string
  instructions: string[]
}

// Correction types
export interface Correction {
  id?: string
  timestamp: string
  user_id: string
  notes: string
  corrected_data: Record<string, unknown>
  original_data?: Record<string, unknown>
}

export interface CorrectionHistoryResponse {
  corrections: Correction[]
}

// Upload options
export interface UploadOptions {
  run_ocr?: boolean
  run_gpt_vision?: boolean
  run_summary?: boolean
  run_evaluation?: boolean
}

/**
 * Backend API Client
 * 
 * Provides methods for interacting with the ARGUS backend API.
 */
class BackendClient {
  private baseUrl: string = ''
  private initialized: boolean = false
  private initPromise: Promise<void> | null = null

  constructor() {
    // Base URL will be fetched lazily from /api/config
  }

  /**
   * Initialize the client by fetching the backend URL
   */
  private async initialize(): Promise<void> {
    if (this.initialized) {
      return
    }

    // Avoid multiple concurrent initializations
    if (this.initPromise) {
      return this.initPromise
    }

    this.initPromise = (async () => {
      try {
        // Fetch backend URL from the Next.js API route
        const response = await fetch('/api/config')
        if (response.ok) {
          const config = await response.json()
          this.baseUrl = config.backendUrl || ''
        }
      } catch (error) {
        console.warn('Failed to fetch backend config, using fallback:', error)
        // Fallback to environment variable or empty string
        this.baseUrl = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_BACKEND_URL || ''
      }
      this.initialized = true
    })()

    return this.initPromise
  }

  /**
   * Get the backend base URL, initializing if needed
   */
  async getBackendBaseUrl(): Promise<string> {
    await this.initialize()
    return this.baseUrl
  }

  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    await this.initialize()
    const url = `${this.baseUrl}${endpoint}`
    
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP error ${response.status}`)
    }

    return response.json()
  }

  // Health endpoints
  async healthCheck(): Promise<HealthResponse> {
    return this.fetch<HealthResponse>("/health")
  }

  // Document endpoints
  async listDocuments(dataset?: string, limit?: number): Promise<DocumentsResponse> {
    const params = new URLSearchParams()
    if (dataset) params.append("dataset", dataset)
    if (limit) params.append("limit", limit.toString())
    
    const query = params.toString() ? `?${params.toString()}` : ""
    return this.fetch<DocumentsResponse>(`/api/documents${query}`)
  }

  // Alias for listDocuments for backward compatibility
  async getDocuments(dataset?: string, limit?: number): Promise<DocumentsResponse> {
    return this.listDocuments(dataset, limit)
  }

  async getDocument(documentId: string): Promise<Document> {
    return this.fetch<Document>(`/api/documents/${encodeURIComponent(documentId)}`)
  }

  async deleteDocument(documentId: string): Promise<{ message: string }> {
    return this.fetch<{ message: string }>(
      `/api/documents/${encodeURIComponent(documentId)}`,
      { method: "DELETE" }
    )
  }

  async reprocessDocument(documentId: string): Promise<{ message: string }> {
    return this.fetch<{ message: string }>(
      `/api/documents/${encodeURIComponent(documentId)}/reprocess`,
      { method: "POST" }
    )
  }

  async getDocumentFileUrl(documentId: string): Promise<string> {
    // The backend serves the file directly at /file endpoint
    // Return the URL for iframe/embed use
    await this.initialize()
    return `${this.baseUrl}/api/documents/${encodeURIComponent(documentId)}/file`
  }

  // Configuration endpoints
  async getConfiguration(): Promise<Configuration> {
    return this.fetch<Configuration>("/api/configuration")
  }

  async updateConfiguration(config: Record<string, unknown>): Promise<{ status: string; message: string }> {
    return this.fetch<{ status: string; message: string }>("/api/configuration", {
      method: "POST",
      body: JSON.stringify(config),
    })
  }

  async refreshConfiguration(): Promise<{ status: string; message: string }> {
    return this.fetch<{ status: string; message: string }>("/api/configuration/refresh", {
      method: "POST",
    })
  }

  // Dataset endpoints
  async getDatasets(): Promise<DatasetsResponse> {
    return this.fetch<DatasetsResponse>("/api/datasets")
  }

  async createDataset(request: CreateDatasetRequest): Promise<CreateDatasetResponse> {
    return this.fetch<CreateDatasetResponse>("/api/datasets", {
      method: "POST",
      body: JSON.stringify(request),
    })
  }

  async getDatasetDocuments(datasetName: string): Promise<DocumentsResponse> {
    return this.fetch<DocumentsResponse>(
      `/api/datasets/${encodeURIComponent(datasetName)}/documents`
    )
  }

  // Chat endpoints
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return this.fetch<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify(request),
    })
  }

  async sendChatMessage(documentId: string, message: string, chatHistory?: ChatMessage[]): Promise<ChatResponse> {
    return this.chat({
      document_id: documentId,
      message,
      chat_history: chatHistory,
    })
  }

  // MCP endpoints
  async getMCPInfo(): Promise<MCPInfo> {
    return this.fetch<MCPInfo>("/mcp/info")
  }

  // Settings endpoints
  async getOpenAISettings(): Promise<OpenAISettings> {
    return this.fetch<OpenAISettings>("/api/openai-settings")
  }

  async updateOpenAISettings(settings: Partial<OpenAISettings>): Promise<{ message: string }> {
    return this.fetch<{ message: string }>("/api/openai-settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    })
  }

  async getConcurrencySettings(): Promise<ConcurrencySettings> {
    return this.fetch<ConcurrencySettings>("/api/concurrency")
  }

  async updateConcurrencySettings(settings: { max_runs: number }): Promise<{ success: boolean; message: string }> {
    return this.fetch<{ success: boolean; message: string }>("/api/concurrency", {
      method: "PUT",
      body: JSON.stringify(settings),
    })
  }

  async getConcurrencyDiagnostics(): Promise<Record<string, unknown>> {
    return this.fetch<Record<string, unknown>>("/api/concurrency/diagnostics")
  }

  // Upload endpoints
  async getUploadUrl(filename: string, dataset: string = "default-dataset"): Promise<UploadUrlResponse> {
    const params = new URLSearchParams({ filename, dataset })
    return this.fetch<UploadUrlResponse>(`/api/upload-url?${params.toString()}`)
  }

  async processBlob(blobUrl: string, dataset?: string): Promise<{ message: string }> {
    return this.fetch<{ message: string }>("/api/process-blob", {
      method: "POST",
      body: JSON.stringify({ blob_url: blobUrl, dataset }),
    })
  }

  // File upload with options - uses SAS URL for production
  async uploadFile(
    datasetName: string,
    file: File,
    options?: UploadOptions
  ): Promise<{ message: string; id: string }> {
    // Get SAS URL for direct blob upload
    const uploadInfo = await this.getUploadUrl(file.name, datasetName)
    
    // Determine content type
    const contentType = file.type || 'application/octet-stream'
    
    // Upload directly to Azure Blob Storage using SAS URL
    const uploadResponse = await fetch(uploadInfo.upload_url, {
      method: 'PUT',
      headers: {
        'x-ms-blob-type': 'BlockBlob',
        'Content-Type': contentType,
      },
      body: file,
    })

    if (!uploadResponse.ok) {
      const errorText = await uploadResponse.text().catch(() => '')
      throw new Error(`Upload failed: ${uploadResponse.status} ${errorText}`)
    }

    // The blob upload triggers automatic processing via Event Grid
    return {
      message: `File ${file.name} uploaded successfully to ${datasetName}. Processing will begin automatically.`,
      id: uploadInfo.blob_path,
    }
  }

  // Correction endpoints
  async getCorrectionHistory(documentId: string): Promise<CorrectionHistoryResponse> {
    return this.fetch<CorrectionHistoryResponse>(
      `/api/documents/${encodeURIComponent(documentId)}/corrections`
    )
  }

  async submitCorrection(
    documentId: string,
    correctedData: Record<string, unknown>,
    notes: string,
    userId: string = "anonymous"
  ): Promise<{ message: string }> {
    return this.fetch<{ message: string }>(
      `/api/documents/${encodeURIComponent(documentId)}/corrections`,
      {
        method: "PATCH",
        body: JSON.stringify({
          corrected_data: correctedData,
          notes,
          user_id: userId,
        }),
      }
    )
  }

  // Statistics (local development)
  async getStats(): Promise<{
    total_documents: number
    completed_documents: number
    pending_documents: number
    success_rate: number
  }> {
    return this.fetch(`/api/stats`)
  }
}

// Export singleton instance
export const backendClient = new BackendClient()

// Export the class for testing
export { BackendClient }
