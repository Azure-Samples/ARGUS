# ARGUS: Automated Retrieval and GPT Understanding System

> Argus Panoptes, in ancient Greek mythology, was a giant with a hundred eyes and a servant of the goddess Hera. His many eyes made him an excellent watchman, as some of his eyes would always remain open while the others slept, allowing him to be ever-vigilant.

## Overview

This solution demonstrates **Azure Document Intelligence + GPT-4 Vision** for intelligent document processing. Classic OCR models lack reasoning ability based on context when extracting information from documents. ARGUS uses a hybrid approach with OCR and multimodal Large Language Models to achieve better results without pre-training.

### Key Features
- 🔍 **Hybrid OCR + LLM Processing**: Combines Azure Document Intelligence with GPT-4 Vision
- 🚀 **Container App Deployment**: Modern, scalable container-based architecture
- 📊 **Multi-format Support**: Handles various document types with configurable datasets
- 🔄 **Event-driven Processing**: Supports both manual and automated document processing
- 📈 **Comprehensive Monitoring**: Built-in health checks and application insights

## Architecture

**Current Deployment**: Azure Container App with modern cloud-native architecture

- **Backend**: Azure Container App running FastAPI with document processing logic
- **Storage**: Azure Blob Storage for document storage, Cosmos DB for metadata and results
- **AI Services**: Azure Document Intelligence for OCR, Azure OpenAI for intelligent extraction
- **Security**: User-assigned managed identity with least-privilege RBAC
- **Monitoring**: Application Insights for comprehensive observability

![architecture](docs/ArchitectureOverview.png)

## Quick Start

### Deployment with Azure Developer CLI

The fastest way to deploy ARGUS is using `azd` (Azure Developer CLI):

![architecture](docs/ArchitectureOverview.png)

## Prerequisites
### Azure OpenAI Resource

Before deploying the solution, you need to create an OpenAI resource and deploy a model that is vision capable.

### Prerequisites

1. **Install Azure Developer CLI**:
   ```bash
   # Install azd (Azure Developer CLI)
   curl -fsSL https://aka.ms/install-azd.sh | bash
   ```

2. **Install Azure CLI** (if not already installed):
   ```bash
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   ```

3. **Create Azure OpenAI Resource** (Optional for full functionality):
   - Follow [this guide](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource) to create an OpenAI resource
   - Deploy a vision-capable model (GPT-4 Turbo with Vision, GPT-4 Omni, etc.)

### Deploy ARGUS

1. **Clone and authenticate**:
   ```bash
   git clone <your-repo-url>
   cd ARGUS
   az login
   ```

2. **Deploy with one command**:
   ```bash
   azd up
   ```

3. **Verify deployment**:
   ```bash
   # Run end-to-end test
   ./test-e2e-simple.sh
   
   # Check application logs
   azd logs
   ```

### Configuration

After deployment, configure your Azure OpenAI credentials:

1. **Update parameters** in `infra/main.parameters.json`:
   ```json
   {
     "openAiApiKey": {"value": "your-real-openai-key"},
     "openAiEndpoint": {"value": "https://your-openai-resource.openai.azure.com/"},
     "openAiModelDeploymentName": {"value": "your-model-deployment-name"}
   }
   ```

2. **Redeploy**:
   ```bash
   azd up
   ```

## Usage

### API Endpoints

Once deployed, ARGUS provides several endpoints:

- **Health Check**: `GET /health` - Check application and service status
- **Process Document**: `POST /api/process-blob` - Manually trigger document processing
- **Event Grid Webhook**: `POST /api/blob-created` - Automated processing via Event Grid

### Document Processing

1. **Upload documents** to the storage container:
   ```bash
   az storage blob upload \
     --account-name <storage-account> \
     --container-name datasets \
     --name "default-dataset/my-document.pdf" \
     --file "./my-document.pdf"
   ```

2. **Trigger processing** via API:
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"blob_url":"https://<storage>.blob.core.windows.net/datasets/default-dataset/my-document.pdf"}' \
     <container-app-url>/api/process-blob
   ```

3. **Check results** in Cosmos DB or application logs

### Dataset Configuration

ARGUS supports multiple document types through dataset configurations:

- **Default Dataset**: `/example-datasets/default-dataset/` - General invoices and documents
- **Medical Dataset**: `/example-datasets/medical-dataset/` - Medical forms and reports
- **Custom Datasets**: Add your own in `/example-datasets/your-dataset/`

Each dataset contains:
- `system_prompt.txt` - Instructions for GPT processing
- `output_schema.json` - Expected output structure

## Testing

### Automated Testing

Run the comprehensive test suite:

```bash
# Quick end-to-end test
./test-e2e-simple.sh

