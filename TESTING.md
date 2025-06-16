# ARGUS End-to-End Testing Guide

## 🎯 Overview
This guide helps you test the complete ARGUS document processing workflow on Azure Container Apps.

## 📡 Current Deployment
- **Base URL**: `https://ca-argus-test.happymushroom-0bb928ac.eastus2.azurecontainerapps.io`
- **Health Check**: `GET /health`
- **Manual Processing**: `POST /api/process-blob`
- **Event Grid Webhook**: `POST /api/blob-created`

## 🧪 Testing Methods

### Method 1: Quick Automated Testing (Recommended)
Run the simplified test script that validates the entire workflow:
```bash
./test-e2e-simple.sh
```

### Method 2: Comprehensive Testing
For detailed testing with extensive logging:
```bash
./test-e2e-comprehensive.sh
```

### Method 3: Debug & Diagnostics
For troubleshooting deployment issues:
```bash
./test-debug.sh
```

### Method 4: Manual Step-by-Step Testing

#### Step 1: Verify Application Health
```bash
# Basic availability check
curl https://ca-argus-test.happymushroom-0bb928ac.eastus2.azurecontainerapps.io/

# Detailed health check (includes service connectivity)
curl https://ca-argus-test.happymushroom-0bb928ac.eastus2.azurecontainerapps.io/health
```

Expected health response:
```json
{
  "status": "healthy",
  "timestamp": "2025-06-16T14:18:01.915283",
  "services": {
    "storage": "connected",
    "cosmos_db": "connected"
  }
}
```

#### Step 2: Upload Test Document
```bash
# Upload invoice sample to storage
az storage blob upload \
  --account-name sa5xm7rawmgdbia \
  --container-name datasets \
  --name "datasets/default-dataset/test-invoice.pdf" \
  --file "demo/default-dataset/Invoice Sample.pdf" \
  --auth-mode login
```

#### Step 3: Trigger Manual Processing
```bash
curl -X POST https://ca-argus-test.happymushroom-0bb928ac.eastus2.azurecontainerapps.io/api/process-blob \
  -H "Content-Type: application/json" \
  -d '{"blob_url": "https://sa5xm7rawmgdbia.blob.core.windows.net/datasets/datasets/default-dataset/test-invoice.pdf"}'
```

#### Step 4: Monitor Processing
```bash
# Watch application logs
azd logs --follow

# Or check specific logs
azd logs --service backend
```

#### Step 5: Verify Results
```bash
# Check processed files in storage
az storage blob list \
  --account-name sa5xm7rawmgdbia \
  --container-name datasets \
  --prefix "datasets/default-dataset/test-invoice" \
  --auth-mode login

# Query Cosmos DB for processing results (via Azure portal or CLI)
```

## 🔄 Event Grid Testing (Production Workflow)

### Simulate Event Grid Webhook
```bash
curl -X POST https://ca-argus-test.happymushroom-0bb928ac.eastus2.azurecontainerapps.io/api/blob-created \
  -H "Content-Type: application/json" \
  -d '[{
    "id": "test-event-123",
    "eventType": "Microsoft.Storage.BlobCreated",
    "subject": "/blobServices/default/containers/datasets/blobs/datasets/default-dataset/test-invoice.pdf",
    "eventTime": "2025-06-16T13:00:00.000Z",
    "data": {
      "api": "PutBlob",
      "url": "https://sa5xm7rawmgdbia.blob.core.windows.net/datasets/datasets/default-dataset/test-invoice.pdf",
      "contentType": "application/pdf",
      "blobType": "BlockBlob"
    },
    "dataVersion": "1.0",
    "metadataVersion": "1"
  }]'
```

## 📊 Expected Workflow

1. **Document Upload** → Storage Account (`sa5xm7rawmgdbia`)
2. **Event Trigger** → Container App receives webhook or manual trigger
3. **OCR Processing** → Document Intelligence extracts text and layout
4. **AI Extraction** → GPT processes content based on schema
5. **Data Storage** → Results saved to Cosmos DB
6. **Output Files** → Processed data saved back to Storage Account

## 🔍 Monitoring & Debugging

### Check Application Logs
```bash
# Follow logs in real-time
azd logs --follow

# Get recent logs
azd logs --tail 100
```

### Check Azure Resources
- **Container App**: Azure Portal → Container Apps → `ca-argus-test`
- **Storage Account**: Azure Portal → Storage Accounts → `sa5xm7rawmgdbia`
- **Cosmos DB**: Azure Portal → Azure Cosmos DB → `cb5xm7rawmgdbia`
- **Document Intelligence**: Azure Portal → Document Intelligence → `di5xm7rawmgdbia`

### Troubleshooting Common Issues

1. **Health Check Fails**
   - Check managed identity permissions
   - Verify storage account connectivity

2. **Processing Timeouts**
   - Check document size (large PDFs may timeout)
   - Monitor container app resource usage

3. **Authentication Errors**
   - Verify RBAC role assignments
   - Check managed identity configuration

## 🎯 Test Documents Available

- **Invoice Sample**: `demo/default-dataset/Invoice Sample.pdf`
- **Medical Documents**: `demo/medical-dataset/` (if configured)

## 📈 Success Criteria

✅ Health endpoints return healthy status
✅ Documents upload successfully to storage
✅ Processing requests are accepted (202 status)
✅ Application logs show processing progress
✅ Results appear in Cosmos DB
✅ Output files are generated in storage account

## 🚀 Production Deployment

For production use:
1. Set up Event Grid subscription to storage account
2. Configure auto-scaling rules for container app
3. Set up monitoring and alerting
4. Configure backup and disaster recovery
5. Implement proper logging and observability
