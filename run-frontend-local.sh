#!/bin/bash

# Local Frontend Development Script
echo "🎨 Starting ARGUS Frontend locally..."

# Set the working directory to the frontend
cd "$(dirname "$0")/frontend"

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
if [ -f "../.env.local" ]; then
    export $(grep -v '^#' ../.env.local | grep -v '^$' | xargs)
    echo "✅ Loaded local environment variables"
    echo "🔗 Backend URL: $BACKEND_URL"
else
    echo "⚠️  Warning: .env.local file not found, using defaults"
    export BACKEND_URL="http://localhost:8000"
fi

# Start the frontend server
echo "🌐 Starting frontend server on http://localhost:8501..."
echo "🖥️  Frontend will be available at http://localhost:8501"
echo "📊 Explore Data tab with all advanced features will be ready!"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the Streamlit app
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
