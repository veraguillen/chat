# app/models/webhook_models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any # Asegúrate de importar Optional

# --- Modelos WhatsApp ---

class WhatsAppTextMessage(BaseModel):
    body: str

class WhatsAppInteractiveListReply(BaseModel):
    id: str
    title: str
    description: Optional[str] = None

class WhatsAppInteractive(BaseModel):
    type: str
    list_reply: Optional[WhatsAppInteractiveListReply] = None
    # button_reply: Optional[Dict[str, Any]] = None # Si usas botones

class WhatsAppContext(BaseModel): # Para identificar respuestas a mensajes previos
    from_: Optional[str] = Field(None, alias='from')
    id: Optional[str] = None

class WhatsAppMessage(BaseModel):
    from_: str = Field(..., alias='from')
    id: str
    timestamp: str
    type: str
    text: Optional[WhatsAppTextMessage] = None
    interactive: Optional[WhatsAppInteractive] = None
    context: Optional[WhatsAppContext] = None # Añadido por si respondes
    # Añadir otros tipos que manejes: image, audio, document, etc.

class WhatsAppStatus(BaseModel): # Modelo para actualizaciones de estado
    id: str # wam_id del mensaje original
    recipient_id: str
    status: str # sent, delivered, read, failed
    timestamp: str
    # conversation: Optional[Dict[str, Any]] = None # Info de la conversación
    # pricing: Optional[Dict[str, Any]] = None # Info de costos

class WhatsAppErrorData(BaseModel):
    details: str

class WhatsAppError(BaseModel):
    code: int
    title: str
    message: Optional[str] = None
    error_data: Optional[WhatsAppErrorData] = None


class WhatsAppMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str

class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: WhatsAppMetadata
    # contacts: Optional[List[Dict[str, Any]]] = None # Info del contacto

    # --- CORRECCIÓN AQUÍ: Hacer messages y statuses opcionales ---
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[WhatsAppStatus]] = None # Añadir statuses como opcional
    errors: Optional[List[WhatsAppError]] = None # Añadir errores como opcional
    # ----------------------------------------------------------

class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str # Usualmente 'messages' o 'statuses'

class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]

class WhatsAppPayload(BaseModel):
    object: str
    entry: List[WhatsAppEntry]

# --- Modelos Messenger (Sin cambios necesarios por ahora) ---
# ... (tus modelos Messenger existentes) ...
class MessengerTextMessage(BaseModel):
    mid: str
    text: str

class MessengerSender(BaseModel):
    id: str # PSID

class MessengerRecipient(BaseModel):
    id: str # Page ID

class MessagingEvent(BaseModel):
    sender: MessengerSender
    recipient: MessengerRecipient
    timestamp: int
    message: Optional[MessengerTextMessage] = None
    # ... otros eventos de Messenger ...

class MessengerEntry(BaseModel):
    id: str # Page ID
    time: int
    messaging: List[MessagingEvent]

class MessengerPayload(BaseModel):
    object: str # 'page'
    entry: List[MessengerEntry]