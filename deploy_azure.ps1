# Azure Deployment Script for Chatbot - Fixed Version
# This script automates the deployment of the chatbot to Azure App Service

# Exit on error
$ErrorActionPreference = "Stop"

# Configuration
$subscriptionId = "148212ee-39f9-4c68-a01c-893b20634d54"
$resourceGroup = "beta-bot"
$location = "eastus"
$appServicePlan = "chatbot-plan"
$appName = "grupo-beta"
$pythonVersion = "3.11"

# Login to Azure if not already logged in
try {
    $account = az account show 2>$null | ConvertFrom-Json
    if (-not $account) {
        Write-Host "🔑 Logging in to Azure..."
        az login --use-device-code
    }
    
    # Set the active subscription
    Write-Host "📌 Setting active subscription..."
    az account set --subscription $subscriptionId
} catch {
    Write-Error "❌ Failed to authenticate with Azure: $_"
    exit 1
}

# Create resource group if it doesn't exist
Write-Host "🔄 Checking/Creating resource group..."
if (!(az group exists --name $resourceGroup)) {
    Write-Host "📦 Creating resource group '$resourceGroup'..."
    az group create --name $resourceGroup --location $location
} else {
    Write-Host "✅ Resource group '$resourceGroup' already exists."
}

# Create App Service Plan if it doesn't exist
Write-Host "🔄 Checking/Creating App Service Plan..."
$planExists = az appservice plan list --resource-group $resourceGroup --query "[?name=='$appServicePlan']" | ConvertFrom-Json
if ($null -eq $planExists) {
    Write-Host "📊 Creating App Service Plan '$appServicePlan'..."
    az appservice plan create --name $appServicePlan --resource-group $resourceGroup --sku B1 --is-linux --location $location
} else {
    Write-Host "✅ App Service Plan '$appServicePlan' already exists."
}

