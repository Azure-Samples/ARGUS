"""
Logic App Manager for Azure Logic App concurrency management
"""
import logging
import os
from datetime import datetime
from typing import Dict, Any
from azure.identity import DefaultAzureCredential
from azure.mgmt.logic import LogicManagementClient

logger = logging.getLogger(__name__)


class LogicAppManager:
    """Manages Logic App concurrency settings via Azure Management API"""
    
    def __init__(self):
        self.credential = DefaultAzureCredential()
        self.subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        self.resource_group_name = os.getenv('AZURE_RESOURCE_GROUP_NAME')
        self.logic_app_name = os.getenv('LOGIC_APP_NAME')
        
        if not all([self.subscription_id, self.resource_group_name, self.logic_app_name]):
            logger.warning("Logic App management requires AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP_NAME, and LOGIC_APP_NAME environment variables")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Logic App Manager initialized for {self.logic_app_name} in {self.resource_group_name}")
    
    def get_logic_management_client(self):
        """Create a Logic Management client"""
        if not self.enabled:
            raise ValueError("Logic App Manager is not properly configured")
        return LogicManagementClient(self.credential, self.subscription_id)
    
    async def get_concurrency_settings(self) -> Dict[str, Any]:
        """Get current Logic App concurrency settings"""
        try:
            if not self.enabled:
                return {"error": "Logic App Manager not configured", "enabled": False}
            
            logic_client = self.get_logic_management_client()
            
            # Get the Logic App workflow
            workflow = logic_client.workflows.get(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name
            )
            
            # Extract concurrency settings from workflow definition
            definition = workflow.definition or {}
            triggers = definition.get('triggers', {})
            
            # Get concurrency from the first trigger (most common case)
            runs_on = 5  # Default value
            trigger_name = None
            for name, trigger_config in triggers.items():
                trigger_name = name
                runtime_config = trigger_config.get('runtimeConfiguration', {})
                concurrency = runtime_config.get('concurrency', {})
                runs_on = concurrency.get('runs', 5)
                break  # Use the first trigger found
            
            return {
                "enabled": True,
                "logic_app_name": self.logic_app_name,
                "resource_group": self.resource_group_name,
                "current_max_runs": runs_on,
                "trigger_name": trigger_name,
                "workflow_state": workflow.state,
                "last_modified": workflow.changed_time.isoformat() if workflow.changed_time else None
            }
            
        except Exception as e:
            logger.error(f"Error getting Logic App concurrency settings: {e}")
            return {"error": str(e), "enabled": False}
    
    async def update_concurrency_settings(self, max_runs: int) -> Dict[str, Any]:
        """Update Logic App concurrency settings"""
        try:
            if not self.enabled:
                return {"error": "Logic App Manager not configured", "success": False}
            
            if max_runs < 1 or max_runs > 100:
                return {"error": "Max runs must be between 1 and 100", "success": False}
            
            logic_client = self.get_logic_management_client()
            
            # Get the current workflow
            current_workflow = logic_client.workflows.get(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name
            )
            
            # Update the workflow definition with new concurrency settings
            updated_definition = current_workflow.definition.copy() if current_workflow.definition else {}
            
            # Find the trigger and update its concurrency settings using runtimeConfiguration
            triggers = updated_definition.get('triggers', {})
            for trigger_name, trigger_config in triggers.items():
                # Set runtime configuration for concurrency control
                if 'runtimeConfiguration' not in trigger_config:
                    trigger_config['runtimeConfiguration'] = {}
                if 'concurrency' not in trigger_config['runtimeConfiguration']:
                    trigger_config['runtimeConfiguration']['concurrency'] = {}
                trigger_config['runtimeConfiguration']['concurrency']['runs'] = max_runs
                logger.info(f"Updated concurrency for trigger {trigger_name} to {max_runs}")
            
            # Create the workflow update request using the proper Workflow object
            from azure.mgmt.logic.models import Workflow
            
            workflow_update = Workflow(
                location=current_workflow.location,
                definition=updated_definition,
                state=current_workflow.state,
                parameters=current_workflow.parameters,
                tags=current_workflow.tags  # Include tags to maintain existing metadata
            )
            
            # Update the workflow
            updated_workflow = logic_client.workflows.create_or_update(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name,
                workflow=workflow_update
            )
            
            logger.info(f"Successfully updated Logic App {self.logic_app_name} max concurrent runs to {max_runs}")
            
            return {
                "success": True,
                "logic_app_name": self.logic_app_name,
                "new_max_runs": max_runs,
                "updated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating Logic App concurrency settings: {e}")
            return {"error": str(e), "success": False}

    async def get_workflow_definition(self) -> Dict[str, Any]:
        """Get the complete Logic App workflow definition for inspection"""
        try:
            if not self.enabled:
                return {"error": "Logic App Manager not configured", "enabled": False}
            
            logic_client = self.get_logic_management_client()
            
            # Get the Logic App workflow
            workflow = logic_client.workflows.get(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name
            )
            
            return {
                "enabled": True,
                "logic_app_name": self.logic_app_name,
                "resource_group": self.resource_group_name,
                "workflow_state": workflow.state,
                "definition": workflow.definition,
                "last_modified": workflow.changed_time.isoformat() if workflow.changed_time else None
            }
            
        except Exception as e:
            logger.error(f"Error getting Logic App workflow definition: {e}")
            return {"error": str(e), "enabled": False}

    async def update_action_concurrency_settings(self, max_runs: int) -> Dict[str, Any]:
        """Update Logic App action-level concurrency settings for HTTP actions"""
        try:
            if not self.enabled:
                return {"error": "Logic App Manager not configured", "success": False}
            
            if max_runs < 1 or max_runs > 100:
                return {"error": "Max runs must be between 1 and 100", "success": False}
            
            logic_client = self.get_logic_management_client()
            
            # Get the current workflow
            current_workflow = logic_client.workflows.get(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name
            )
            
            # Update the workflow definition with new concurrency settings
            updated_definition = current_workflow.definition.copy() if current_workflow.definition else {}
            
            # Update trigger-level concurrency
            triggers = updated_definition.get('triggers', {})
            for trigger_name, trigger_config in triggers.items():
                if 'runtimeConfiguration' not in trigger_config:
                    trigger_config['runtimeConfiguration'] = {}
                if 'concurrency' not in trigger_config['runtimeConfiguration']:
                    trigger_config['runtimeConfiguration']['concurrency'] = {}
                trigger_config['runtimeConfiguration']['concurrency']['runs'] = max_runs
                logger.info(f"Updated trigger concurrency for {trigger_name} to {max_runs}")
            
            # Update action-level concurrency for HTTP actions and loops
            actions = updated_definition.get('actions', {})
            updated_actions = 0
            
            def update_action_concurrency(actions_dict):
                nonlocal updated_actions
                for action_name, action_config in actions_dict.items():
                    # Set concurrency for HTTP actions
                    if action_config.get('type') in ['Http', 'ApiConnection']:
                        if 'runtimeConfiguration' not in action_config:
                            action_config['runtimeConfiguration'] = {}
                        if 'concurrency' not in action_config['runtimeConfiguration']:
                            action_config['runtimeConfiguration']['concurrency'] = {}
                        action_config['runtimeConfiguration']['concurrency']['runs'] = max_runs
                        logger.info(f"Updated action concurrency for {action_name} to {max_runs}")
                        updated_actions += 1
                    
                    # Handle nested actions in conditionals and loops
                    if 'actions' in action_config:
                        update_action_concurrency(action_config['actions'])
                    if 'else' in action_config and 'actions' in action_config['else']:
                        update_action_concurrency(action_config['else']['actions'])
                    
                    # Handle foreach loops specifically
                    if action_config.get('type') == 'Foreach':
                        if 'runtimeConfiguration' not in action_config:
                            action_config['runtimeConfiguration'] = {}
                        if 'concurrency' not in action_config['runtimeConfiguration']:
                            action_config['runtimeConfiguration']['concurrency'] = {}
                        action_config['runtimeConfiguration']['concurrency']['repetitions'] = max_runs
                        logger.info(f"Updated foreach concurrency for {action_name} to {max_runs}")
                        updated_actions += 1
                        
                        # Also update nested actions
                        if 'actions' in action_config:
                            update_action_concurrency(action_config['actions'])
            
            update_action_concurrency(actions)
            
            # Create the workflow update request
            from azure.mgmt.logic.models import Workflow
            
            workflow_update = Workflow(
                location=current_workflow.location,
                definition=updated_definition,
                state=current_workflow.state,
                parameters=current_workflow.parameters,
                tags=current_workflow.tags
            )
            
            # Update the workflow
            updated_workflow = logic_client.workflows.create_or_update(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name,
                workflow=workflow_update
            )
            
            logger.info(f"Successfully updated Logic App {self.logic_app_name} concurrency: trigger and {updated_actions} actions to {max_runs}")
            
            return {
                "success": True,
                "logic_app_name": self.logic_app_name,
                "new_max_runs": max_runs,
                "updated_triggers": len(triggers),
                "updated_actions": updated_actions,
                "updated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating Logic App action concurrency settings: {e}")
            return {"error": str(e), "success": False}
