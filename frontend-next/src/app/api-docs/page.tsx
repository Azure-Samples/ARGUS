"use client"

import * as React from "react"
import { motion } from "framer-motion"
import {
  FileCode,
  Server,
  Heart,
  FileText,
  Settings2,
  MessageSquare,
  History,
  Database,
  Upload,
  ChevronRight,
  Copy,
  Check,
  ExternalLink,
} from "lucide-react"

import { PageContainer } from "@/components/layout/page-container"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

// Code block component with copy functionality
function CodeBlock({ code, language = "json" }: { code: string; language?: string }) {
  const [copied, setCopied] = React.useState(false)

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    toast.success("Copied to clipboard")
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group">
      <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm">
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

// Endpoint component
function Endpoint({
  method,
  path,
  description,
  requestBody,
  response,
}: {
  method: "GET" | "POST" | "PUT" | "DELETE"
  path: string
  description: string
  requestBody?: string
  response?: string
}) {
  const methodColors = {
    GET: "bg-blue-500",
    POST: "bg-green-500",
    PUT: "bg-yellow-500",
    DELETE: "bg-red-500",
  }

  return (
    <Card className="mb-4">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3">
          <Badge className={`${methodColors[method]} text-white`}>{method}</Badge>
          <code className="text-sm font-mono bg-muted px-2 py-1 rounded">{path}</code>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {requestBody && (
          <div>
            <h4 className="text-sm font-medium mb-2">Request Body</h4>
            <CodeBlock code={requestBody} />
          </div>
        )}
        {response && (
          <div>
            <h4 className="text-sm font-medium mb-2">Response</h4>
            <CodeBlock code={response} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function ApiDocsPage() {
  return (
    <PageContainer
      title="🔌 API Documentation"
      description="REST API reference for the ARGUS backend"
    >
      {/* Overview */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCode className="h-5 w-5" />
            ARGUS API Overview
          </CardTitle>
          <CardDescription>
            REST API for document processing, AI-powered extraction, and document interaction
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="p-4 rounded-lg border">
              <h4 className="font-medium mb-2">Base URLs</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Production:</span>
                  <code className="bg-muted px-2 py-0.5 rounded">Container App endpoint</code>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Local Dev:</span>
                  <code className="bg-muted px-2 py-0.5 rounded">http://localhost:8000</code>
                </div>
              </div>
            </div>
            <div className="p-4 rounded-lg border">
              <h4 className="font-medium mb-2">Authentication</h4>
              <ul className="space-y-1 text-sm text-muted-foreground">
                <li>• Azure Default Credentials for Azure services</li>
                <li>• API keys via environment variables</li>
                <li>• CORS enabled for frontend integration</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* API Tabs */}
      <Tabs defaultValue="health" className="space-y-4">
        <TabsList className="flex flex-wrap h-auto gap-2">
          <TabsTrigger value="health" className="flex items-center gap-2">
            <Heart className="h-4 w-4" />
            Health
          </TabsTrigger>
          <TabsTrigger value="documents" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Documents
          </TabsTrigger>
          <TabsTrigger value="datasets" className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            Datasets
          </TabsTrigger>
          <TabsTrigger value="chat" className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Chat
          </TabsTrigger>
          <TabsTrigger value="corrections" className="flex items-center gap-2">
            <History className="h-4 w-4" />
            Corrections
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex items-center gap-2">
            <Settings2 className="h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Health Endpoints */}
        <TabsContent value="health">
          <Endpoint
            method="GET"
            path="/"
            description="Simple health check endpoint to verify service availability"
            response={`{
  "status": "healthy",
  "service": "ARGUS Backend"
}`}
          />
          <Endpoint
            method="GET"
            path="/health"
            description="Comprehensive health check including Azure service connectivity"
            response={`{
  "status": "healthy",
  "timestamp": "2025-07-17T10:30:00.123456Z",
  "services": {
    "storage": "connected",
    "cosmos_db": "connected"
  }
}`}
          />
        </TabsContent>

        {/* Document Endpoints */}
        <TabsContent value="documents">
          <Endpoint
            method="GET"
            path="/api/documents"
            description="List all processed documents with optional filtering"
            response={`{
  "documents": [
    {
      "id": "doc-123",
      "filename": "invoice.pdf",
      "dataset": "invoices",
      "status": "completed",
      "created_at": "2025-01-15T10:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}`}
          />
          <Endpoint
            method="GET"
            path="/api/documents/{document_id}"
            description="Get detailed information about a specific document"
            response={`{
  "id": "doc-123",
  "filename": "invoice.pdf",
  "dataset": "invoices",
  "status": "completed",
  "extracted_data": { ... },
  "ocr_data": { ... },
  "evaluation": { ... },
  "summary": "Document summary text"
}`}
          />
          <Endpoint
            method="DELETE"
            path="/api/documents/{document_id}"
            description="Delete a document from Cosmos DB and Blob Storage"
            response={`{
  "message": "Document deleted successfully",
  "document_id": "doc-123"
}`}
          />
          <Endpoint
            method="POST"
            path="/api/documents/{document_id}/reprocess"
            description="Trigger reprocessing of a document"
            requestBody={`{
  "options": {
    "include_ocr": true,
    "include_images": true,
    "enable_summary": true
  }
}`}
            response={`{
  "message": "Reprocessing started",
  "document_id": "doc-123"
}`}
          />
          <Endpoint
            method="POST"
            path="/api/upload"
            description="Upload a file for processing"
            requestBody={`FormData:
- file: PDF file
- dataset: string
- options: JSON string`}
            response={`{
  "message": "File uploaded successfully",
  "blob_url": "https://storage.blob.core.windows.net/...",
  "document_id": "doc-456"
}`}
          />
        </TabsContent>

        {/* Dataset Endpoints */}
        <TabsContent value="datasets">
          <Endpoint
            method="GET"
            path="/api/datasets"
            description="List all available datasets"
            response={`{
  "datasets": [
    {
      "name": "invoices",
      "has_system_prompt": true,
      "has_output_schema": true,
      "document_count": 150
    }
  ]
}`}
          />
          <Endpoint
            method="GET"
            path="/api/datasets/{dataset_name}/configuration"
            description="Get configuration for a specific dataset"
            response={`{
  "system_prompt": "Extract invoice data...",
  "output_schema": {
    "invoice_number": "string",
    "total_amount": "number"
  }
}`}
          />
          <Endpoint
            method="PUT"
            path="/api/datasets/{dataset_name}/configuration"
            description="Update dataset configuration"
            requestBody={`{
  "system_prompt": "Updated extraction instructions...",
  "output_schema": { ... }
}`}
            response={`{
  "message": "Configuration updated successfully"
}`}
          />
          <Endpoint
            method="POST"
            path="/api/datasets"
            description="Create a new dataset"
            requestBody={`{
  "name": "contracts",
  "system_prompt": "Extract contract data...",
  "output_schema": { ... }
}`}
            response={`{
  "message": "Dataset created successfully",
  "dataset": { ... }
}`}
          />
        </TabsContent>

        {/* Chat Endpoints */}
        <TabsContent value="chat">
          <Endpoint
            method="POST"
            path="/api/documents/{document_id}/chat"
            description="Send a chat message about a document"
            requestBody={`{
  "message": "What is the total amount on this invoice?"
}`}
            response={`{
  "message": "The total amount on this invoice is $1,234.56",
  "context_used": ["Page 1: Total Amount section"]
}`}
          />
        </TabsContent>

        {/* Corrections Endpoints */}
        <TabsContent value="corrections">
          <Endpoint
            method="POST"
            path="/api/documents/{document_id}/corrections"
            description="Submit a human correction for a document"
            requestBody={`{
  "field": "invoice_number",
  "corrected_value": "INV-2025-001"
}`}
            response={`{
  "message": "Correction submitted successfully",
  "correction_id": "corr-123"
}`}
          />
          <Endpoint
            method="GET"
            path="/api/documents/{document_id}/corrections"
            description="Get correction history for a document"
            response={`{
  "corrections": [
    {
      "id": "corr-123",
      "field": "invoice_number",
      "original_value": "INV-2025-000",
      "corrected_value": "INV-2025-001",
      "timestamp": "2025-01-15T11:00:00Z"
    }
  ]
}`}
          />
        </TabsContent>

        {/* Settings Endpoints */}
        <TabsContent value="settings">
          <Endpoint
            method="GET"
            path="/api/settings/openai"
            description="Get current OpenAI configuration"
            response={`{
  "endpoint": "https://your-resource.openai.azure.com/",
  "deployment_name": "gpt-4o"
}`}
          />
          <Endpoint
            method="PUT"
            path="/api/settings/openai"
            description="Update OpenAI configuration"
            requestBody={`{
  "endpoint": "https://your-resource.openai.azure.com/",
  "api_key": "sk-...",
  "deployment_name": "gpt-4o"
}`}
            response={`{
  "message": "OpenAI settings updated successfully"
}`}
          />
          <Endpoint
            method="GET"
            path="/api/settings/concurrency"
            description="Get current concurrency settings"
            response={`{
  "max_concurrent_uploads": 5,
  "max_concurrent_api_calls": 10
}`}
          />
          <Endpoint
            method="PUT"
            path="/api/settings/concurrency"
            description="Update concurrency settings"
            requestBody={`{
  "max_concurrent_uploads": 10,
  "max_concurrent_api_calls": 20
}`}
            response={`{
  "message": "Concurrency settings updated successfully"
}`}
          />
        </TabsContent>
      </Tabs>

      {/* Full Documentation Link */}
      <Card className="mt-8">
        <CardContent className="py-6">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium">Need more details?</h4>
              <p className="text-sm text-muted-foreground">
                View the complete API documentation in the repository
              </p>
            </div>
            <Button variant="outline" asChild>
              <a
                href="https://github.com/albertaga27/azure-doc-extraction-gbb-ai/blob/main/api_documentation.md"
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Full Documentation
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
