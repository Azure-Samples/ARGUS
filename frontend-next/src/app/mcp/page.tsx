"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Plug,
  Play,
  Copy,
  Check,
  RefreshCw,
  FileText,
  MessageSquare,
  Database,
  Search,
  Upload,
  Settings,
  ExternalLink,
  Loader2,
  CheckCircle,
  XCircle,
  Info,
  Send,
  Paperclip,
  X,
  Bot,
  User,
  Wrench,
} from "lucide-react"

import { PageContainer } from "@/components/layout/page-container"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import { toast } from "sonner"
import { backendClient } from "@/lib/api-client"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

interface MCPInfo {
  name: string
  description: string
  version: string
  transport: string
  endpoints: {
    mcp: string
  }
  tools: Array<{
    name: string
    description: string
  }>
  configuration_example: {
    mcpServers: {
      argus: {
        url: string
      }
    }
  }
}

interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
  toolCalls?: Array<{
    tool: string
    arguments: Record<string, unknown>
    result_preview: string
  }>
  attachments?: Array<{
    filename: string
    type: string
    size: number
  }>
}

interface ToolResult {
  success: boolean
  data?: unknown
  error?: string
  executionTime?: number
}

interface FileAttachment {
  file: File
  preview?: string
  uploadUrl?: string
  uploaded?: boolean
}

// Code block component with copy functionality
function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = React.useState(false)

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    toast.success("Copied to clipboard")
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group">
      <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm max-h-96">
        <code>{code}</code>
      </pre>
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={copyToClipboard}
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  )
}

