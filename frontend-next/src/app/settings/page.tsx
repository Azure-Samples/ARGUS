"use client"

import * as React from "react"
import {
  Key,
  Server,
  Zap,
  Save,
  Loader2,
  RefreshCw,
  Eye,
  EyeOff,
  CheckCircle,
  AlertCircle,
  Info,
  Terminal,
  Cloud,
  FileCode,
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
import { Slider } from "@/components/ui/slider"
import { Badge } from "@/components/ui/badge"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { backendClient } from "@/lib/api-client"

interface OpenAISettingsResponse {
  openai_endpoint?: string
  openai_key?: string
  deployment_name?: string
  ocr_provider?: string
  mistral_endpoint?: string
  mistral_key?: string
  mistral_model?: string
  note?: string
}

interface ConcurrencySettingsResponse {
  enabled?: boolean
  current_max_runs?: number
  error?: string
}

export default function SettingsPage() {
  // OpenAI Settings state
  const [openaiEndpoint, setOpenaiEndpoint] = React.useState("")
  const [openaiKey, setOpenaiKey] = React.useState("")
  const [deploymentName, setDeploymentName] = React.useState("")
  const [showApiKey, setShowApiKey] = React.useState(false)
  const [isEnvBased, setIsEnvBased] = React.useState(false)
  const [isLoadingOpenai, setIsLoadingOpenai] = React.useState(true)
  const [isSavingOpenai, setIsSavingOpenai] = React.useState(false)

  // OCR Provider state
  const [ocrProvider, setOcrProvider] = React.useState<string>("azure")
  const [mistralEndpoint, setMistralEndpoint] = React.useState("")
  const [mistralKey, setMistralKey] = React.useState("")
  const [mistralModel, setMistralModel] = React.useState("mistral-document-ai-2505")
  const [showMistralKey, setShowMistralKey] = React.useState(false)
  const [isSavingOcr, setIsSavingOcr] = React.useState(false)

  // Concurrency Settings state (Logic App Manager)
  const [concurrencyEnabled, setConcurrencyEnabled] = React.useState(false)
  const [maxRuns, setMaxRuns] = React.useState(5)
  const [concurrencyError, setConcurrencyError] = React.useState<string | null>(null)
  const [isLoadingConcurrency, setIsLoadingConcurrency] = React.useState(true)
  const [isSavingConcurrency, setIsSavingConcurrency] = React.useState(false)

  // Health check status
  const [healthStatus, setHealthStatus] = React.useState<"connected" | "disconnected" | "checking">("checking")

  // Load settings on mount
  React.useEffect(() => {
    loadAllSettings()
    checkHealth()
  }, [])

  async function checkHealth() {
    setHealthStatus("checking")
    try {
      await backendClient.healthCheck()
      setHealthStatus("connected")
    } catch {
      setHealthStatus("disconnected")
    }
  }

  async function loadAllSettings() {
    await Promise.all([
      loadOpenAISettings(),
      loadConcurrencySettings(),
    ])
  }

  async function loadOpenAISettings() {
    setIsLoadingOpenai(true)
    try {
      const settings = await backendClient.getOpenAISettings() as OpenAISettingsResponse
      
      // Check if env-based
      const isEnv = settings.note?.startsWith('Configuration is read from environment variables') || false
      setIsEnvBased(isEnv)
      
      // Set OpenAI settings
      setOpenaiEndpoint(settings.openai_endpoint || "")
      setOpenaiKey(settings.openai_key === "***hidden***" ? "" : settings.openai_key || "")
      setDeploymentName(settings.deployment_name || "")
      
      // Set OCR settings
      setOcrProvider(settings.ocr_provider || "azure")
      setMistralEndpoint(settings.mistral_endpoint || "")
      setMistralKey(settings.mistral_key === "***HIDDEN***" ? "" : settings.mistral_key || "")
      setMistralModel(settings.mistral_model || "mistral-document-ai-2505")
    } catch (error) {
      console.error("Failed to load OpenAI settings:", error)
      toast.error("Failed to load settings")
    } finally {
      setIsLoadingOpenai(false)
    }
  }

  async function saveOpenAISettings() {
    if (!openaiEndpoint || !deploymentName) {
      toast.error("Endpoint and Deployment Name are required")
      return
    }
    
    setIsSavingOpenai(true)
    try {
      const updateData: Record<string, unknown> = {
        openai_endpoint: openaiEndpoint,
        openai_deployment_name: deploymentName,
      }
      // Only include key if provided
      if (openaiKey) {
        updateData.openai_key = openaiKey
      }
      
      await backendClient.updateOpenAISettings(updateData)
      toast.success("OpenAI settings updated", {
        description: isEnvBased ? "Changes are active immediately for new requests" : undefined
      })
      loadOpenAISettings()
    } catch (error) {
      console.error("Failed to save OpenAI settings:", error)
      toast.error("Failed to save OpenAI settings")
    } finally {
      setIsSavingOpenai(false)
    }
  }

  async function saveOcrSettings() {
    if (ocrProvider === "mistral") {
      if (!mistralEndpoint) {
        toast.error("Mistral endpoint is required")
        return
      }
    }
    
    setIsSavingOcr(true)
    try {
      const updateData: Record<string, unknown> = {
        ocr_provider: ocrProvider,
      }
      
      if (ocrProvider === "mistral") {
        updateData.mistral_endpoint = mistralEndpoint
        if (mistralKey) {
          updateData.mistral_key = mistralKey
        }
        updateData.mistral_model = mistralModel
      }
      
      await backendClient.updateOpenAISettings(updateData)
      toast.success(`OCR provider updated to ${ocrProvider === "azure" ? "Azure Document Intelligence" : "Mistral OCR"}`, {
        description: "Changes are active immediately for new document processing"
      })
      loadOpenAISettings()
    } catch (error) {
      console.error("Failed to save OCR settings:", error)
      toast.error("Failed to save OCR settings")
    } finally {
      setIsSavingOcr(false)
    }
  }

  async function loadConcurrencySettings() {
    setIsLoadingConcurrency(true)
    try {
      const settings = await backendClient.getConcurrencySettings() as ConcurrencySettingsResponse
      setConcurrencyEnabled(settings.enabled || false)
      setMaxRuns(settings.current_max_runs || 5)
      setConcurrencyError(settings.error || null)
    } catch (error) {
      console.error("Failed to load concurrency settings:", error)
      setConcurrencyEnabled(false)
      setConcurrencyError("Failed to connect to Logic App Manager")
    } finally {
      setIsLoadingConcurrency(false)
    }
  }

  async function saveConcurrencySettings() {
    setIsSavingConcurrency(true)
    try {
      await backendClient.updateConcurrencySettings({ max_runs: maxRuns })
      toast.success(`Concurrency updated to ${maxRuns} concurrent runs`)
      loadConcurrencySettings()
    } catch (error) {
      console.error("Failed to save concurrency settings:", error)
      toast.error("Failed to update concurrency settings")
    } finally {
      setIsSavingConcurrency(false)
    }
  }

  return (
    <PageContainer
      title="⚙️ Settings"
      description="Configure API endpoints, credentials, and processing options"
    >
      {/* Connection Status */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CardTitle className="text-lg">Backend Connection</CardTitle>
              {healthStatus === "connected" && (
                <Badge variant="default" className="bg-green-500">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  Connected
                </Badge>
              )}
              {healthStatus === "disconnected" && (
                <Badge variant="destructive">
                  <AlertCircle className="h-3 w-3 mr-1" />
                  Disconnected
                </Badge>
              )}
              {healthStatus === "checking" && (
                <Badge variant="secondary">
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  Checking...
                </Badge>
              )}
            </div>
            <Button variant="outline" size="sm" onClick={() => { checkHealth(); loadAllSettings(); }}>
              <RefreshCw className={`h-4 w-4 mr-2 ${healthStatus === "checking" ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        {/* OpenAI Configuration */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Key className="h-5 w-5 text-muted-foreground" />
              <CardTitle>OpenAI Configuration</CardTitle>
            </div>
            <CardDescription>
              Configure Azure OpenAI endpoint and credentials
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoadingOpenai ? (
              <div className="space-y-4">
                <div className="h-10 bg-muted animate-pulse rounded" />
                <div className="h-10 bg-muted animate-pulse rounded" />
                <div className="h-10 bg-muted animate-pulse rounded" />
              </div>
            ) : (
              <>
                {isEnvBased && (
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertTitle>Environment Variable Configuration</AlertTitle>
                    <AlertDescription>
                      Configuration is managed via environment variables. Runtime updates are temporary and will be lost when the container restarts.
                    </AlertDescription>
                  </Alert>
                )}
                
                <div className="space-y-2">
                  <Label htmlFor="endpoint">Azure OpenAI Endpoint</Label>
                  <Input
                    id="endpoint"
                    placeholder="https://your-resource.openai.azure.com/"
                    value={openaiEndpoint}
                    onChange={(e) => setOpenaiEndpoint(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="api-key">API Key</Label>
                  <div className="relative">
                    <Input
                      id="api-key"
                      type={showApiKey ? "text" : "password"}
                      placeholder={isEnvBased ? "Enter new key or leave blank to keep current" : "Enter your API key"}
                      value={openaiKey}
                      onChange={(e) => setOpenaiKey(e.target.value)}
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute right-0 top-0 h-full px-3"
                      onClick={() => setShowApiKey(!showApiKey)}
                    >
                      {showApiKey ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="deployment">Model Deployment Name</Label>
                  <Input
                    id="deployment"
                    placeholder="gpt-4o"
                    value={deploymentName}
                    onChange={(e) => setDeploymentName(e.target.value)}
                  />
                </div>
                <Button
                  onClick={saveOpenAISettings}
                  disabled={isSavingOpenai}
                  className="w-full"
                >
                  {isSavingOpenai ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  {isEnvBased ? "Update Runtime Settings" : "Save OpenAI Settings"}
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* OCR Provider Configuration */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Server className="h-5 w-5 text-muted-foreground" />
              <CardTitle>OCR Provider</CardTitle>
            </div>
            <CardDescription>
              Select the OCR provider for document processing
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoadingOpenai ? (
              <div className="space-y-4">
                <div className="h-10 bg-muted animate-pulse rounded" />
                <div className="h-20 bg-muted animate-pulse rounded" />
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label>Provider</Label>
                  <Select value={ocrProvider} onValueChange={setOcrProvider}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select OCR provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="azure">
                        <div className="flex items-center gap-2">
                          <span>Azure Document Intelligence</span>
                          <Badge variant="secondary" className="text-xs">Recommended</Badge>
                        </div>
                      </SelectItem>
                      <SelectItem value="mistral">Mistral Document AI</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="rounded-lg bg-muted p-4 text-sm">
                  {ocrProvider === "azure" ? (
                    <div className="space-y-2">
                      <p className="font-medium">Azure Document Intelligence</p>
                      <p className="text-muted-foreground">
                        Microsoft&apos;s enterprise-grade OCR service with layout analysis, 
                        table extraction, and form recognition.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="font-medium">Mistral Document AI</p>
                      <p className="text-muted-foreground">
                        Mistral&apos;s document understanding API. Good for general text 
                        extraction with lower costs.
                      </p>
                    </div>
                  )}
                </div>

                {/* Mistral Settings - show only when Mistral is selected */}
                {ocrProvider === "mistral" && (
                  <div className="space-y-4 pt-4 border-t">
                    <div className="space-y-2">
                      <Label htmlFor="mistral-endpoint">Mistral Endpoint</Label>
                      <Input
                        id="mistral-endpoint"
                        placeholder="https://your-endpoint.services.ai.azure.com/providers/mistral/azure/ocr"
                        value={mistralEndpoint}
                        onChange={(e) => setMistralEndpoint(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="mistral-key">Mistral API Key</Label>
                      <div className="relative">
                        <Input
                          id="mistral-key"
                          type={showMistralKey ? "text" : "password"}
                          placeholder="Enter your Mistral API key"
                          value={mistralKey}
                          onChange={(e) => setMistralKey(e.target.value)}
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="absolute right-0 top-0 h-full px-3"
                          onClick={() => setShowMistralKey(!showMistralKey)}
                        >
                          {showMistralKey ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="mistral-model">Mistral Model</Label>
                      <Input
                        id="mistral-model"
                        placeholder="mistral-document-ai-2505"
                        value={mistralModel}
                        onChange={(e) => setMistralModel(e.target.value)}
                      />
                    </div>
                  </div>
                )}

                <Button
                  onClick={saveOcrSettings}
                  disabled={isSavingOcr}
                  className="w-full"
                >
                  {isSavingOcr ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  Update OCR Provider
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* Concurrency Settings - Logic App Manager */}
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-muted-foreground" />
              <CardTitle>Concurrency Settings</CardTitle>
            </div>
            <CardDescription>
              Control how many files can be processed simultaneously via Logic App Manager
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingConcurrency ? (
              <div className="space-y-4">
                <div className="h-20 bg-muted animate-pulse rounded" />
              </div>
            ) : !concurrencyEnabled ? (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Logic App Manager Unavailable</AlertTitle>
                <AlertDescription>
                  {concurrencyError || "Logic App Manager is not configured or not available. Please check your deployment configuration."}
                </AlertDescription>
              </Alert>
            ) : (
              <div className="space-y-6">
                <Alert>
                  <CheckCircle className="h-4 w-4" />
                  <AlertTitle>Logic App Manager Connected</AlertTitle>
                  <AlertDescription>
                    Concurrency control is active. Adjust the slider to change how many files can be processed in parallel.
                  </AlertDescription>
                </Alert>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Label>Maximum Concurrent Runs</Label>
                    <Badge variant="outline" className="text-lg font-mono">
                      {maxRuns}
                    </Badge>
                  </div>
                  <Slider
                    value={[maxRuns]}
                    onValueChange={([value]) => setMaxRuns(value)}
                    min={1}
                    max={100}
                    step={1}
                  />
                  <div className="text-sm text-muted-foreground space-y-2">
                    {maxRuns <= 5 && (
                      <p className="text-blue-600 dark:text-blue-400">
                        💡 <strong>Conservative:</strong> Lower values provide more controlled processing with lower resource usage
                      </p>
                    )}
                    {maxRuns > 5 && maxRuns <= 20 && (
                      <p className="text-green-600 dark:text-green-400">
                        💡 <strong>Balanced:</strong> Good for most scenarios with mixed file sizes
                      </p>
                    )}
                    {maxRuns > 20 && (
                      <p className="text-amber-600 dark:text-amber-400">
                        💡 <strong>Aggressive:</strong> Faster processing, requires sufficient Azure resources (Document Intelligence, OpenAI, Cosmos DB)
                      </p>
                    )}
                  </div>
                </div>

                <Button
                  onClick={saveConcurrencySettings}
                  disabled={isSavingConcurrency}
                  className="w-full"
                >
                  {isSavingConcurrency ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  Update Concurrency
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Persistent Changes Instructions */}
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Info className="h-5 w-5 text-muted-foreground" />
              <CardTitle>Making Changes Permanent</CardTitle>
            </div>
            <CardDescription>
              Runtime changes above are temporary. For persistent changes that survive container restarts, update your deployment configuration.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Alert className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Important</AlertTitle>
              <AlertDescription>
                Settings configured above are stored in memory and will be reset when the container restarts. 
                For production deployments, update the environment variables using one of the methods below.
              </AlertDescription>
            </Alert>

            <Accordion type="single" collapsible className="w-full">
              <AccordionItem value="azure-portal">
                <AccordionTrigger>
                  <div className="flex items-center gap-2">
                    <Cloud className="h-4 w-4" />
                    Option 1: Update via Azure Portal (Recommended)
                  </div>
                </AccordionTrigger>
                <AccordionContent className="space-y-3 text-sm">
                  <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
                    <li>Go to <strong>Azure Portal</strong> → <strong>Container Apps</strong> → <strong>Your Backend App</strong></li>
                    <li>Navigate to <strong>Settings</strong> → <strong>Environment variables</strong></li>
                    <li>Update OpenAI variables:
                      <ul className="list-disc list-inside ml-4 mt-1">
                        <li><code className="bg-muted px-1 rounded">AZURE_OPENAI_ENDPOINT</code></li>
                        <li><code className="bg-muted px-1 rounded">AZURE_OPENAI_API_KEY</code></li>
                        <li><code className="bg-muted px-1 rounded">AZURE_OPENAI_DEPLOYMENT_NAME</code></li>
                      </ul>
                    </li>
                    <li>For OCR provider (optional):
                      <ul className="list-disc list-inside ml-4 mt-1">
                        <li><code className="bg-muted px-1 rounded">OCR_PROVIDER</code> - Set to <code className="bg-muted px-1 rounded">azure</code> or <code className="bg-muted px-1 rounded">mistral</code></li>
                        <li><code className="bg-muted px-1 rounded">MISTRAL_ENDPOINT</code> - Mistral API endpoint (if using Mistral)</li>
                        <li><code className="bg-muted px-1 rounded">MISTRAL_API_KEY</code> - Mistral API key (if using Mistral)</li>
                        <li><code className="bg-muted px-1 rounded">MISTRAL_DOC_AI_MODEL</code> - Model name (default: mistral-document-ai-2505)</li>
                      </ul>
                    </li>
                    <li><strong>Restart</strong> the container app for changes to take effect</li>
                  </ol>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="azure-cli">
                <AccordionTrigger>
                  <div className="flex items-center gap-2">
                    <Terminal className="h-4 w-4" />
                    Option 2: Update via Azure CLI
                  </div>
                </AccordionTrigger>
                <AccordionContent className="space-y-4">
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Update OpenAI settings:</p>
                    <div className="bg-muted rounded-lg p-4 font-mono text-sm overflow-x-auto">
                      <pre className="whitespace-pre-wrap">{`az containerapp update \\
  --name <your-backend-app-name> \\
  --resource-group <your-resource-group> \\
  --set-env-vars \\
    AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/" \\
    AZURE_OPENAI_API_KEY="your-api-key" \\
    AZURE_OPENAI_DEPLOYMENT_NAME="your-deployment-name"`}</pre>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Update OCR provider (optional - for Mistral):</p>
                    <div className="bg-muted rounded-lg p-4 font-mono text-sm overflow-x-auto">
                      <pre className="whitespace-pre-wrap">{`az containerapp update \\
  --name <your-backend-app-name> \\
  --resource-group <your-resource-group> \\
  --set-env-vars \\
    OCR_PROVIDER="mistral" \\
    MISTRAL_ENDPOINT="https://your-endpoint.services.ai.azure.com/..." \\
    MISTRAL_API_KEY="your-mistral-key" \\
    MISTRAL_DOC_AI_MODEL="mistral-document-ai-2505"`}</pre>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="azd">
                <AccordionTrigger>
                  <div className="flex items-center gap-2">
                    <FileCode className="h-4 w-4" />
                    Option 3: Update via Infrastructure (azd)
                  </div>
                </AccordionTrigger>
                <AccordionContent className="space-y-3 text-sm">
                  <p className="text-muted-foreground">If you&apos;re using Azure Developer CLI (azd):</p>
                  <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
                    <li>Update the environment variables in your <code className="bg-muted px-1 rounded">infra/main.parameters.json</code> file</li>
                    <li>Available environment variables:
                      <ul className="list-disc list-inside ml-4 mt-1">
                        <li><code className="bg-muted px-1 rounded">AZURE_OPENAI_ENDPOINT</code>, <code className="bg-muted px-1 rounded">AZURE_OPENAI_API_KEY</code>, <code className="bg-muted px-1 rounded">AZURE_OPENAI_DEPLOYMENT_NAME</code></li>
                        <li><code className="bg-muted px-1 rounded">OCR_PROVIDER</code>, <code className="bg-muted px-1 rounded">MISTRAL_ENDPOINT</code>, <code className="bg-muted px-1 rounded">MISTRAL_API_KEY</code>, <code className="bg-muted px-1 rounded">MISTRAL_DOC_AI_MODEL</code></li>
                      </ul>
                    </li>
                    <li>Run <code className="bg-muted px-1 rounded">azd up</code> to redeploy with new settings</li>
                  </ol>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  )
}
