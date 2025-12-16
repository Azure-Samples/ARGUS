"use client"

import * as React from "react"
import { motion } from "framer-motion"
import {
  BookOpen,
  Upload,
  Search,
  FolderPlus,
  RefreshCw,
  Database,
  Cloud,
  Brain,
  FileText,
  CheckCircle,
  XCircle,
  MinusCircle,
  ExternalLink,
  ChevronRight,
} from "lucide-react"

import { PageContainer } from "@/components/layout/page-container"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

const sections = [
  {
    id: "uploading",
    icon: Upload,
    title: "1. Uploading Files",
    content: [
      {
        subtitle: "Navigate to the \"Process Files\" tab",
        description: "This is where you'll configure and upload your documents for processing.",
      },
      {
        subtitle: "Select a Dataset",
        description: "Choose a dataset from the dropdown menu. The selected dataset will load its corresponding model prompt and example schema.",
      },
      {
        subtitle: "Configure the Dataset (Optional)",
        description: "Modify the model prompt or example schema if needed. Click 'Save Configuration' to update.",
      },
      {
        subtitle: "Upload Files",
        description: "Use the file uploader to select PDF files for processing. Click 'Submit' to upload the files directly to cloud storage. The uploaded files are processed automatically using the selected dataset's configuration.",
      },
    ],
  },
  {
    id: "exploring",
    icon: Search,
    title: "2. Exploring Data",
    content: [
      {
        subtitle: "Navigate to the \"Explore Data\" tab",
        description: "View and manage all processed documents from this tab.",
      },
      {
        subtitle: "View Document Statistics",
        description: "See overview metrics including total documents, processed count, errors, and datasets.",
      },
      {
        subtitle: "Filter and Search",
        description: "Use the dataset filter to view documents from specific datasets. Browse the document list with processing status indicators.",
      },
      {
        subtitle: "Analyze Processing Status",
        description: "View charts showing processing status distribution and dataset distribution across your documents.",
      },
      {
        subtitle: "View Document Details",
        description: "Select individual documents to view detailed information, extracted content, and processing metadata.",
      },
    ],
  },
  {
    id: "datasets",
    icon: FolderPlus,
    title: "3. Adding New Dataset",
    content: [
      {
        subtitle: "Navigate to the \"Process Files\" tab",
        description: "New datasets can be created from the processing page.",
      },
      {
        subtitle: "Expand \"Create New Dataset\" section",
        description: "Click on the accordion to reveal the new dataset form.",
      },
      {
        subtitle: "Configure Your Dataset",
        description: "Enter a new dataset name, model prompt, and example schema. Click 'Create Dataset' to save. The new dataset will be available for selection immediately.",
      },
    ],
  },
  {
    id: "notes",
    icon: BookOpen,
    title: "4. Additional Notes",
    content: [
      {
        subtitle: "Reprocessing Failed Files",
        description: "For files that have failed, you can trigger reprocessing from the \"Explore Data\" tab by selecting the document and clicking the reprocess button.",
      },
      {
        subtitle: "Handling Long Documents",
        description: "Extraction accuracy might take a hit on very long documents. In such cases, we recommend splitting the documents into smaller parts before uploading.",
      },
    ],
  },
]

const pipelineSteps = [
  {
    title: "File Upload and Storage",
    description: "Uploaded files are sent to Azure Blob Storage, organized into folders based on the selected dataset.",
    icon: Cloud,
  },
  {
    title: "Triggering Processing",
    description: "The upload triggers an Azure Function to start the processing pipeline using Azure Document Intelligence OCR and GPT-4 Vision.",
    icon: RefreshCw,
  },
  {
    title: "Data Extraction",
    description: "Azure Document Intelligence OCR extracts text and structure. GPT-4 Vision processes this to generate structured data based on the provided schema.",
    icon: Brain,
  },
  {
    title: "Data Storage",
    description: "Extracted data is stored in Cosmos DB along with metadata and processing logs. The system maintains audit trails for each processed file.",
    icon: Database,
  },
  {
    title: "Data Retrieval",
    description: "The Explore Data tab fetches data from Cosmos DB, displaying processing status and details for each file.",
    icon: FileText,
  },
]

