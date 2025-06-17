#!/bin/bash
# ARGUS Backend Local Development Script (Local Mode)
# This version runs without connecting to Azure Cosmos DB

set -e

echo "🚀 Starting ARGUS Backend locally (LOCAL MODE - No Azure dependencies)..."

# Navigate to backend directory
cd "$(dirname "$0")/src/containerapp"

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# Load environment variables from .env.local (skip Azure credentials for local mode)
echo "🔑 Loading local environment variables..."
if [ -f "../../.env.local" ]; then
    export $(grep -v '^#' ../../.env.local | grep -v '^$' | xargs)
fi

echo "🌐 Starting backend server on http://localhost:8000..."
echo "📋 API Documentation will be available at http://localhost:8000/docs"
echo "🔗 Backend API endpoints:"
echo "   - GET /api/documents - List all documents"
echo "   - GET /api/documents/{doc_id} - Get document details"
echo "   - GET /health - Health check"
echo "   - POST /api/upload - Upload file (mock)"
echo "   - POST /api/process/{doc_id} - Process document (mock)"
echo ""
echo "🧪 LOCAL DEVELOPMENT MODE:"
echo "   - Uses in-memory storage instead of Cosmos DB"
echo "   - Mock processing functions for testing"
echo "   - CORS enabled for frontend development"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server with hot reload using the local development version
uvicorn main_local:app --host 0.0.0.0 --port 8000 --reload --log-level info
