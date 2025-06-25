#!/usr/bin/env python3
"""
Startup simulation test for ARGUS modular backend
Tests the initialization process without actually starting the server
"""
import os
import sys
import asyncio
from unittest.mock import patch, MagicMock

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_startup_simulation():
    """Simulate the startup process"""
    print("🚀 Simulating ARGUS Backend Startup Process")
    print("=" * 60)
    
    try:
        # Mock environment variables that would be present in Azure
        with patch.dict(os.environ, {
            'BLOB_ACCOUNT_URL': 'https://mockaccount.blob.core.windows.net',
            'AZURE_SUBSCRIPTION_ID': 'mock-subscription-id',
            'AZURE_RESOURCE_GROUP_NAME': 'mock-resource-group',
            'LOGIC_APP_NAME': 'mock-logic-app',
            'AZURE_STORAGE_ACCOUNT_NAME': 'mockaccount'
        }):
            
            # Mock Azure clients to avoid actual Azure calls
            with patch('dependencies.DefaultAzureCredential'), \
                 patch('dependencies.BlobServiceClient'), \
                 patch('dependencies.connect_to_cosmos') as mock_cosmos:
                
                # Mock Cosmos DB connection
                mock_cosmos.return_value = (MagicMock(), MagicMock())
                
                # Import and test the dependencies module
                import dependencies
                print("✅ Dependencies module imported successfully")
                
                # Test initialization
                await dependencies.initialize_azure_clients()
                print("✅ Azure clients initialization completed")
                
                # Test getter functions
                assert dependencies.get_blob_service_client() is not None
                assert dependencies.get_data_container() is not None
                assert dependencies.get_conf_container() is not None
                assert dependencies.get_logic_app_manager() is not None
                print("✅ All client getter functions working")
                
                # Test cleanup
                await dependencies.cleanup_azure_clients()
                print("✅ Cleanup process completed")
        
        # Test the FastAPI app creation
        import main
        app = main.app
        
        # Verify app properties
        assert app.title == "ARGUS Backend"
        assert app.description == "Document processing backend using Azure AI services"
        assert app.version == "1.0.0"
        print("✅ FastAPI app created with correct configuration")
        
        # Count routes
        routes = [r for r in app.routes if hasattr(r, 'path') and not r.path.startswith('/docs') and not r.path.startswith('/openapi')]
        print(f"✅ FastAPI app has {len(routes)} routes configured")
        
        # Test API routes module
        import api_routes
        print("✅ API routes module imported successfully")
        
        # Test other modules
        import models
        import logic_app_manager
        import blob_processing
        print("✅ All supporting modules imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Startup simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run the startup simulation test"""
    success = await test_startup_simulation()
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 STARTUP SIMULATION SUCCESSFUL!")
        print("✅ All modules can be imported and initialized")
        print("✅ FastAPI app can be created successfully")
        print("✅ The modular backend is ready for deployment")
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ STARTUP SIMULATION FAILED!")
        print("🔧 Please review the errors above")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
