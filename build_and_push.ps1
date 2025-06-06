# Script para construir y desplegar la imagen Docker a Azure Container Registry
param (
    [switch]$LocalBuild = $false,
    [switch]$PushToRegistry = $false
)

# Variables de entorno
$ACR_REGISTRY = "chat2025.azurecr.io"
$IMAGE_NAME = "chat-app"
$TAG = "latest"

Write-Host "==== INICIANDO PROCESO DE CONSTRUCCIÓN Y DESPLIEGUE ====" -ForegroundColor Green

# 1. Construir la imagen Docker optimizada
Write-Host "1. Construyendo imagen Docker optimizada..." -ForegroundColor Cyan
docker build -t $IMAGE_NAME`:$TAG .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error al construir la imagen Docker" -ForegroundColor Red
    exit 1
}

Write-Host "Imagen construida exitosamente: $IMAGE_NAME`:$TAG" -ForegroundColor Green

# Comprobar tamaño de la imagen
Write-Host "`nTamaño de la imagen:" -ForegroundColor Cyan
docker images $IMAGE_NAME`:$TAG --format "{{.Size}}"

# 2. Probar ejecución local si se solicita
if ($LocalBuild) {
    Write-Host "`n2. Ejecutando imagen localmente para pruebas..." -ForegroundColor Cyan
    Write-Host "Presiona Ctrl+C para detener la ejecución local cuando termines de probar" -ForegroundColor Yellow
    
    # Ejecutar la imagen localmente
    docker run -p 8000:8000 --name chatbot-test $IMAGE_NAME`:$TAG
    
    # Limpiar el contenedor de prueba
    docker rm -f chatbot-test
}

# 3. Etiquetar y enviar a ACR si se solicita
if ($PushToRegistry) {
    Write-Host "`n3. Etiquetando y enviando imagen a Azure Container Registry..." -ForegroundColor Cyan
    
    # Etiquetar la imagen para el registro
    docker tag $IMAGE_NAME`:$TAG $ACR_REGISTRY/$IMAGE_NAME`:$TAG
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error al etiquetar la imagen" -ForegroundColor Red
        exit 1
    }
    
    # Verificar que estamos autenticados en ACR
    Write-Host "Verificando autenticación en ACR..." -ForegroundColor Cyan
    
    # Solicitar la contraseña de forma segura o usar una variable de entorno
    if (-not $env:ACR_PASSWORD) {
        $securePassword = Read-Host "Introduce la contraseña del ACR (chat2025)" -AsSecureString
        $password = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword))
    } else {
        $password = $env:ACR_PASSWORD
    }
    
    docker login $ACR_REGISTRY --username chat2025 --password $password
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error al autenticarse en ACR. Por favor, ejecuta manualmente:" -ForegroundColor Red
        Write-Host "docker login $ACR_REGISTRY --username chat2025" -ForegroundColor Yellow
        exit 1
    }
    
    # Enviar imagen a ACR
    Write-Host "Enviando imagen a ACR..." -ForegroundColor Cyan
    docker push $ACR_REGISTRY/$IMAGE_NAME`:$TAG
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error al enviar la imagen a ACR" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Imagen enviada exitosamente a: $ACR_REGISTRY/$IMAGE_NAME`:$TAG" -ForegroundColor Green
}

Write-Host "`n==== PROCESO COMPLETADO ====" -ForegroundColor Green

# Instrucciones finales
Write-Host "`nPara ejecutar solamente la construcción:" -ForegroundColor Yellow
Write-Host ".\build_and_push.ps1" -ForegroundColor White

Write-Host "`nPara ejecutar construcción y prueba local:" -ForegroundColor Yellow
Write-Host ".\build_and_push.ps1 -LocalBuild" -ForegroundColor White

Write-Host "`nPara ejecutar construcción y envío a ACR:" -ForegroundColor Yellow
Write-Host ".\build_and_push.ps1 -PushToRegistry" -ForegroundColor White

Write-Host "`nPara ejecutar construcción, prueba local y envío a ACR:" -ForegroundColor Yellow
Write-Host ".\build_and_push.ps1 -LocalBuild -PushToRegistry" -ForegroundColor White