# Comprehensive test with debugging
./test-e2e-comprehensive.sh

# Debug deployment issues
./test-debug.sh
```

### Manual Testing

1. **Test health endpoint**:
   ```bash
   curl <container-app-url>/health
   ```

2. **Upload and process a document**:
   ```bash
   # Upload
   az storage blob upload --file "demo/default-dataset/Invoice Sample.pdf" ...
   
   # Process
   curl -X POST -d '{"blob_url":"..."}' <container-app-url>/api/process-blob
   ```

## Monitoring

- **Application Insights**: Monitor performance and errors
- **Container App Logs**: `azd logs` or Azure Portal
- **Health Endpoint**: Real-time service status at `/health`

## Optional: Frontend (Not Auto-Deployed)

To run the Streamlit frontend locally:

```bash
# Install dependencies
pip install -r frontend/requirements.txt

# Set environment variables (if using azd)
azd env get-values > frontend/.env

# OR manually copy the template
mv frontend/.env.temp frontend/.env
# Then edit frontend/.env with your values

# Run Streamlit app
cd frontend
streamlit run app.py
```

The frontend provides a user-friendly interface for:
- Document upload and processing
- Dataset configuration
- Result visualization
- Processing history

## Architecture Details

### Container App Architecture

ARGUS uses a modern container-based architecture:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Blob Storage  │───▶│  Container App   │───▶│   Cosmos DB     │
│   (Documents)   │    │   (FastAPI)      │    │  (Results)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │ Document Intel.  │
                    │ + Azure OpenAI   │
                    └──────────────────┘
```

### Security Features

- **Managed Identity**: No hardcoded credentials
- **RBAC**: Least-privilege access to all resources  
- **Network Security**: Container app with restricted ingress
- **Secrets Management**: Secure configuration via environment variables

## Dataset Configuration

ARGUS supports multiple document types through configurable datasets:

### Structure
```
example-datasets/
├── default-dataset/
│   ├── system_prompt.txt      # Instructions for GPT
│   └── output_schema.json     # Expected output structure
└── medical-dataset/
    ├── system_prompt.txt
    └── output_schema.json
```

### Creating Custom Datasets

1. **Create dataset folder**: `example-datasets/my-dataset/`
2. **Add prompt**: Write processing instructions in `system_prompt.txt`
3. **Define schema**: Create `output_schema.json` with expected fields
4. **Upload documents**: Use folder name in blob path: `my-dataset/document.pdf`

### Example Schema
```json
{
  "invoice_number": "",
  "total_amount": "",
  "vendor_name": "",
  "invoice_date": "",
  "line_items": []
}
```

## Performance Evaluation (Optional)

Use the Jupyter notebook for performance evaluation:

```bash
# Install notebook dependencies
pip install -r notebooks/requirements.txt

# Run evaluation notebook
cd notebooks
jupyter notebook evaluator.ipynb
```

The notebook provides:
- **Overall Accuracy**: System performance metrics
- **Field-Level Analysis**: Individual field accuracy  
- **Custom Distance Metrics**: Fuzzy matching with Jaro-Winkler
- **Visualization**: Performance charts and comparisons

## Troubleshooting

### Common Issues

1. **OpenAI Authentication Errors** (401):
   ```bash
   # Update with real credentials in infra/main.parameters.json
   azd up  # Redeploy
   ```

2. **Blob Processing Failures**:
   ```bash
   # Check storage permissions and blob paths
   ./test-debug.sh
   ```

3. **Health Check Failures**:
   ```bash
   # Run diagnostics
   azd logs
   curl <container-app-url>/health
   ```

### Debug Tools

- **Debug Script**: `./test-debug.sh` - Comprehensive diagnostics
- **Test Scripts**: `./test-e2e-simple.sh` - Quick validation
- **Logs**: `azd logs` - Application logs

## Team

- [Alberto Gallo](https://github.com/albertaga27)
- [Petteri Johansson](https://github.com/piizei)  
- [Christin Pohl](https://github.com/pohlchri)
- [Konstantinos Mavrodis](https://github.com/kmavrodis_microsoft)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test your changes with provided test scripts
4. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

For detailed testing procedures, see [TESTING.md](TESTING.md).
