# Script para desplegar la aplicación en Azure App Service

# Configuración
$subscriptionId = "148212ee-39f9-4c68-a01c-893b20634d54"
$resourceGroupName = "beta-bot"
$appServiceName = "chatbot-app"  # Nombre de la aplicación
$location = "eastus"  # Región de Azure
$planName = "chatbot-plan"

# Establecer la suscripción activa
az account set --subscription $subscriptionId

# Crear el plan de App Service
Write-Host "Creando plan de App Service..."
az appservice plan create \
    --name $planName \
    --resource-group $resourceGroupName \
    --location $location \
    --is-linux \
    --sku B1

# Crear la aplicación web
Write-Host "Creando aplicación web..."
az webapp create \
    --name $appServiceName \
    --plan $planName \
    --resource-group $resourceGroupName \
    --runtime "PYTHON|3.11"

# Configurar el despliegue desde Git
Write-Host "Configurando despliegue desde Git..."
az webapp deployment source config \
    --name $appServiceName \
    --resource-group $resourceGroupName \
    --repo-url "https://github.com/tu-repositorio.git" \
    --branch "main"

Write-Host "Despliegue configurado exitosamente!"
Write-Host "La aplicación está disponible en: https://$appServiceName.azurewebsites.net"
