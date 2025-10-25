"""
Backend Flask para sistema de mensajería WhatsApp.

Este paquete proporciona una API REST completa para el envío de mensajes
de WhatsApp, gestión de contactos y estadísticas.

Módulos:
    - app: Servidor Flask principal con endpoints
    - services.whatsapp_service: Comunicación con WhatsApp Business API
    - utils.csv_handler: Gestión de archivos CSV de contactos

Versión: 1.0.0
"""

__version__ = '1.0.0'
__author__ = 'Agent_T_T'
__all__ = ['app']