# Create Web App if it doesn't exist
Write-Host "🔄 Checking/Creating Web App..."
$appExists = az webapp list --resource-group $resourceGroup --query "[?name=='$appName']" | ConvertFrom-Json
if ($null -eq $appExists) {
    Write-Host "🚀 Creating Web App '$appName'..."
    az webapp create --name $appName --resource-group $resourceGroup --plan $appServicePlan --runtime "PYTHON|$pythonVersion"
    
    # Configure Python specific settings
    az webapp config set --resource-group $resourceGroup --name $appName `
        --linux-fx-version "PYTHON|$pythonVersion" \
        --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 -k uvicorn.workers.UvicornWorker app.main:app"
} else {
    Write-Host "✅ Web App '$appName' already exists."
}

# Configure environment variables
Write-Host "🔧 Configuring application settings..."

# Get database connection string from environment variables or use existing one
$dbConnectionString = "postgresql+asyncpg://useradmin:Chat8121943.@chatbot-iram.postgres.database.azure.com:5432/chatbot_db?ssl=require"

# Application settings
$appSettings = @{
    # Server configuration
    WEBSITES_PORT = "8000"
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    ENABLE_ORYX_BUILD = "true"
    PYTHON_ENABLE_WORKER_EXTENSIONS = "1"
    
    # Database
    DATABASE_URL = $dbConnectionString
    
    # WhatsApp
    WHATSAPP_PHONE_NUMBER_ID = "665300739992317"
    WHATSAPP_ACCESS_TOKEN = "EAAJtmxxtxScBO2rZB0hZAREor30UII4vWncKV3hCOGFlmcIpRmvKNpYROUPW6eHuwbDt7p5JFWHYuZCHcnfbFOHH9TZAMakmnnfdEuoocCzeU63lTsqfSZAD1m05tZBowKMsL6qJLNwHzhtoOpGI5nLf3LWXZBsDo5k985PutKU7vtV2rVb6Wke7dPNmUHkk2XKCQZDZD"
    
    # Facebook Messenger
    MESSENGER_PAGE_ACCESS_TOKEN = "your_facebook_page_access_token"
    VERIFY_TOKEN = "Julia"
    RECIPIENT_WAID = "+56941325404"
    APP_ID = "683462917735719"
    APP_SECRET = "37ca6279f0c98a2afd27a7204802ba4a"
    
    # Azure Storage for FAISS
    STORAGE_ACCOUNT_NAME = "chat2025"
    CONTAINER_NAME = "chat2025"
    AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=chat2025;***REMOVED***;EndpointSuffix=core.windows.net"
    FAISS_INDEX_NAME = "index"
    
    # Application settings
    DEBUG_MODE = "False"
    LOG_LEVEL = "INFO"
    
    # Security
    SECRET_KEY = "your-secret-key-here"  # Change this to a secure random string
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = "1440"  # 24 hours
}
    # AI and Embeddings
    EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    RAG_DEFAULT_K = "3"
    
    # Calendly Integration
    CALENDLY_API_KEY = "***REMOVED***"
    CALENDLY_EVENT_TYPE_URI = "https://api.calendly.com/event_types/6943da13-c493-4a09-8830-2184f4332a92"
    FAISS_INDEX_NAME = "index"
    FAISS_FOLDER_NAME = "faiss_index_kb_spanish_v1"
    WHATSAPP_TOKEN_EXPIRATION = "2025-05-06T17:00:00Z"
    LOG_LEVEL = "INFO"
    LOG_MAX_SIZE = "10485760"
    LOG_BACKUP_COUNT = "30"
    CALENDLY_TIMEZONE = "America/Mexico_City"
    SERVER_HOST = "0.0.0.0"
    SERVER_PORT = "8000"
    OPENROUTER_API_KEY = "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"
    CALENDLY_USER_SLUG = "chatbotiram-mex"
    CALENDLY_DAYS_TO_CHECK = "7"
    OPENROUTER_MODEL_CHAT = "meta-llama/llama-3-8b-instruct"
    OPENROUTER_CHAT_ENDPOINT = "https://openrouter.ai/api/v1"
    LLM_TEMPERATURE = "0.5"
    LLM_MAX_TOKENS = "1000"
    HUGGINGFACE_TOKEN = "***REMOVED***"
    PGHOST = "chatbot-iram.postgres.database.azure.com"
    PGUSER = "useradmin"
    PGPASSWORD = "Chat8121943."
    PGDATABASE = "chatbot_db"
    PGPORT = "5432"
    SSL_MODE = "require"
    DATABASE_URL = "postgresql+asyncpg://useradmin:Chat8121943.@chatbot-iram.postgres.database.azure.com:5432/chatbot_db?ssl=require"
}

# Convert the settings hashtable to a JSON string and update the app settings
$settingsJson = $appSettings | ConvertTo-Json -Compress -Depth 10

Write-Host "🔧 Updating application settings..."
az webapp config appsettings set --resource-group $resourceGroup --name $appName --settings $settingsJson

# Configure logging
Write-Host "📝 Configuring logging..."
az webapp log config --resource-group $resourceGroup --name $appName --docker-container-logging filesystem --level information

# Configure deployment from GitHub
Write-Host "🚀 Configuring GitHub deployment..."
# Uncomment and update with your GitHub repository details
<#
$githubRepo = "your-username/your-repo"
$githubBranch = "main"
$githubToken = "your-github-token"

az webapp deployment source config --name $appName --resource-group $resourceGroup \
    --repo-url "https://github.com/$githubRepo" --branch $githubBranch --git-token $githubToken
#>

# Configure Always On
Write-Host "🔌 Enabling Always On..."
az webapp config set --resource-group $resourceGroup --name $appName --always-on true

# Configure web sockets
Write-Host "🔌 Enabling Web Sockets..."
az webapp config set --resource-group $resourceGroup --name $appName --web-sockets-enabled true

# Configure auto-heal
Write-Host "⚕️  Configuring Auto-heal..."
az webapp config set --resource-group $resourceGroup --name $appName \
    --auto-heal-enabled true \
    --slow-request-time 30 \
    --http20-enabled true

# Restart the app to apply all settings
Write-Host "🔄 Restarting the application..."
az webapp restart --resource-group $resourceGroup --name $appName

# Get the app URL
$appUrl = "https://$appName.azurewebsites.net"

# Display deployment summary
Write-Host ""
Write-Host "🎉 Deployment completed successfully!"
Write-Host ""
Write-Host "🔗 Application URL: $appUrl"
Write-Host "📊 Azure Portal: https://portal.azure.com/#@/resource/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.Web/sites/$appName/overview"
Write-Host ""
Write-Host "📋 Next steps:"
Write-Host "1. Verify the application is running: curl -I $appUrl"
Write-Host "2. Check logs: az webapp log tail --resource-group $resourceGroup --name $appName"
Write-Host "3. Set up continuous deployment from your Git repository"
Write-Host "4. Configure custom domain and SSL if needed"
Write-Host ""
Write-Host "💡 Tip: You can monitor your application in the Azure Portal:"
Write-Host "   - Application Insights: https://portal.azure.com/#@/resource/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/microsoft.insights/components/$appName/overview"
Write-Host "   - Metrics: https://portal.azure.com/#@/resource/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.Web/sites/$appName/metrics"
Write-Host ""
Write-Host "✅ Deployment completed successfully!"