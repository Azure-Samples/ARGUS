"use client"

import * as React from "react"
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  LineChart,
  Line,
} from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

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

interface AnalyticsChartsProps {
  documents: ProcessedDocument[]
}

const COLORS = {
  completed: "#22c55e",
  processing: "#eab308",
  failed: "#ef4444",
}

const PIE_COLORS = ["#22c55e", "#eab308", "#ef4444"]

export function AnalyticsCharts({ documents }: AnalyticsChartsProps) {
  // Status distribution
  const statusData = React.useMemo(() => {
    const counts = {
      completed: documents.filter((d) => d.status === "completed").length,
      processing: documents.filter((d) => d.status === "processing").length,
      failed: documents.filter((d) => d.status === "failed").length,
    }
    return [
      { name: "Completed", value: counts.completed, color: COLORS.completed },
      { name: "Processing", value: counts.processing, color: COLORS.processing },
      { name: "Failed", value: counts.failed, color: COLORS.failed },
    ].filter((d) => d.value > 0)
  }, [documents])

  // Documents by dataset
  const datasetData = React.useMemo(() => {
    const datasetCounts: Record<string, { completed: number; processing: number; failed: number }> = {}
    documents.forEach((doc) => {
      if (!datasetCounts[doc.dataset]) {
        datasetCounts[doc.dataset] = { completed: 0, processing: 0, failed: 0 }
      }
      datasetCounts[doc.dataset][doc.status]++
    })
    return Object.entries(datasetCounts).map(([name, counts]) => ({
      name,
      ...counts,
    }))
  }, [documents])

  // Processing time distribution
  const processingTimeData = React.useMemo(() => {
    return documents
      .filter((d) => d.totalTime !== undefined && d.totalTime > 0)
      .map((d) => ({
        fileName: d.fileName.slice(0, 20),
        time: Math.round(d.totalTime || 0),
        status: d.status,
      }))
      .sort((a, b) => b.time - a.time)
      .slice(0, 20)
  }, [documents])

  // Processing over time
  const timelineData = React.useMemo(() => {
    const byDate: Record<string, { date: string; count: number; completed: number; failed: number }> = {}
    documents.forEach((doc) => {
      const dateStr = doc.timestamp.toISOString().split("T")[0]
      if (!byDate[dateStr]) {
        byDate[dateStr] = { date: dateStr, count: 0, completed: 0, failed: 0 }
      }
      byDate[dateStr].count++
      if (doc.status === "completed") byDate[dateStr].completed++
      if (doc.status === "failed") byDate[dateStr].failed++
    })
    return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  }, [documents])

  // Pages vs Processing Time scatter
  const scatterData = React.useMemo(() => {
    return documents
      .filter((d) => d.pages && d.totalTime)
      .map((d) => ({
        pages: d.pages,
        time: d.totalTime,
        fileName: d.fileName,
      }))
  }, [documents])

  // Stats summary
  const stats = React.useMemo(() => {
    const completedDocs = documents.filter((d) => d.status === "completed")
    const timesWithValues = completedDocs.filter((d) => d.totalTime).map((d) => d.totalTime!)
    const avgTime = timesWithValues.length > 0 
      ? timesWithValues.reduce((a, b) => a + b, 0) / timesWithValues.length 
      : 0
    const totalPages = documents.reduce((sum, d) => sum + (d.pages || 0), 0)
    const successRate = documents.length > 0 
      ? (completedDocs.length / documents.length) * 100 
      : 0

    return {
      totalDocs: documents.length,
      avgTime: avgTime.toFixed(1),
      totalPages,
      successRate: successRate.toFixed(1),
    }
  }, [documents])

  if (documents.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          No data available for analytics
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalDocs}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg Processing Time</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.avgTime}s</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Pages</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalPages}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.successRate}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="datasets">By Dataset</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Status Pie Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Processing Status</CardTitle>
                <CardDescription>Distribution of document statuses</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={statusData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        outerRadius={100}
                        fill="#8884d8"
                        dataKey="value"
                        label={({ name, value, percent }) =>
                          `${name}: ${value} (${(percent * 100).toFixed(0)}%)`
                        }
                      >
                        {statusData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Processing Time Histogram */}
            <Card>
              <CardHeader>
                <CardTitle>Processing Time</CardTitle>
                <CardDescription>Time taken per document (top 20)</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={processingTimeData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" unit="s" />
                      <YAxis dataKey="fileName" type="category" width={100} tick={{ fontSize: 10 }} />
                      <Tooltip
                        formatter={(value: number) => [`${value}s`, "Processing Time"]}
                      />
                      <Bar
                        dataKey="time"
                        fill="#3b82f6"
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="datasets">
          <Card>
            <CardHeader>
              <CardTitle>Documents by Dataset</CardTitle>
              <CardDescription>Status breakdown per dataset</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={datasetData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="completed" stackId="a" fill={COLORS.completed} name="Completed" />
                    <Bar dataKey="processing" stackId="a" fill={COLORS.processing} name="Processing" />
                    <Bar dataKey="failed" stackId="a" fill={COLORS.failed} name="Failed" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="performance">
          <Card>
            <CardHeader>
              <CardTitle>Pages vs Processing Time</CardTitle>
              <CardDescription>Correlation between document size and processing time</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                {scatterData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="pages" name="Pages" unit=" pages" />
                      <YAxis dataKey="time" name="Time" unit="s" />
                      <Tooltip
                        cursor={{ strokeDasharray: "3 3" }}
                        formatter={(value: number, name: string) => [
                          name === "pages" ? `${value} pages` : `${value}s`,
                          name === "pages" ? "Pages" : "Processing Time",
                        ]}
                      />
                      <Scatter name="Documents" data={scatterData} fill="#3b82f6" />
                    </ScatterChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-muted-foreground">
                    Not enough data for correlation analysis
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="timeline">
          <Card>
            <CardHeader>
              <CardTitle>Processing Timeline</CardTitle>
              <CardDescription>Documents processed over time</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={timelineData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      name="Total"
                    />
                    <Line
                      type="monotone"
                      dataKey="completed"
                      stroke={COLORS.completed}
                      strokeWidth={2}
                      name="Completed"
                    />
                    <Line
                      type="monotone"
                      dataKey="failed"
                      stroke={COLORS.failed}
                      strokeWidth={2}
                      name="Failed"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
