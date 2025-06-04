import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from app.core.config import settings

def verify_azure_config():
    try:
        credential = DefaultAzureCredential()
        resource_client = ResourceManagementClient(
            credential=credential,
            subscription_id=settings.azure_subscription_id
        )
        
        # Verify resource group
        resource_group = resource_client.resource_groups.get(
            settings.azure_resource_group
        )
        print(f"✅ Resource group verified: {resource_group.name}")
        
        return True
    except Exception as e:
        print(f"❌ Azure configuration error: {e}")
        return False

if __name__ == "__main__":
    verify_azure_config()