// Tool card component
function ToolCard({
  name,
  description,
  icon: Icon,
  onClick,
  isActive,
}: {
  name: string
  description: string
  icon: React.ElementType
  onClick: () => void
  isActive: boolean
}) {
  return (
    <Card
      className={`cursor-pointer transition-all hover:border-primary ${
        isActive ? "border-primary bg-primary/5" : ""
      }`}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-primary" />
          <CardTitle className="text-sm font-medium">{name}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

// Chat message component
function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user"
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}
    >
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? "bg-primary text-primary-foreground" : "bg-muted"
      }`}>
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={`flex-1 max-w-[80%] ${isUser ? "text-right" : ""}`}>
        <div className={`inline-block p-3 rounded-lg ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        }`}>
          {message.attachments && message.attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {message.attachments.map((att, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  <Paperclip className="h-3 w-3 mr-1" />
                  {att.filename}
                </Badge>
              ))}
            </div>
          )}
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="text-sm prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-pre:bg-background/50 prose-code:text-primary prose-code:bg-background/50 prose-code:px-1 prose-code:rounded">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.toolCalls.map((tool, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs text-muted-foreground">
                <Wrench className="h-3 w-3" />
                <span>Used: {tool.tool}</span>
              </div>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground mt-1">
          {message.timestamp.toLocaleTimeString()}
        </p>
      </div>
    </motion.div>
  )
}

export default function MCPPage() {
  const [mcpInfo, setMcpInfo] = React.useState<MCPInfo | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)
  const [connectionStatus, setConnectionStatus] = React.useState<"connected" | "disconnected" | "checking">("checking")
  const [selectedTool, setSelectedTool] = React.useState<string>("argus_list_documents")
  const [toolResult, setToolResult] = React.useState<ToolResult | null>(null)
  const [isExecuting, setIsExecuting] = React.useState(false)
  
  // Tool arguments state
  const [documentId, setDocumentId] = React.useState("")
  const [datasetName, setDatasetName] = React.useState("default-dataset")
  const [searchQuery, setSearchQuery] = React.useState("")
  const [toolChatMessage, setToolChatMessage] = React.useState("")
  const [blobUrl, setBlobUrl] = React.useState("")
  const [uploadFilename, setUploadFilename] = React.useState("")
  const [limit, setLimit] = React.useState("50")
  
  // Create dataset tool state
  const [newDatasetName, setNewDatasetName] = React.useState("")
  const [systemPrompt, setSystemPrompt] = React.useState("")
  const [outputSchema, setOutputSchema] = React.useState("")
  const [maxPagesPerChunk, setMaxPagesPerChunk] = React.useState("10")
  
  // Chat state
  const [chatMessages, setChatMessages] = React.useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = React.useState("")
  const [isChatLoading, setIsChatLoading] = React.useState(false)
  const [attachments, setAttachments] = React.useState<FileAttachment[]>([])
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const chatEndRef = React.useRef<HTMLDivElement>(null)

  // Scroll to bottom when new messages arrive
  React.useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatMessages])

  // Fetch MCP info on mount
  React.useEffect(() => {
    fetchMCPInfo()
  }, [])

  const fetchMCPInfo = async () => {
    setIsLoading(true)
    setConnectionStatus("checking")
    try {
      const baseUrl = await backendClient.getBackendBaseUrl()
      const response = await fetch(`${baseUrl}/mcp/info`)
      if (response.ok) {
        const info = await response.json()
        setMcpInfo(info)
        setConnectionStatus("connected")
      } else {
        setConnectionStatus("disconnected")
      }
    } catch (error) {
      console.error("Failed to fetch MCP info:", error)
      setConnectionStatus("disconnected")
    } finally {
      setIsLoading(false)
    }
  }

  const getToolIcon = (toolName: string) => {
    const icons: Record<string, React.ElementType> = {
      argus_list_documents: FileText,
      argus_get_document: FileText,
      argus_chat_with_document: MessageSquare,
      argus_list_datasets: Database,
      argus_get_dataset_config: Settings,
      argus_process_document_url: Play,
      argus_get_extraction: FileText,
      argus_search_documents: Search,
      argus_get_upload_url: Upload,
      argus_create_dataset: Database,
    }
    return icons[toolName] || FileText
  }

  const executeTool = async () => {
    setIsExecuting(true)
    setToolResult(null)
    const startTime = Date.now()

    try {
      const baseUrl = await backendClient.getBackendBaseUrl()
      let endpoint = ""
      let method = "GET"
      let body: Record<string, unknown> | null = null

      switch (selectedTool) {
        case "argus_list_documents":
          endpoint = `/api/documents?dataset=${datasetName}&limit=${limit}`
          break
        case "argus_get_document":
          if (!documentId) throw new Error("Document ID is required")
          endpoint = `/api/documents/${documentId}`
          break
        case "argus_chat_with_document":
          if (!documentId || !toolChatMessage) throw new Error("Document ID and message are required")
          endpoint = `/api/chat`
          method = "POST"
          body = { document_id: documentId, message: toolChatMessage }
          break
        case "argus_list_datasets":
          endpoint = `/api/datasets`
          break
        case "argus_get_dataset_config":
          endpoint = `/api/datasets/${datasetName}/configuration`
          break
        case "argus_process_document_url":
          if (!blobUrl) throw new Error("Blob URL is required")
          endpoint = `/api/process-blob`
          method = "POST"
          body = { blob_url: blobUrl, dataset: datasetName }
          break
        case "argus_get_extraction":
          if (!documentId) throw new Error("Document ID is required")
          endpoint = `/api/documents/${documentId}`
          break
        case "argus_search_documents":
          if (!searchQuery) throw new Error("Search query is required")
          endpoint = `/api/documents?search=${encodeURIComponent(searchQuery)}&dataset=${datasetName}&limit=${limit}`
          break
        case "argus_get_upload_url":
          if (!uploadFilename) throw new Error("Filename is required")
          endpoint = `/api/upload-url?filename=${encodeURIComponent(uploadFilename)}&dataset=${datasetName}`
          break
        case "argus_create_dataset":
          if (!newDatasetName) throw new Error("Dataset name is required")
          if (!systemPrompt) throw new Error("System prompt is required")
          if (!outputSchema) throw new Error("Output schema is required")
          endpoint = `/api/datasets`
          method = "POST"
          let parsedSchema
          try {
            parsedSchema = JSON.parse(outputSchema)
          } catch {
            throw new Error("Output schema must be valid JSON")
          }
          body = {
            dataset_name: newDatasetName,
            system_prompt: systemPrompt,
            output_schema: parsedSchema,
            max_pages_per_chunk: parseInt(maxPagesPerChunk) || 10
          }
          break
        default:
          throw new Error("Unknown tool")
      }

      const response = await fetch(`${baseUrl}${endpoint}`, {
        method,
        headers: method === "POST" ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      })

      const data = await response.json()
      const executionTime = Date.now() - startTime

      if (response.ok) {
        setToolResult({ success: true, data, executionTime })
        toast.success(`Tool executed successfully in ${executionTime}ms`)
      } else {
        setToolResult({ success: false, error: data.detail || "Request failed", executionTime })
        toast.error(data.detail || "Tool execution failed")
      }
    } catch (error) {
      const executionTime = Date.now() - startTime
      const errorMessage = error instanceof Error ? error.message : "Unknown error"
      setToolResult({ success: false, error: errorMessage, executionTime })
      toast.error(errorMessage)
    } finally {
      setIsExecuting(false)
    }
  }

  // Handle file selection
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return

    const newAttachments: FileAttachment[] = []
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      newAttachments.push({
        file,
        preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
      })
    }
    setAttachments((prev) => [...prev, ...newAttachments])
  }

  // Remove attachment
  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  // Send chat message
  const sendChatMessage = async () => {
    if (!chatInput.trim() && attachments.length === 0) return
    if (isChatLoading) return

    // Capture the message and attachments before clearing state
    const messageContent = chatInput.trim()
    const currentAttachments = [...attachments]
    
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: messageContent,
      timestamp: new Date(),
      attachments: currentAttachments.map((a) => ({
        filename: a.file.name,
        type: a.file.type,
        size: a.file.size,
      })),
    }

    // Clear input and show loading state immediately for better UX
    setChatMessages((prev) => [...prev, userMessage])
    setChatInput("")
    setIsChatLoading(true)

    try {
      // Upload attachments first if any
      let uploadedFiles: Array<{ filename: string; blob_url: string; document_id: string }> = []
      if (currentAttachments.length > 0) {
        toast.info("Uploading files...")
        const baseUrl = await backendClient.getBackendBaseUrl()
        
        for (const att of currentAttachments) {
          try {
            // Upload file through backend (avoids CORS issues with direct blob storage upload)
            const formData = new FormData()
            formData.append('file', att.file)
            
            const uploadResponse = await fetch(
              `${baseUrl}/api/datasets/default-dataset/upload?run_ocr=false&run_gpt_vision=false&run_summary=false&run_evaluation=false`,
              {
                method: "POST",
                body: formData,
              }
            )

            if (uploadResponse.ok) {
              const uploadData = await uploadResponse.json()
              uploadedFiles.push({ 
                filename: att.file.name, 
                blob_url: uploadData.blob_url,
                document_id: uploadData.document_id 
              })
            } else {
              console.error(`Failed to upload ${att.file.name}: ${uploadResponse.statusText}`)
            }
          } catch (error) {
            console.error(`Failed to upload ${att.file.name}:`, error)
          }
        }
        
        if (uploadedFiles.length > 0) {
          toast.success(`Uploaded ${uploadedFiles.length} file(s)`)
        } else if (currentAttachments.length > 0) {
          toast.error("Failed to upload files")
        }
      }

      const baseUrl = await backendClient.getBackendBaseUrl()
      
      // Build chat history for context (excluding the message we just added)
      const chatHistory = chatMessages.slice(-10).map((m) => ({
        role: m.role,
        content: m.content,
      }))

      // Send message to MCP chat endpoint with the captured message content
      const response = await fetch(`${baseUrl}/api/mcp-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageContent,
          chat_history: chatHistory,
          attachments: uploadedFiles.map((f) => ({
            filename: f.filename,
            blob_url: f.blob_url,
            document_id: f.document_id,
          })),
        }),
      })

      const data = await response.json()

      if (response.ok) {
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
          toolCalls: data.tool_calls,
        }
        setChatMessages((prev) => [...prev, assistantMessage])
      } else {
        toast.error(data.detail || "Failed to get response")
        const errorMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: `Sorry, I encountered an error: ${data.detail || "Unknown error"}`,
          timestamp: new Date(),
        }
        setChatMessages((prev) => [...prev, errorMessage])
      }
    } catch (error) {
      console.error("Chat error:", error)
      toast.error("Failed to send message")
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "Sorry, I couldn't connect to the server. Please try again.",
        timestamp: new Date(),
      }
      setChatMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsChatLoading(false)
      setAttachments([])
    }
  }

  // Handle enter key in chat input
  const handleChatKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendChatMessage()
    }
  }

  const renderToolInputs = () => {
    switch (selectedTool) {
      case "argus_list_documents":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="dataset">Dataset (optional)</Label>
              <Input id="dataset" value={datasetName} onChange={(e) => setDatasetName(e.target.value)} placeholder="default-dataset" />
            </div>
            <div>
              <Label htmlFor="limit">Limit</Label>
              <Input id="limit" type="number" value={limit} onChange={(e) => setLimit(e.target.value)} placeholder="50" />
            </div>
          </div>
        )
      case "argus_get_document":
      case "argus_get_extraction":
        return (
          <div>
            <Label htmlFor="documentId">Document ID *</Label>
            <Input id="documentId" value={documentId} onChange={(e) => setDocumentId(e.target.value)} placeholder="Enter document ID" />
          </div>
        )
      case "argus_chat_with_document":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="documentId">Document ID *</Label>
              <Input id="documentId" value={documentId} onChange={(e) => setDocumentId(e.target.value)} placeholder="Enter document ID" />
            </div>
            <div>
              <Label htmlFor="message">Message *</Label>
              <Textarea id="message" value={toolChatMessage} onChange={(e) => setToolChatMessage(e.target.value)} placeholder="Ask a question about the document..." rows={3} />
            </div>
          </div>
        )
      case "argus_list_datasets":
        return <p className="text-sm text-muted-foreground">No parameters required. Click Execute to list all datasets.</p>
      case "argus_get_dataset_config":
        return (
          <div>
            <Label htmlFor="datasetName">Dataset Name *</Label>
            <Input id="datasetName" value={datasetName} onChange={(e) => setDatasetName(e.target.value)} placeholder="default-dataset" />
          </div>
        )
      case "argus_process_document_url":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="blobUrl">Blob URL *</Label>
              <Input id="blobUrl" value={blobUrl} onChange={(e) => setBlobUrl(e.target.value)} placeholder="https://storage.blob.core.windows.net/..." />
            </div>
            <div>
              <Label htmlFor="dataset">Dataset</Label>
              <Input id="dataset" value={datasetName} onChange={(e) => setDatasetName(e.target.value)} placeholder="default-dataset" />
            </div>
          </div>
        )
      case "argus_search_documents":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="query">Search Query *</Label>
              <Input id="query" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Enter search keywords..." />
            </div>
            <div>
              <Label htmlFor="dataset">Dataset (optional)</Label>
              <Input id="dataset" value={datasetName} onChange={(e) => setDatasetName(e.target.value)} placeholder="default-dataset" />
            </div>
            <div>
              <Label htmlFor="limit">Limit</Label>
              <Input id="limit" type="number" value={limit} onChange={(e) => setLimit(e.target.value)} placeholder="20" />
            </div>
          </div>
        )
      case "argus_get_upload_url":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="filename">Filename *</Label>
              <Input id="filename" value={uploadFilename} onChange={(e) => setUploadFilename(e.target.value)} placeholder="document.pdf" />
            </div>
            <div>
              <Label htmlFor="dataset">Dataset</Label>
              <Input id="dataset" value={datasetName} onChange={(e) => setDatasetName(e.target.value)} placeholder="default-dataset" />
            </div>
          </div>
        )
      case "argus_create_dataset":
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="newDatasetName">Dataset Name *</Label>
              <Input 
                id="newDatasetName" 
                value={newDatasetName} 
                onChange={(e) => setNewDatasetName(e.target.value)} 
                placeholder="my-dataset (alphanumeric and hyphens only)" 
              />
            </div>
            <div>
              <Label htmlFor="systemPrompt">System Prompt *</Label>
              <Textarea 
                id="systemPrompt" 
                value={systemPrompt} 
                onChange={(e) => setSystemPrompt(e.target.value)} 
                placeholder="Extract all data from the document and return it in the specified JSON format..."
                rows={4}
              />
            </div>
            <div>
              <Label htmlFor="outputSchema">Output Schema (JSON) *</Label>
              <Textarea 
                id="outputSchema" 
                value={outputSchema} 
                onChange={(e) => setOutputSchema(e.target.value)} 
                placeholder='{"field1": "description of what to extract", "field2": "..."}'
                rows={6}
                className="font-mono text-sm"
              />
            </div>
            <div>
              <Label htmlFor="maxPages">Max Pages Per Chunk</Label>
              <Input 
                id="maxPages" 
                type="number" 
                value={maxPagesPerChunk} 
                onChange={(e) => setMaxPagesPerChunk(e.target.value)} 
                placeholder="10" 
              />
            </div>
          </div>
        )
      default:
        return null
    }
  }

  if (isLoading) {
    return (
      <PageContainer title="🔌 MCP Integration" description="Model Context Protocol for AI Assistants">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="🔌 MCP Integration" description="Model Context Protocol for AI Assistants">
      {/* Connection Status */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Plug className="h-5 w-5" />
              <div>
                <CardTitle>MCP Server Status</CardTitle>
                <CardDescription>Connect AI assistants like GitHub Copilot and Claude to ARGUS</CardDescription>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {connectionStatus === "connected" ? (
                <Badge variant="default" className="bg-green-500">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  Connected
                </Badge>
              ) : connectionStatus === "checking" ? (
                <Badge variant="secondary">
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  Checking...
                </Badge>
              ) : (
                <Badge variant="destructive">
                  <XCircle className="h-3 w-3 mr-1" />
                  Disconnected
                </Badge>
              )}
              <Button variant="outline" size="sm" onClick={fetchMCPInfo}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        {mcpInfo && (
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="p-3 rounded-lg border">
                <p className="text-xs text-muted-foreground">Server Name</p>
                <p className="font-medium">{mcpInfo.name}</p>
              </div>
              <div className="p-3 rounded-lg border">
                <p className="text-xs text-muted-foreground">Version</p>
                <p className="font-medium">{mcpInfo.version}</p>
              </div>
              <div className="p-3 rounded-lg border">
                <p className="text-xs text-muted-foreground">Transport</p>
                <p className="font-medium uppercase">{mcpInfo.transport}</p>
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      <Tabs defaultValue="chat" className="space-y-4">
        <TabsList>
          <TabsTrigger value="chat" className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            AI Chat
          </TabsTrigger>
          <TabsTrigger value="playground" className="flex items-center gap-2">
            <Play className="h-4 w-4" />
            Tool Playground
          </TabsTrigger>
          <TabsTrigger value="setup" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Setup Guide
          </TabsTrigger>
        </TabsList>

        {/* AI Chat Tab */}
        <TabsContent value="chat" className="space-y-4">
          <Card className="h-[600px] flex flex-col">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-5 w-5" />
                ARGUS AI Assistant
              </CardTitle>
              <CardDescription>
                Chat with AI to interact with your documents. Attach files to upload and process them.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col overflow-hidden">
              {/* Chat Messages */}
              <ScrollArea className="flex-1 pr-4">
                <div className="space-y-4 pb-4">
                  {chatMessages.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p className="text-lg font-medium">Welcome to ARGUS AI Assistant!</p>
                      <p className="text-sm mt-2">Ask me about your documents, search for files, or upload new ones.</p>
                      <div className="flex flex-wrap justify-center gap-2 mt-4">
                        <Badge variant="secondary" className="cursor-pointer" onClick={() => setChatInput("List all my documents")}>
                          List all documents
                        </Badge>
                        <Badge variant="secondary" className="cursor-pointer" onClick={() => setChatInput("What datasets are available?")}>
                          Show datasets
                        </Badge>
                        <Badge variant="secondary" className="cursor-pointer" onClick={() => setChatInput("Search for invoices")}>
                          Search invoices
                        </Badge>
                      </div>
                    </div>
                  ) : (
                    chatMessages.map((message) => (
                      <ChatMessageBubble key={message.id} message={message} />
                    ))
                  )}
                  {isChatLoading && (
                    <div className="flex gap-3">
                      <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                        <Bot className="h-4 w-4" />
                      </div>
                      <div className="bg-muted p-3 rounded-lg">
                        <Loader2 className="h-4 w-4 animate-spin" />
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
              </ScrollArea>

              {/* Attachments Preview */}
              <AnimatePresence>
                {attachments.length > 0 && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="border-t pt-3 mb-3"
                  >
                    <div className="flex flex-wrap gap-2">
                      {attachments.map((att, idx) => (
                        <div key={idx} className="relative group">
                          <Badge variant="secondary" className="pr-6">
                            <Paperclip className="h-3 w-3 mr-1" />
                            {att.file.name}
                          </Badge>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-destructive text-destructive-foreground opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={() => removeAttachment(idx)}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Chat Input */}
              <div className="flex gap-2 pt-3 border-t">
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.tiff,.docx,.xlsx"
                  onChange={handleFileSelect}
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isChatLoading}
                >
                  <Paperclip className="h-4 w-4" />
                </Button>
                <Textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={handleChatKeyDown}
                  placeholder="Ask about your documents, search, or upload files..."
                  className="min-h-[40px] max-h-[120px] resize-none"
                  rows={1}
                  disabled={isChatLoading}
                />
                <Button onClick={sendChatMessage} disabled={isChatLoading || (!chatInput.trim() && attachments.length === 0)}>
                  {isChatLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tool Playground Tab */}
        <TabsContent value="playground" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            {/* Tool Selection */}
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle className="text-sm">Available Tools</CardTitle>
                <CardDescription>Select a tool to test</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px] pr-4">
                  <div className="space-y-2">
                    {mcpInfo?.tools.map((tool) => (
                      <ToolCard
                        key={tool.name}
                        name={tool.name.replace("argus_", "")}
                        description={tool.description}
                        icon={getToolIcon(tool.name)}
                        onClick={() => setSelectedTool(tool.name)}
                        isActive={selectedTool === tool.name}
                      />
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Tool Execution */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm flex items-center gap-2">
                      {React.createElement(getToolIcon(selectedTool), { className: "h-4 w-4" })}
                      {selectedTool}
                    </CardTitle>
                    <CardDescription>{mcpInfo?.tools.find((t) => t.name === selectedTool)?.description}</CardDescription>
                  </div>
                  <Button onClick={executeTool} disabled={isExecuting}>
                    {isExecuting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
                    Execute
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 rounded-lg border bg-muted/50">
                  <h4 className="text-sm font-medium mb-3">Parameters</h4>
                  {renderToolInputs()}
                </div>

                {toolResult && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium">Result</h4>
                      <div className="flex items-center gap-2">
                        {toolResult.success ? (
                          <Badge variant="default" className="bg-green-500">
                            <CheckCircle className="h-3 w-3 mr-1" />
                            Success
                          </Badge>
                        ) : (
                          <Badge variant="destructive">
                            <XCircle className="h-3 w-3 mr-1" />
                            Error
                          </Badge>
                        )}
                        {toolResult.executionTime && <Badge variant="outline">{toolResult.executionTime}ms</Badge>}
                      </div>
                    </div>
                    <CodeBlock code={JSON.stringify(toolResult.success ? toolResult.data : { error: toolResult.error }, null, 2)} />
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Setup Guide Tab */}
        <TabsContent value="setup" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Configure Your AI Assistant</CardTitle>
              <CardDescription>Add ARGUS MCP server to your AI assistant configuration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* VS Code / GitHub Copilot */}
              <div>
                <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                  <img src="https://code.visualstudio.com/favicon.ico" className="h-5 w-5" alt="VS Code" />
                  VS Code / GitHub Copilot
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Add to your workspace <code className="bg-muted px-1 rounded">.vscode/mcp.json</code> or global settings:
                </p>
                <CodeBlock
                  code={JSON.stringify(
                    {
                      mcpServers: {
                        argus: {
                          url: mcpInfo?.configuration_example?.mcpServers?.argus?.url || "https://ca-argus.nicesand-0a67ac7b.eastus2.azurecontainerapps.io/mcp",
                        },
                      },
                    },
                    null,
                    2
                  )}
                />
              </div>

              {/* Claude Desktop */}
              <div>
                <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                  <img src="https://claude.ai/favicon.ico" className="h-5 w-5" alt="Claude" />
                  Claude Desktop
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Add to <code className="bg-muted px-1 rounded">~/Library/Application Support/Claude/claude_desktop_config.json</code>:
                </p>
                <CodeBlock
                  code={JSON.stringify(
                    {
                      mcpServers: {
                        argus: {
                          url: mcpInfo?.configuration_example?.mcpServers?.argus?.url || "https://ca-argus.nicesand-0a67ac7b.eastus2.azurecontainerapps.io/mcp",
                        },
                      },
                    },
                    null,
                    2
                  )}
                />
              </div>

              {/* MCP Endpoints */}
              <div>
                <h3 className="text-lg font-semibold mb-2">MCP Endpoints</h3>
                <div className="grid gap-2">
                  <div className="p-3 rounded-lg border flex items-center justify-between">
                    <div>
                      <p className="font-medium">Streamable HTTP Endpoint</p>
                      <p className="text-sm text-muted-foreground">Main MCP communication endpoint</p>
                    </div>
                    <code className="bg-muted px-2 py-1 rounded text-sm">/mcp</code>
                  </div>
                  <div className="p-3 rounded-lg border flex items-center justify-between">
                    <div>
                      <p className="font-medium">Info Endpoint</p>
                      <p className="text-sm text-muted-foreground">Server information</p>
                    </div>
                    <code className="bg-muted px-2 py-1 rounded text-sm">/mcp/info</code>
                  </div>
                </div>
              </div>

              {/* Learn More */}
              <div className="p-4 rounded-lg bg-muted/50 flex items-start gap-3">
                <Info className="h-5 w-5 text-blue-500 mt-0.5" />
                <div>
                  <p className="font-medium">Learn More About MCP</p>
                  <p className="text-sm text-muted-foreground mb-2">
                    The Model Context Protocol enables AI assistants to securely connect to external tools and data sources.
                  </p>
                  <a
                    href="https://modelcontextprotocol.io/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-primary hover:underline inline-flex items-center gap-1"
                  >
                    Visit modelcontextprotocol.io
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </PageContainer>
  )
}
