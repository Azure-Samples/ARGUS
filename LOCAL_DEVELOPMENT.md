# 🚀 ARGUS Local Development Guide

This guide helps you run ARGUS locally for faster development and testing.

## 📋 Prerequisites

- Python 3.11 or higher
- Virtual environment support (`venv`)
- Azure credentials configured (for full Azure features) - **Optional for local development**

## 🏃‍♂️ Quick Start

### Option 1: Local Development Mode (Recommended for Local Testing)

**Use this when you can't connect to Azure services or want to work entirely offline:**

```bash
./run-backend-local-dev.sh
```

This mode:
- ✅ Works without Azure Cosmos DB (uses in-memory storage)
- ✅ Includes mock data and processing functions
- ✅ Has CORS enabled for frontend development
- ✅ Perfect for UI development and testing

### Option 2: Full Azure Integration Mode

**Use this when you have proper Azure access and firewall configured:**

```bash
./run-backend-local.sh
```

This mode:
- 🔗 Connects to real Azure services (Cosmos DB, Storage, etc.)
- ⚠️ Requires Azure firewall configuration
- 📊 Uses real data from your Azure deployment

### Option 3: Start Both Services Together

```bash
./start-local-dev.sh
```

This will automatically start both backend and frontend services.

## 🌐 Access Points

Once running locally:

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🔧 Development Workflow

### Making Changes

1. **Frontend Changes**: 
   - Edit files in `frontend/`
   - Streamlit automatically reloads on file changes
   - Refresh your browser to see updates

2. **Backend Changes**:
   - Edit files in `src/containerapp/`
   - Uvicorn automatically reloads on file changes
   - API changes are immediately available

### Testing the API

You can test the backend API directly:

```bash
# Check health
curl http://localhost:8000/health

# List documents
curl http://localhost:8000/api/documents

# View API documentation
open http://localhost:8000/docs
```

### Local Development Features

The local development backend (`main_local.py`) includes:

- 📝 **In-memory storage** - No need for Cosmos DB
- 🎭 **Mock processing** - Simulates OCR, GPT extraction, etc.
- 📊 **Sample data** - Pre-loaded test documents
- 🔄 **File upload simulation** - Test upload workflows
- 📈 **Statistics endpoint** - Monitor processing stats

## 🐛 Troubleshooting

### Backend Won't Start (Cosmos DB Errors)

**Problem**: `Cosmos DB account firewall settings` error

**Solution**: Use the local development mode:
```bash
./run-backend-local-dev.sh
```

### Frontend Can't Connect to Backend

**Problem**: Frontend shows connection errors

**Solutions**:
1. Ensure backend is running on `http://localhost:8000`
2. Check that `BACKEND_URL=http://localhost:8000` in `.env.local`
3. Verify CORS is enabled in the backend

### Port Already in Use

**Problem**: `Address already in use` error

**Solutions**:
```bash
# Kill processes on port 8000 (backend)
lsof -ti:8000 | xargs kill -9

# Kill processes on port 8501 (frontend)  
lsof -ti:8501 | xargs kill -9
```

### Environment Variables Not Loading

**Problem**: Missing environment variables

**Solutions**:
1. Ensure `.env.local` exists in the project root
2. Check file permissions: `chmod 644 .env.local`
3. Verify variable names match exactly (case-sensitive)

## 🧪 Testing Different Scenarios

### Test File Upload
1. Go to http://localhost:8501
2. Use the file upload feature
3. Check http://localhost:8000/api/documents to see the uploaded file

### Test Document Processing
1. Upload a document
2. Use the process endpoint: `POST /api/process/{doc_id}`
3. Watch the document state change through the API

### Test API Endpoints
Visit http://localhost:8000/docs to interact with:
- Document management endpoints
- File upload endpoints  
- Processing status endpoints
- Configuration endpoints

## 🔄 Switching Between Modes

You can easily switch between local development and Azure integration:

1. **For local development**: Use `run-backend-local-dev.sh`
2. **For Azure testing**: Use `run-backend-local.sh` (requires Azure access)
3. **Stop any mode**: Press `Ctrl+C` in the terminal

## � Dependencies

Both backend and frontend use separate virtual environments:

- **Backend**: `src/containerapp/venv/`
- **Frontend**: `frontend/venv/`

Dependencies are automatically installed when you run the development scripts.

## 🚀 Next Steps

1. **Make your changes** in the code
2. **Test locally** using the development environment
3. **Deploy to Azure** when ready using `azd up`

The local environment mimics the production environment, so you can be confident your changes will work when deployed! 
   - Edit files in `/frontend/`
   - Streamlit will auto-reload on file changes
   - Refresh your browser to see changes

2. **Backend Changes**:
   - Edit files in `/src/containerapp/`
   - FastAPI will auto-reload on file changes
   - API changes are immediately available

### Environment Configuration

- **Local config**: `.env.local` (for local development)
- **Azure config**: `.azure/argus-test/.env` (for deployments)

The local setup uses the same Azure services (Cosmos DB, Blob Storage, etc.) but runs the application locally for faster iteration.

## 🛠️ Troubleshooting

### Common Issues

1. **Port Already in Use**:
   ```bash
   # Kill processes on ports 8000 and 8501
   lsof -ti:8000 | xargs kill -9
   lsof -ti:8501 | xargs kill -9
   ```

2. **Missing Dependencies**:
   - Delete `venv` folders and run the scripts again
   - They will recreate the virtual environments

3. **Azure Authentication**:
   - Ensure you're logged into Azure CLI: `az login`
   - Or set up service principal credentials

### Logs and Debugging

- **Backend logs**: Visible in the terminal running the backend
- **Frontend logs**: Visible in the terminal running Streamlit
- **API debugging**: Use http://localhost:8000/docs for interactive testing

## 🔄 Deployment

When ready to deploy your changes:

```bash
# Deploy to Azure
azd up
```

## 📁 Project Structure

```
ARGUS/
├── .env.local                 # Local environment variables
├── start-local-dev.sh        # Start both services
├── run-backend-local.sh      # Start backend only
├── run-frontend-local.sh     # Start frontend only
├── src/containerapp/         # Backend source code
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Backend dependencies
│   └── venv/               # Backend virtual environment
├── frontend/                # Frontend source code
│   ├── app.py              # Main Streamlit app
│   ├── explore_data.py     # Enhanced Explore Data tab
│   ├── requirements.txt    # Frontend dependencies
│   └── venv/              # Frontend virtual environment
```

## 🎯 Development Tips

1. **Use the Enhanced Explore Data Tab**: The restored version has all the advanced features
2. **Test API endpoints**: Use http://localhost:8000/docs for interactive testing
3. **Monitor logs**: Keep both terminal windows visible to monitor logs
4. **Hot reload**: Both services support hot reloading for faster development

Happy coding! 🎉
