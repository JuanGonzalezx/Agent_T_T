"""
Backend Flask para sistema de mensajeria WhatsApp.

Este paquete proporciona una API REST completa para el envio de mensajes
de WhatsApp usando Turso como fuente unica de verdad.

Modulos:
    - app: Servidor Flask principal con endpoints
    - services.whatsapp_service: Comunicacion con WhatsApp Business API
    - services.db_handler: Gestion de base de datos Turso
    - services.google_drive_service: Integracion con Google Drive

Version: 2.0.0
"""

__version__ = '2.0.0'
__author__ = 'Agent_T_T'
__all__ = ['app']
