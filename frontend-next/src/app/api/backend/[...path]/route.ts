import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
const API_KEY = process.env.BACKEND_API_KEY || ''

/**
 * Catch-all proxy route that forwards requests to the backend with the API key.
 * Browser calls /api/backend/... → this route adds X-API-Key → forwards to backend.
 */
async function proxyRequest(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  const backendPath = '/' + path.join('/')
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${BACKEND_URL}${backendPath}${searchParams ? `?${searchParams}` : ''}`

  const headers = new Headers()
  // Forward relevant headers from the original request
  const contentType = request.headers.get('content-type')
  if (contentType) {
    headers.set('Content-Type', contentType)
  }
  const accept = request.headers.get('accept')
  if (accept) {
    headers.set('Accept', accept)
  }

  // Add API key (server-side only — never exposed to browser)
  if (API_KEY) {
    headers.set('X-API-Key', API_KEY)
  }

  const fetchOptions: RequestInit = {
    method: request.method,
    headers,
  }

  // Forward body for methods that have one
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    // Check if it's a form/multipart upload
    if (contentType?.includes('multipart/form-data')) {
      fetchOptions.body = await request.arrayBuffer()
      // Let fetch set the correct content-type with boundary
      headers.delete('Content-Type')
      headers.set('Content-Type', contentType)
    } else {
      fetchOptions.body = await request.arrayBuffer()
    }
  }

  try {
    const response = await fetch(url, fetchOptions)

    // Stream the response back
    const responseHeaders = new Headers()
    response.headers.forEach((value, key) => {
      // Skip headers that Next.js manages
      if (!['transfer-encoding', 'connection'].includes(key.toLowerCase())) {
        responseHeaders.set(key, value)
      }
    })

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    })
  } catch (error) {
    console.error('Backend proxy error:', error)
    return NextResponse.json(
      { detail: 'Failed to reach backend service' },
      { status: 502 }
    )
  }
}

export const GET = proxyRequest
export const POST = proxyRequest
export const PUT = proxyRequest
export const PATCH = proxyRequest
export const DELETE = proxyRequest
