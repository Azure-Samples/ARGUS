"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Search,
  RefreshCw,
  Trash2,
  RotateCcw,
  Filter,
  Download,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  BarChart3,
  Calendar,
  Loader2,
  ChevronDown,
  Eye,
  ArrowUpDown,
  ArrowUp,
  ArrowDown
} from "lucide-react"
import { toast } from "sonner"

import { PageContainer } from "@/components/layout/page-container"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { backendClient, Document } from "@/lib/api-client"
import { formatDate, formatDuration, formatBytes } from "@/lib/utils"
import { DocumentDetailSheet } from "@/components/documents/document-detail-sheet"
import { AnalyticsCharts } from "@/components/documents/analytics-charts"

interface ProcessedDocument {
  id: string
  dataset: string
  fileName: string
  status: "completed" | "processing" | "failed"
  fileLanded: boolean
  ocrCompleted: boolean
  gptExtraction: boolean
  gptEvaluation: boolean
  gptSummary: boolean
  finished: boolean
  errors?: string
  timestamp: Date
  totalTime?: number
  pages?: number
  size?: number
  selected: boolean
}

function parseDocuments(documents: Document[]): ProcessedDocument[] {
  return documents.map((doc) => {
    // Parse dataset and filename from id or properties
    let dataset = "unknown"
    let fileName = "unknown"

    const docId = doc.id || ""
    if (docId.includes("__")) {
      const parts = docId.split("__")
      dataset = parts[0] || "unknown"
      fileName = parts[1] || "unknown"
    } else if (docId.includes("/")) {
      const parts = docId.split("/")
      dataset = parts[0] || "unknown"
      fileName = parts.slice(1).join("/") || "unknown"
    }

    // Get state from flattened or nested structure
    const state = doc.state as Record<string, boolean> | undefined || {}
    const properties = doc.properties as Record<string, unknown> | undefined || {}
    const extractedData = doc.extracted_data as Record<string, unknown> | undefined || {}

    const fileLanded = state.file_landed || false
    const ocrCompleted = state.ocr_completed || false
    const gptExtraction = state.gpt_extraction_completed || false
    const gptEvaluation = state.gpt_evaluation_completed || false
    const gptSummary = state.gpt_summary_completed || false
    const finished = state.processing_completed || gptSummary || gptEvaluation
    
    // Normalize errors to string (can be string, array, or undefined)
    let errorsStr = ''
    if (typeof doc.errors === 'string') {
      errorsStr = doc.errors
    } else if (Array.isArray(doc.errors) && doc.errors.length > 0) {
      errorsStr = JSON.stringify(doc.errors)
    }
    
    // Check for actual errors - state.error boolean OR non-empty errors
    const hasError = state.error === true || (errorsStr.length > 0 && errorsStr !== '[]')
    const errorMessage = hasError ? errorsStr : ""

    // Determine status - only failed if there's an actual error
    let status: "completed" | "processing" | "failed" = "processing"
    if (finished) status = "completed"
    else if (hasError) status = "failed"

    return {
      id: doc.id,
      dataset,
      fileName,
      status,
      fileLanded,
      ocrCompleted,
      gptExtraction,
      gptEvaluation,
      gptSummary,
      finished,
      errors: errorMessage,
      timestamp: new Date(doc.created_at || properties.request_timestamp as string || Date.now()),
      totalTime: doc.processing_time || properties.total_time_seconds as number,
      pages: doc.num_pages || properties.num_pages as number,
      size: properties.blob_size as number || 0,
      selected: false,
    }
  })
}

function StatusIcon({ status }: { status: "completed" | "processing" | "failed" }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="h-4 w-4 text-green-500" />
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />
    default:
      return <Clock className="h-4 w-4 text-yellow-500" />
  }
}

function StepIndicator({ completed }: { completed: boolean }) {
  if (completed) {
    return (
      <div className="flex items-center justify-center w-5 h-5 rounded-full bg-green-500/20">
        <CheckCircle className="h-3.5 w-3.5 text-green-500" />
      </div>
    )
  }
  return (
    <div className="flex items-center justify-center w-5 h-5 rounded-full bg-muted">
      <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40" />
    </div>
  )
}

