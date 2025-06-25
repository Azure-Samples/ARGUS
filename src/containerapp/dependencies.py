"""
Azure client dependencies and global state management
"""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

# Import your existing processing functions
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'functionapp'))
from ai_ocr.process import connect_to_cosmos

logger = logging.getLogger(__name__)

# Azure credentials
credential = DefaultAzureCredential()

# Global variables for Azure clients
blob_service_client = None
data_container = None
conf_container = None
logic_app_manager = None

# Global thread pool executor for parallel processing
global_executor = None

# Global semaphore for concurrency control based on Logic App settings
global_processing_semaphore = None


async def initialize_azure_clients():
    """Initialize Azure clients on startup"""
    global blob_service_client, data_container, conf_container, global_executor, logic_app_manager, global_processing_semaphore
    
    try:
        # Initialize global thread pool executor
        global_executor = ThreadPoolExecutor(max_workers=10)
        logger.info("Initialized global ThreadPoolExecutor with 10 workers")
        
        # Initialize processing semaphore with default concurrency of 1
        # This will be updated when Logic App concurrency settings are retrieved
        global_processing_semaphore = asyncio.Semaphore(1)
        logger.info("Initialized global processing semaphore with 1 permit")
        
        # Initialize Logic App Manager
        from logic_app_manager import LogicAppManager
        logic_app_manager = LogicAppManager()
        
        # Try to get current Logic App concurrency to set proper semaphore value
        if logic_app_manager.enabled:
            try:
                settings = await logic_app_manager.get_concurrency_settings()
                if settings.get('enabled'):
                    max_runs = settings.get('current_max_runs', 1)
                    global_processing_semaphore = asyncio.Semaphore(max_runs)
                    logger.info(f"Updated processing semaphore to {max_runs} permits based on Logic App settings")
            except Exception as e:
                logger.warning(f"Could not retrieve Logic App concurrency settings on startup: {e}")
        
        # Initialize blob service client
        storage_account_url = os.getenv('BLOB_ACCOUNT_URL')
        if not storage_account_url:
            storage_account_name = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
            if storage_account_name:
                storage_account_url = f"https://{storage_account_name}.blob.core.windows.net"
            else:
                raise ValueError("Either BLOB_ACCOUNT_URL or AZURE_STORAGE_ACCOUNT_NAME must be set")
        
        blob_service_client = BlobServiceClient(
            account_url=storage_account_url,
            credential=credential
        )
        
        # Initialize Cosmos DB containers
        data_container, conf_container = connect_to_cosmos()
        
        logger.info("Successfully initialized Azure clients")
        
    except Exception as e:
        logger.error(f"Failed to initialize Azure clients: {e}")
        raise


async def cleanup_azure_clients():
    """Cleanup Azure clients on shutdown"""
    global global_executor
    
    if global_executor:
        logger.info("Shutting down global ThreadPoolExecutor")
        global_executor.shutdown(wait=True)
    logger.info("Shutting down application")


def get_blob_service_client():
    """Get the global blob service client"""
    return blob_service_client


def get_data_container():
    """Get the global data container"""
    return data_container


def get_conf_container():
    """Get the global configuration container"""
    return conf_container


def get_logic_app_manager():
    """Get the global logic app manager"""
    return logic_app_manager


def get_global_executor():
    """Get the global thread pool executor"""
    return global_executor


def get_global_processing_semaphore():
    """Get the global processing semaphore"""
    return global_processing_semaphore


def set_global_processing_semaphore(semaphore):
    """Set the global processing semaphore"""
    global global_processing_semaphore
    global_processing_semaphore = semaphore