export default function InstructionsPage() {
  return (
    <PageContainer
      title="📖 Instructions"
      description="Learn how to use the ARGUS document processing system"
    >
      {/* Introduction */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            How to Use the ARGUS System
          </CardTitle>
          <CardDescription>
            A comprehensive guide to document processing with ARGUS
          </CardDescription>
        </CardHeader>
        <CardContent className="prose prose-sm dark:prose-invert max-w-none">
          <p>
            The ARGUS System is a comprehensive document processing platform that uses Azure AI
            services to extract structured data from PDF files. The system uses direct cloud
            service integration for fast and efficient processing.
          </p>
          <div className="grid gap-4 md:grid-cols-3 mt-6 not-prose">
            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted">
              <div className="p-2 rounded-md bg-primary/10">
                <FileText className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-medium text-sm">Frontend</p>
                <p className="text-xs text-muted-foreground">Next.js web interface</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted">
              <div className="p-2 rounded-md bg-primary/10">
                <Cloud className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-medium text-sm">Azure Services</p>
                <p className="text-xs text-muted-foreground">Doc Intelligence, OpenAI, Storage</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted">
              <div className="p-2 rounded-md bg-primary/10">
                <Database className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-medium text-sm">Data Storage</p>
                <p className="text-xs text-muted-foreground">Cosmos DB + Blob Storage</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Step-by-Step Instructions */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Step-by-Step Instructions</CardTitle>
        </CardHeader>
        <CardContent>
          <Accordion type="multiple" defaultValue={["uploading"]} className="space-y-4">
            {sections.map((section) => (
              <AccordionItem key={section.id} value={section.id} className="border rounded-lg px-4">
                <AccordionTrigger className="hover:no-underline py-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-md bg-primary/10">
                      <section.icon className="h-5 w-5 text-primary" />
                    </div>
                    <span className="font-semibold">{section.title}</span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pt-2 pb-4">
                  <div className="space-y-4 pl-12">
                    {section.content.map((item, index) => (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="flex gap-3"
                      >
                        <ChevronRight className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="font-medium">{item.subtitle}</p>
                          <p className="text-sm text-muted-foreground mt-1">
                            {item.description}
                          </p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </CardContent>
      </Card>

      {/* What is a Dataset? */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderPlus className="h-5 w-5" />
            What is a Dataset?
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground mb-4">
            A dataset defines how documents should be processed, including:
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="p-4 rounded-lg border">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="secondary">Model Prompt</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Instructions for the AI model on how to extract data from documents. 
                This guides the extraction behavior and output format.
              </p>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="secondary">Example Schema</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                The target data structure to be extracted. Can be empty—in this case, 
                the AI model will create a schema based on the document content.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Status Indicators */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Status Indicators</CardTitle>
          <CardDescription>Understanding document processing status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="flex items-center gap-3 p-4 rounded-lg border">
              <CheckCircle className="h-6 w-6 text-green-500" />
              <div>
                <p className="font-medium">Completed</p>
                <p className="text-sm text-muted-foreground">Successfully processed</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-4 rounded-lg border">
              <XCircle className="h-6 w-6 text-red-500" />
              <div>
                <p className="font-medium">Failed</p>
                <p className="text-sm text-muted-foreground">Processing error occurred</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-4 rounded-lg border">
              <MinusCircle className="h-6 w-6 text-yellow-500" />
              <div>
                <p className="font-medium">Processing</p>
                <p className="text-sm text-muted-foreground">Still being processed</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Processing Pipeline */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Processing Pipeline</CardTitle>
          <CardDescription>How documents flow through the system</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="relative">
            {pipelineSteps.map((step, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex gap-4 mb-6 last:mb-0"
              >
                <div className="relative flex flex-col items-center">
                  <div className="p-3 rounded-full bg-primary/10 border-2 border-primary z-10">
                    <step.icon className="h-5 w-5 text-primary" />
                  </div>
                  {index < pipelineSteps.length - 1 && (
                    <div className="w-0.5 h-full bg-border absolute top-12" />
                  )}
                </div>
                <div className="flex-1 pt-1">
                  <h4 className="font-semibold mb-1">{step.title}</h4>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Additional Resources */}
      <Card>
        <CardHeader>
          <CardTitle>Additional Resources</CardTitle>
        </CardHeader>
        <CardContent>
          <a
            href="https://github.com/albertaga27/azure-doc-extraction-gbb-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-primary hover:underline"
          >
            <ExternalLink className="h-4 w-4" />
            View Source Code on GitHub
          </a>
          <Separator className="my-4" />
          <p className="text-sm text-muted-foreground">
            This guide provides a comprehensive overview of the ARGUS System, ensuring that users
            can effectively upload, process, and manage their documents with ease.
          </p>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
