#!/bin/bash
# ARGUS Local Development Test Script

echo "🧪 Testing ARGUS Local Development Setup..."
echo ""

# Test Backend Health
echo "1️⃣ Testing Backend Health Check..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "✅ Backend health check passed"
    echo "   Response: $HEALTH_RESPONSE"
else
    echo "❌ Backend health check failed"
    echo "   Response: $HEALTH_RESPONSE"
    exit 1
fi
echo ""

# Test Backend API Documents
echo "2️⃣ Testing Backend Documents API..."
DOCS_RESPONSE=$(curl -s http://localhost:8000/api/documents)
DOC_COUNT=$(echo "$DOCS_RESPONSE" | jq -r '.count // 0')
if [ "$DOC_COUNT" -gt 0 ]; then
    echo "✅ Backend documents API working - Found $DOC_COUNT documents"
else
    echo "❌ Backend documents API failed or no documents found"
    echo "   Response: $DOCS_RESPONSE"
    exit 1
fi
echo ""

# Test Configuration API
echo "3️⃣ Testing Configuration API..."
CONFIG_RESPONSE=$(curl -s http://localhost:8000/api/configuration)
if echo "$CONFIG_RESPONSE" | grep -q "local-development"; then
    echo "✅ Configuration API working"
else
    echo "❌ Configuration API failed"
    echo "   Response: $CONFIG_RESPONSE"
    exit 1
fi
echo ""

# Test Datasets API
echo "4️⃣ Testing Datasets API..."
DATASETS_RESPONSE=$(curl -s http://localhost:8000/api/datasets)
DATASET_COUNT=$(echo "$DATASETS_RESPONSE" | jq '. | length')
if [ "$DATASET_COUNT" -gt 0 ]; then
    echo "✅ Datasets API working - Found $DATASET_COUNT datasets"
else
    echo "❌ Datasets API failed"
    echo "   Response: $DATASETS_RESPONSE"
    exit 1
fi
echo ""

# Test Frontend
echo "5️⃣ Testing Frontend Response..."
FRONTEND_RESPONSE=$(curl -s http://localhost:8501)
if echo "$FRONTEND_RESPONSE" | grep -q "Streamlit"; then
    echo "✅ Frontend is responding"
else
    echo "❌ Frontend is not responding properly"
    exit 1
fi
echo ""

# Test Backend API Documentation
echo "6️⃣ Testing Backend API Documentation..."
DOCS_PAGE=$(curl -s http://localhost:8000/docs)
if echo "$DOCS_PAGE" | grep -q "Swagger"; then
    echo "✅ Backend API documentation is available"
else
    echo "❌ Backend API documentation not accessible"
fi
echo ""

echo "🎉 All tests passed! ARGUS Local Development is working correctly!"
echo ""
echo "📋 Summary:"
echo "   • Backend API: http://localhost:8000"
echo "   • Frontend UI: http://localhost:8501"  
echo "   • API Docs: http://localhost:8000/docs"
echo "   • Health Check: http://localhost:8000/health"
echo ""
echo "🚀 You can now develop locally without Azure dependencies!"
