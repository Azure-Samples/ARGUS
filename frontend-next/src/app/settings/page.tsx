"use client"

import * as React from "react"
import { motion } from "framer-motion"
import {
  Settings2,
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
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { backendClient } from "@/lib/api-client"

interface OpenAISettings {
  endpoint: string
  api_key: string
  deployment_name: string
}

interface MistralSettings {
  endpoint: string
  api_key: string
  model: string
}

interface ConcurrencySettings {
  max_concurrent_uploads: number
  max_concurrent_api_calls: number
}

export default function SettingsPage() {
  // OpenAI Settings
  const [openaiSettings, setOpenaiSettings] = React.useState<OpenAISettings>({
    endpoint: "",
    api_key: "",
    deployment_name: "",
  })
  const [showApiKey, setShowApiKey] = React.useState(false)
  const [isLoadingOpenai, setIsLoadingOpenai] = React.useState(true)
  const [isSavingOpenai, setIsSavingOpenai] = React.useState(false)

  // OCR Provider
  const [ocrProvider, setOcrProvider] = React.useState<string>("azure")
  const [mistralSettings, setMistralSettings] = React.useState<MistralSettings>({
    endpoint: "",
    api_key: "",
    model: "mistral-document-ai-2505",
  })
  const [showMistralKey, setShowMistralKey] = React.useState(false)
  const [isLoadingOcr, setIsLoadingOcr] = React.useState(true)
  const [isSavingOcr, setIsSavingOcr] = React.useState(false)

  // Concurrency Settings
  const [concurrencySettings, setConcurrencySettings] = React.useState<ConcurrencySettings>({
    max_concurrent_uploads: 5,
    max_concurrent_api_calls: 10,
  })
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
      const settings = await backendClient.getOpenAISettings() as { endpoint?: string; api_key?: string; deployment_name?: string }
      setOpenaiSettings({
        endpoint: settings.endpoint || "",
        api_key: settings.api_key || "",
        deployment_name: settings.deployment_name || "",
      })
    } catch (error) {
      console.error("Failed to load OpenAI settings:", error)
      toast.error("Failed to load OpenAI settings")
    } finally {
      setIsLoadingOpenai(false)
    }
  }

  async function saveOpenAISettings() {
    setIsSavingOpenai(true)
    try {
      await backendClient.updateOpenAISettings(openaiSettings as unknown as Record<string, unknown>)
      toast.success("OpenAI settings saved successfully")
    } catch (error) {
      console.error("Failed to save OpenAI settings:", error)
      toast.error("Failed to save OpenAI settings")
    } finally {
      setIsSavingOpenai(false)
    }
  }

  async function loadConcurrencySettings() {
    setIsLoadingConcurrency(true)
    try {
      const settings = await backendClient.getConcurrencySettings() as { max_concurrent_uploads?: number; max_concurrent_api_calls?: number }
      setConcurrencySettings({
        max_concurrent_uploads: settings.max_concurrent_uploads || 5,
        max_concurrent_api_calls: settings.max_concurrent_api_calls || 10,
      })
    } catch (error) {
      console.error("Failed to load concurrency settings:", error)
      toast.error("Failed to load concurrency settings")
    } finally {
      setIsLoadingConcurrency(false)
    }
  }

  async function saveConcurrencySettings() {
    setIsSavingConcurrency(true)
    try {
      await backendClient.updateConcurrencySettings(concurrencySettings as unknown as Record<string, unknown>)
      toast.success("Concurrency settings saved successfully")
    } catch (error) {
      console.error("Failed to save concurrency settings:", error)
      toast.error("Failed to save concurrency settings")
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
            <Button variant="outline" size="sm" onClick={checkHealth}>
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
                <div className="space-y-2">
                  <Label htmlFor="endpoint">Endpoint URL</Label>
                  <Input
                    id="endpoint"
                    placeholder="https://your-resource.openai.azure.com/"
                    value={openaiSettings.endpoint}
                    onChange={(e) =>
                      setOpenaiSettings((prev) => ({ ...prev, endpoint: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="api-key">API Key</Label>
                  <div className="relative">
                    <Input
                      id="api-key"
                      type={showApiKey ? "text" : "password"}
                      placeholder="Enter your API key"
                      value={openaiSettings.api_key}
                      onChange={(e) =>
                        setOpenaiSettings((prev) => ({ ...prev, api_key: e.target.value }))
                      }
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
                  <Label htmlFor="deployment">Deployment Name</Label>
                  <Input
                    id="deployment"
                    placeholder="gpt-4o"
                    value={openaiSettings.deployment_name}
                    onChange={(e) =>
                      setOpenaiSettings((prev) => ({ ...prev, deployment_name: e.target.value }))
                    }
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
                  Save OpenAI Settings
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
                  <SelectItem value="mistral">Mistral OCR</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="rounded-lg bg-muted p-4 text-sm">
              {ocrProvider === "azure" ? (
                <div className="space-y-2">
                  <p className="font-medium">Azure Document Intelligence</p>
                  <p className="text-muted-foreground">
                    Uses Azure AI Document Intelligence for high-quality OCR with
                    layout analysis, table extraction, and form recognition.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="font-medium">Mistral OCR</p>
                  <p className="text-muted-foreground">
                    Uses Mistral&apos;s vision capabilities for OCR. Good for
                    general document processing with lower costs.
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
                    value={mistralSettings.endpoint}
                    onChange={(e) =>
                      setMistralSettings((prev) => ({ ...prev, endpoint: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="mistral-key">Mistral API Key</Label>
                  <div className="relative">
                    <Input
                      id="mistral-key"
                      type={showMistralKey ? "text" : "password"}
                      placeholder="Enter your Mistral API key"
                      value={mistralSettings.api_key}
                      onChange={(e) =>
                        setMistralSettings((prev) => ({ ...prev, api_key: e.target.value }))
                      }
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
                    value={mistralSettings.model}
                    onChange={(e) =>
                      setMistralSettings((prev) => ({ ...prev, model: e.target.value }))
                    }
                  />
                </div>
              </div>
            )}

            <Button
              onClick={async () => {
                setIsSavingOcr(true)
                try {
                  const updateData: Record<string, unknown> = {
                    ocr_provider: ocrProvider,
                  }
                  if (ocrProvider === "mistral") {
                    if (!mistralSettings.endpoint) {
                      toast.error("Mistral endpoint is required")
                      return
                    }
                    updateData.mistral_endpoint = mistralSettings.endpoint
                    if (mistralSettings.api_key) {
                      updateData.mistral_key = mistralSettings.api_key
                    }
                    updateData.mistral_model = mistralSettings.model
                  }
                  await backendClient.updateOpenAISettings(updateData)
                  toast.success("OCR provider saved", {
                    description: `Using ${ocrProvider === "azure" ? "Azure Document Intelligence" : "Mistral OCR"}`,
                  })
                } catch (error) {
                  console.error("Failed to save OCR settings:", error)
                  toast.error("Failed to save OCR settings")
                } finally {
                  setIsSavingOcr(false)
                }
              }}
              disabled={isSavingOcr}
              className="w-full"
            >
              {isSavingOcr ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Save OCR Settings
            </Button>
          </CardContent>
        </Card>

        {/* Concurrency Settings */}
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-muted-foreground" />
              <CardTitle>Concurrency Settings</CardTitle>
            </div>
            <CardDescription>
              Control parallel processing limits for optimal performance
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingConcurrency ? (
              <div className="space-y-8">
                <div className="h-20 bg-muted animate-pulse rounded" />
                <div className="h-20 bg-muted animate-pulse rounded" />
              </div>
            ) : (
              <div className="space-y-8">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Label>Max Concurrent Uploads</Label>
                    <Badge variant="outline" className="text-lg font-mono">
                      {concurrencySettings.max_concurrent_uploads}
                    </Badge>
                  </div>
                  <Slider
                    value={[concurrencySettings.max_concurrent_uploads]}
                    onValueChange={([value]) =>
                      setConcurrencySettings((prev) => ({
                        ...prev,
                        max_concurrent_uploads: value,
                      }))
                    }
                    min={1}
                    max={20}
                    step={1}
                  />
                  <p className="text-sm text-muted-foreground">
                    Number of files that can be uploaded simultaneously. Higher values
                    speed up batch uploads but may impact browser performance.
                  </p>
                </div>

                <Separator />

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Label>Max Concurrent API Calls</Label>
                    <Badge variant="outline" className="text-lg font-mono">
                      {concurrencySettings.max_concurrent_api_calls}
                    </Badge>
                  </div>
                  <Slider
                    value={[concurrencySettings.max_concurrent_api_calls]}
                    onValueChange={([value]) =>
                      setConcurrencySettings((prev) => ({
                        ...prev,
                        max_concurrent_api_calls: value,
                      }))
                    }
                    min={1}
                    max={50}
                    step={1}
                  />
                  <p className="text-sm text-muted-foreground">
                    Number of parallel API calls for document processing. Higher values
                    increase throughput but may hit rate limits.
                  </p>
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
                  Save Concurrency Settings
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  )
}
