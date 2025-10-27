"""
Servicio de mensajería WhatsApp.

Este módulo encapsula toda la lógica de negocio relacionada con el
envío de mensajes de WhatsApp a través de la API de Facebook Graph.
"""

import os
import json
import requests
from typing import Tuple
from dotenv import load_dotenv

# Cargar variables de entorno al importar el módulo
# Esto asegura que las credenciales estén disponibles desde el inicio
load_dotenv()


class WhatsAppService:
    """
    Servicio para el envío de mensajes de WhatsApp.
    
    Esta clase encapsula toda la comunicación con la API de WhatsApp Business,
    manejando autenticación, construcción de payloads y gestión de errores.
    """
    
    def __init__(self):
        """
        Inicializa el servicio con las credenciales de la API.
        
        Las credenciales se cargan desde variables de entorno para
        mantener la seguridad y facilitar el despliegue en diferentes
        ambientes (desarrollo, producción).
        """
        self.access_token = os.getenv("ACCESS_TOKEN")
        self.phone_number_id = os.getenv("PHONE_NUMBER_ID")
        self.version = os.getenv("VERSION", "v22.0")
        
        # La URL base se construye dinámicamente para facilitar cambios de versión
        self.base_url = f"https://graph.facebook.com/{self.version}/{self.phone_number_id}/messages"
    
    def validate_credentials(self) -> Tuple[bool, str]:
        """
        Valida que las credenciales estén configuradas correctamente.
        
        La validación temprana previene errores durante el envío y
        proporciona feedback claro sobre problemas de configuración.
        
        Returns:
            Tuple[bool, str]: (válido, mensaje)
        """
        if not self.access_token or self.access_token == "tu_token_aqui":
            return False, "ACCESS_TOKEN no configurado o inválido"
        
        if not self.phone_number_id:
            return False, "PHONE_NUMBER_ID no configurado"
        
        return True, "Credenciales válidas"
    
    def _build_text_message_payload(self, recipient: str, text: str) -> str:
        """
        Construye el payload JSON para un mensaje de texto.
        
        El payload sigue la especificación de la API de WhatsApp Business,
        permitiendo personalizar el tipo de mensaje y sus propiedades.
        
        Args:
            recipient: Número de teléfono en formato E.164
            text: Contenido del mensaje
            
        Returns:
            str: JSON string con el payload
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {
                "preview_url": False,  # Evita preview automático de URLs
                "body": text
            }
        }
        return json.dumps(payload)
    
    def _build_template_message_payload(self, recipient: str, template_name: str, language_code: str, parameters: list) -> str:
        """
        Construye el payload JSON para un mensaje de plantilla (template).
        
        Args:
            recipient: Número de teléfono en formato E.164
            template_name: Nombre de la plantilla aprobada
            language_code: Código de idioma
            parameters: Lista ordenada de valores
            
        Returns:
            str: JSON string con el payload
        """
        # Construir componentes solo si hay parámetros
        components = []
        
        if parameters and len(parameters) > 0:
            body_parameters = []
            for param_value in parameters:
                # Asegurar que el valor sea string y no esté vacío
                text_value = str(param_value).strip() if param_value else ""
                body_parameters.append({
                    "type": "text",
                    "text": text_value
                })
            
            components.append({
                "type": "body",
                "parameters": body_parameters
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                },
                "components": components
            }
        }
        # Usar dumps sin escape de caracteres Unicode
        return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    
    def _normalize_phone_number(self, phone: str) -> str:
        """
        Normaliza un número de teléfono al formato requerido por la API.
        
        La normalización elimina caracteres especiales que podrían causar
        errores en la API, asegurando formato consistente.
        
        Args:
            phone: Número de teléfono en cualquier formato
            
        Returns:
            str: Número normalizado (solo dígitos)
        """
        return str(phone).strip().replace('+', '').replace(' ', '').replace('-', '')
    
    def send_text_message(self, phone: str, message: str) -> Tuple[bool, str]:
        """
        Envía un mensaje de texto a un número de WhatsApp.
        
        Este método maneja todo el ciclo de envío: normalización del número,
        construcción del payload, llamada a la API y procesamiento de respuesta.
        
        Args:
            phone: Número de teléfono (se normalizará automáticamente)
            message: Texto del mensaje
            
        Returns:
            Tuple[bool, str]: (éxito, message_id o mensaje_error)
        """
        # Validar credenciales antes de intentar enviar
        # Esto evita llamadas API innecesarias con configuración incorrecta
        valid, msg = self.validate_credentials()
        if not valid:
            return False, msg
        
        # Normalizar el número de teléfono
        normalized_phone = self._normalize_phone_number(phone)
        
        # Construir el payload del mensaje
        payload = self._build_text_message_payload(normalized_phone, message)
        
        # Configurar headers de autenticación
        # El Bearer token es el método estándar de autenticación en Graph API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            # Timeout de 30s previene bloqueos indefinidos en caso de problemas de red
            response = requests.post(
                self.base_url,
                data=payload,
                headers=headers,
                timeout=30
            )
            
            # Procesar respuesta exitosa
            if response.status_code == 200:
                response_data = response.json()
                
                # Extraer el ID del mensaje de la respuesta
                # Este ID permite rastrear el mensaje en el sistema de WhatsApp
                if 'messages' in response_data and len(response_data['messages']) > 0:
                    message_id = response_data['messages'][0].get('id', '')
                    return True, message_id
                else:
                    return False, f"Respuesta inesperada: {response_data}"
            
            # Manejar errores de la API
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('message', response.text)
                return False, f"Error {response.status_code}: {error_msg}"
        
        # Manejo de excepciones de red y comunicación
        # Estos errores son comunes y requieren mensajes claros para debugging
        except requests.exceptions.Timeout:
            return False, "Timeout: La API no respondió a tiempo"
        
        except requests.exceptions.ConnectionError:
            return False, "Error de conexión: Verifica la conectividad a internet"
        
        except Exception as e:
            return False, f"Error inesperado: {str(e)}"
    
    def send_template_message(self, phone: str, template_name: str, parameters: list = None, language_code: str = "es") -> Tuple[bool, str]:
        """
        Envía un mensaje usando una plantilla pre-aprobada de WhatsApp.
        
        Las plantillas permiten enviar mensajes estructurados con variables
        dinámicas. Los parámetros deben enviarse en el orden exacto de la plantilla.
        
        Args:
            phone: Número de teléfono (se normalizará automáticamente)
            template_name: Nombre de la plantilla aprobada en Meta
            parameters: Lista ordenada de valores para las variables
                       Deben estar en el mismo orden que en la plantilla
            language_code: Código de idioma de la plantilla (default: "es")
            
        Returns:
            Tuple[bool, str]: (éxito, message_id o mensaje_error)
        """
        # Validar credenciales antes de intentar enviar
        valid, msg = self.validate_credentials()
        if not valid:
            return False, msg
        
        # Normalizar el número de teléfono
        normalized_phone = self._normalize_phone_number(phone)
        
        # Construir el payload del mensaje de plantilla
        payload = self._build_template_message_payload(
            normalized_phone, 
            template_name, 
            language_code, 
            parameters or []
        )
        
        # Configurar headers de autenticación
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            # Timeout de 30s previene bloqueos indefinidos
            response = requests.post(
                self.base_url,
                data=payload,
                headers=headers,
                timeout=30
            )
            
            # Procesar respuesta exitosa
            if response.status_code == 200:
                response_data = response.json()
                
                # Extraer el ID del mensaje
                if 'messages' in response_data and len(response_data['messages']) > 0:
                    message_id = response_data['messages'][0].get('id', '')
                    return True, message_id
                else:
                    return False, f"Respuesta inesperada: {response_data}"
            
            # Manejar errores de la API
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('message', response.text)
                return False, f"Error {response.status_code}: {error_msg}"
        
        # Manejo de excepciones de red
        except requests.exceptions.Timeout:
            return False, "Timeout: La API no respondió a tiempo"
        
        except requests.exceptions.ConnectionError:
            return False, "Error de conexión: Verifica la conectividad a internet"
        
        except Exception as e:
            return False, f"Error inesperado: {str(e)}"

