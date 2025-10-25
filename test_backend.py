"""
Script de prueba para el backend de mensajería WhatsApp.

Este script demuestra cómo usar los diferentes endpoints del API
mediante peticiones HTTP usando la librería requests.
"""

import requests
import json

# Configuración del servidor
BASE_URL = "http://localhost:5000"

def print_response(title, response):
    """
    Imprime la respuesta del servidor de forma legible.
    
    Args:
        title: Título de la prueba
        response: Objeto Response de requests
    """
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print("="*70)


def test_health_check():
    """Prueba el endpoint de health check."""
    response = requests.get(f"{BASE_URL}/health")
    print_response("🏥 Health Check", response)
    return response.status_code == 200


def test_get_stats():
    """Obtiene estadísticas de los contactos."""
    response = requests.get(f"{BASE_URL}/api/contacts/stats")
    print_response("📊 Estadísticas de Contactos", response)
    return response.status_code == 200


def test_get_pending():
    """Lista los contactos pendientes."""
    response = requests.get(f"{BASE_URL}/api/contacts/pending")
    print_response("📋 Contactos Pendientes", response)
    return response.status_code == 200


def test_send_simple(phone, message):
    """
    Prueba el envío de un mensaje simple.
    
    Args:
        phone: Número de teléfono en formato E.164
        message: Texto del mensaje
    """
    payload = {
        "phone": phone,
        "message": message
    }
    
    response = requests.post(
        f"{BASE_URL}/api/messages/send-simple",
        json=payload
    )
    print_response("📱 Envío de Mensaje Simple", response)
    return response.status_code == 200


def test_send_batch(message, create_backup=True):
    """
    Prueba el envío masivo de mensajes.
    
    Args:
        message: Texto del mensaje
        create_backup: Si se debe crear backup del CSV
    """
    payload = {
        "message": message,
        "create_backup": create_backup
    }
    
    response = requests.post(
        f"{BASE_URL}/api/messages/send-batch",
        json=payload
    )
    print_response("📬 Envío Masivo", response)
    return response.status_code == 200


def main():
    """Función principal que ejecuta las pruebas."""
    print("\n" + "🧪 " + "="*66)
    print("  PRUEBAS DEL BACKEND - WhatsApp Messaging API")
    print("🧪 " + "="*66)
    
    print("\n⚠️  IMPORTANTE:")
    print("   - Asegúrate de que el servidor esté corriendo (python backend/app.py)")
    print("   - Configura las variables de entorno en el archivo .env")
    print("   - Ten el archivo bd_envio.csv en la raíz del proyecto\n")
    
    input("Presiona Enter para continuar...")
    
    # 1. Health Check
    if not test_health_check():
        print("\n❌ El servidor no está disponible o las credenciales son inválidas")
        return
    
    # 2. Estadísticas
    test_get_stats()
    
    # 3. Contactos pendientes
    test_get_pending()
    
    # 4. Envío simple (comentado por seguridad)
    # Descomenta y ajusta el número para probar
    # test_send_simple("+573001234567", "Mensaje de prueba desde la API")
    
    # 5. Envío masivo (comentado por seguridad)
    # Descomenta para probar el envío masivo
    # print("\n⚠️  ¿Deseas ejecutar el envío masivo?")
    # respuesta = input("Esto enviará mensajes a todos los contactos pendientes (si/no): ")
    # if respuesta.lower() in ['si', 'sí', 's', 'yes', 'y']:
    #     test_send_batch("Tu mensaje aquí", create_backup=True)
    
    print("\n✅ Pruebas completadas\n")


if __name__ == "__main__":
    main()