export default function ExplorePage() {
  const [documents, setDocuments] = React.useState<ProcessedDocument[]>([])
  const [filteredDocuments, setFilteredDocuments] = React.useState<ProcessedDocument[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [selectedDocument, setSelectedDocument] = React.useState<ProcessedDocument | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false)
  const [documentsToDelete, setDocumentsToDelete] = React.useState<ProcessedDocument[]>([])

  // Filters
  const [datasetFilter, setDatasetFilter] = React.useState<string>("all")
  const [statusFilter, setStatusFilter] = React.useState<string>("all")
  const [searchQuery, setSearchQuery] = React.useState("")
  
  // Sorting
  type SortField = "fileName" | "dataset" | "status" | "totalTime" | "timestamp" | "pages"
  type SortDirection = "asc" | "desc"
  const [sortField, setSortField] = React.useState<SortField>("timestamp")
  const [sortDirection, setSortDirection] = React.useState<SortDirection>("desc")

  // Get unique datasets
  const uniqueDatasets = React.useMemo(() => {
    const datasets = new Set(documents.map((d) => d.dataset))
    return Array.from(datasets).sort()
  }, [documents])

  // Load documents
  async function loadDocuments() {
    setIsLoading(true)
    try {
      const response = await backendClient.listDocuments()
      const docs = parseDocuments(response.documents || [])
      setDocuments(docs.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime()))
    } catch (error) {
      console.error("Failed to load documents:", error)
      toast.error("Failed to load documents")
    } finally {
      setIsLoading(false)
    }
  }

  React.useEffect(() => {
    loadDocuments()
  }, [])

  // Apply filters and sorting
  React.useEffect(() => {
    let filtered = [...documents]

    if (datasetFilter !== "all") {
      filtered = filtered.filter((d) => d.dataset === datasetFilter)
    }

    if (statusFilter !== "all") {
      filtered = filtered.filter((d) => d.status === statusFilter)
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(
        (d) =>
          d.fileName.toLowerCase().includes(query) ||
          d.dataset.toLowerCase().includes(query)
      )
    }
    
    // Sort documents
    filtered = filtered.sort((a, b) => {
      let comparison = 0
      switch (sortField) {
        case "fileName":
          comparison = a.fileName.localeCompare(b.fileName)
          break
        case "dataset":
          comparison = a.dataset.localeCompare(b.dataset)
          break
        case "status":
          comparison = a.status.localeCompare(b.status)
          break
        case "totalTime":
          comparison = (a.totalTime || 0) - (b.totalTime || 0)
          break
        case "timestamp":
          comparison = a.timestamp.getTime() - b.timestamp.getTime()
          break
        case "pages":
          comparison = (a.pages || 0) - (b.pages || 0)
          break
      }
      return sortDirection === "asc" ? comparison : -comparison
    })

    setFilteredDocuments(filtered)
  }, [documents, datasetFilter, statusFilter, searchQuery, sortField, sortDirection])
  
  // Toggle sort
  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc")
    } else {
      setSortField(field)
      setSortDirection("asc")
    }
  }
  
  // Sort indicator component
  function SortIndicator({ field }: { field: SortField }) {
    if (sortField !== field) return <ArrowUpDown className="h-4 w-4 ml-1 opacity-50" />
    return sortDirection === "asc" 
      ? <ArrowUp className="h-4 w-4 ml-1" />
      : <ArrowDown className="h-4 w-4 ml-1" />
  }

  // Selection handlers
  function toggleSelection(id: string) {
    setDocuments((prev) =>
      prev.map((doc) =>
        doc.id === id ? { ...doc, selected: !doc.selected } : doc
      )
    )
  }

  function selectAll() {
    const allSelected = filteredDocuments.every((d) => d.selected)
    setDocuments((prev) =>
      prev.map((doc) => ({
        ...doc,
        selected: filteredDocuments.some((fd) => fd.id === doc.id) ? !allSelected : doc.selected,
      }))
    )
  }

  const selectedDocs = filteredDocuments.filter((d) => d.selected)

  // Delete handlers
  async function handleDelete() {
    try {
      for (const doc of documentsToDelete) {
        await backendClient.deleteDocument(doc.id)
      }
      toast.success(`Deleted ${documentsToDelete.length} document(s)`)
      setDocumentsToDelete([])
      setDeleteDialogOpen(false)
      loadDocuments()
    } catch (error) {
      console.error("Failed to delete:", error)
      toast.error("Failed to delete documents")
    }
  }

  // Reprocess handler
  async function handleReprocess(docs: ProcessedDocument[]) {
    try {
      for (const doc of docs) {
        await backendClient.reprocessDocument(doc.id)
      }
      toast.success(`Reprocessing ${docs.length} document(s)`, {
        description: "Processing will begin shortly. Refresh to see updates.",
      })
      loadDocuments()
    } catch (error) {
      console.error("Failed to reprocess:", error)
      toast.error("Failed to reprocess documents")
    }
  }

  // Stats
  const stats = React.useMemo(() => {
    const total = filteredDocuments.length
    const completed = filteredDocuments.filter((d) => d.status === "completed").length
    const processing = filteredDocuments.filter((d) => d.status === "processing").length
    const failed = filteredDocuments.filter((d) => d.status === "failed").length
    return { total, completed, processing, failed }
  }, [filteredDocuments])

  return (
    <PageContainer
      title="🔎 Explore Data"
      description="View and manage processed documents"
    >
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.completed}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Processing</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{stats.processing}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <Label className="mb-2 block">Search</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by filename..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="w-[200px]">
              <Label className="mb-2 block">Dataset</Label>
              <Select value={datasetFilter} onValueChange={setDatasetFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All datasets" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Datasets</SelectItem>
                  {uniqueDatasets.map((dataset) => (
                    <SelectItem key={dataset} value={dataset}>
                      {dataset}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-[200px]">
              <Label className="mb-2 block">Status</Label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="processing">Processing</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button variant="outline" onClick={loadDocuments} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Main Content Tabs */}
      <Tabs defaultValue="table" className="space-y-4">
        <TabsList>
          <TabsTrigger value="table" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Table
          </TabsTrigger>
          <TabsTrigger value="analytics" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Analytics
          </TabsTrigger>
        </TabsList>

        {/* Table Tab */}
        <TabsContent value="table">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Documents</CardTitle>
                  <CardDescription>
                    {selectedDocs.length > 0
                      ? `${selectedDocs.length} selected`
                      : `${filteredDocuments.length} documents`}
                  </CardDescription>
                </div>
                {selectedDocs.length > 0 && (
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleReprocess(selectedDocs)}
                    >
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Reprocess
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => {
                        setDocumentsToDelete(selectedDocs)
                        setDeleteDialogOpen(true)
                      }}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : filteredDocuments.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No documents found</p>
                </div>
              ) : (
                <ScrollArea className="h-[500px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[50px]">
                          <Checkbox
                            checked={
                              filteredDocuments.length > 0 &&
                              filteredDocuments.every((d) => d.selected)
                            }
                            onCheckedChange={selectAll}
                          />
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => toggleSort("fileName")}
                        >
                          <div className="flex items-center">
                            File Name
                            <SortIndicator field="fileName" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => toggleSort("dataset")}
                        >
                          <div className="flex items-center">
                            Dataset
                            <SortIndicator field="dataset" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => toggleSort("status")}
                        >
                          <div className="flex items-center">
                            Status
                            <SortIndicator field="status" />
                          </div>
                        </TableHead>
                        <TableHead>OCR</TableHead>
                        <TableHead>GPT</TableHead>
                        <TableHead>Eval</TableHead>
                        <TableHead>Summary</TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => toggleSort("totalTime")}
                        >
                          <div className="flex items-center">
                            Time
                            <SortIndicator field="totalTime" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => toggleSort("timestamp")}
                        >
                          <div className="flex items-center">
                            Date
                            <SortIndicator field="timestamp" />
                          </div>
                        </TableHead>
                        <TableHead className="w-[50px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredDocuments.map((doc) => (
                        <TableRow
                          key={doc.id}
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => setSelectedDocument(doc)}
                        >
                          <TableCell onClick={(e) => e.stopPropagation()}>
                            <Checkbox
                              checked={doc.selected}
                              onCheckedChange={() => toggleSelection(doc.id)}
                            />
                          </TableCell>
                          <TableCell className="font-medium max-w-[200px] truncate">
                            {doc.fileName}
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary">{doc.dataset}</Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <StatusIcon status={doc.status} />
                              <span className="capitalize text-sm">{doc.status}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <StepIndicator completed={doc.ocrCompleted} />
                          </TableCell>
                          <TableCell>
                            <StepIndicator completed={doc.gptExtraction} />
                          </TableCell>
                          <TableCell>
                            <StepIndicator completed={doc.gptEvaluation} />
                          </TableCell>
                          <TableCell>
                            <StepIndicator completed={doc.gptSummary} />
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {formatDuration(doc.totalTime)}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {formatDate(doc.timestamp)}
                          </TableCell>
                          <TableCell>
                            <Button variant="ghost" size="icon">
                              <Eye className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="analytics">
          <AnalyticsCharts documents={filteredDocuments} />
        </TabsContent>
      </Tabs>

      {/* Document Detail Sheet */}
      <DocumentDetailSheet
        document={selectedDocument}
        onClose={() => setSelectedDocument(null)}
        onReprocess={(doc) => handleReprocess([doc])}
        onDelete={(doc) => {
          setDocumentsToDelete([doc])
          setDeleteDialogOpen(true)
        }}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Documents</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {documentsToDelete.length} document(s)? 
              This will remove them from both Cosmos DB and Blob Storage. 
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageContainer>
  )
}
