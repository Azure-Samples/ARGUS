#!/bin/bash

# Local Backend Development Script
echo "🚀 Starting ARGUS Backend locally..."

# Set the working directory to the backend source
cd "$(dirname "$0")/src/containerapp"

# Create virtual environment if it doesn't exist
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

# Load environment variables
echo "🔑 Loading environment variables..."
export $(cat ../../.env.local | xargs)

# Start the backend server
echo "🌐 Starting backend server on http://localhost:8000..."
echo "📋 API Documentation will be available at http://localhost:8000/docs"
echo "🔗 Backend API endpoints:"
echo "   - GET /api/documents - List all documents"
echo "   - GET /api/documents/{doc_id} - Get document details"
echo "   - GET /health - Health check"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
