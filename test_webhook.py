"""
Script para probar el webhook de WhatsApp localmente.

Este script simula lo que WhatsApp enviaría a tu webhook cuando un usuario
responde a un mensaje, permitiendo probar sin necesitar configurar ngrok
o tener respuestas reales de usuarios.
"""

import requests
import json

# Configuración
WEBHOOK_URL = "http://localhost:5000/webhook"


def test_webhook_verification():
    """
    Prueba la verificación del webhook (método GET).
    
    Simula la petición que Meta hace para verificar el webhook.
    """
    print("\n" + "="*70)
    print("  🔐 Prueba 1: Verificación del Webhook (GET)")
    print("="*70)
    
    params = {
        'hub.mode': 'subscribe',
        'hub.verify_token': 'mi_token_secreto_whatsapp_2024',  # Debe coincidir con .env
        'hub.challenge': 'test_challenge_123'
    }
    
    try:
        response = requests.get(WEBHOOK_URL, params=params)
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"✅ Respuesta: {response.text}")
        
        if response.status_code == 200 and response.text == 'test_challenge_123':
            print("\n🎉 Verificación exitosa!")
            return True
        else:
            print("\n❌ Verificación falló")
            return False
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_webhook_button_response():
    """
    Prueba el webhook con una respuesta de botón interactivo.
    
    Simula que un usuario presionó el botón "Sí confirmo ✅"
    """
    print("\n" + "="*70)
    print("  📱 Prueba 2: Respuesta de Botón Interactivo")
    print("="*70)
    
    # Este es el formato exacto que WhatsApp envía
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "787655334439239"
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Juan Pérez"},
                                    "wa_id": "573154963483"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "573154963483",  # Debe existir en tu CSV
                                    "id": "wamid.test123",
                                    "timestamp": "1698165123",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": "btn_si",
                                            "title": "Sí confirmo ✅"
                                        }
                                    }
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    print(f"\n📤 Enviando respuesta simulada de: +573154963483")
    print(f"📝 Respuesta: 'Sí confirmo ✅'")
    print(f"🆔 Button ID: 'btn_si'")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"✅ Respuesta: {response.json()}")
        
        if response.status_code == 200:
            print("\n🎉 Webhook procesó la respuesta exitosamente!")
            print("\n💡 Verifica tu CSV - debe tener:")
            print("   - respuesta: Sí confirmo ✅")
            print("   - fecha_respuesta: (timestamp actual)")
            print("   - respuesta_id: btn_si")
            return True
        else:
            print("\n❌ Error al procesar")
            return False
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_webhook_text_response():
    """
    Prueba el webhook con una respuesta de texto plano.
    
    Simula que un usuario escribió "Sí" como texto libre.
    """
    print("\n" + "="*70)
    print("  💬 Prueba 3: Respuesta de Texto Plano")
    print("="*70)
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "787655334439239"
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "María López"},
                                    "wa_id": "573113116974"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "573113116974",  # Debe existir en tu CSV
                                    "id": "wamid.test456",
                                    "timestamp": "1698165456",
                                    "type": "text",
                                    "text": {
                                        "body": "Sí, confirmo mi asistencia"
                                    }
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    print(f"\n📤 Enviando respuesta simulada de: +573113116974")
    print(f"📝 Respuesta: 'Sí, confirmo mi asistencia'")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"✅ Respuesta: {response.json()}")
        
        if response.status_code == 200:
            print("\n🎉 Webhook procesó la respuesta exitosamente!")
            print("\n💡 Verifica tu CSV - debe tener:")
            print("   - respuesta: Sí, confirmo mi asistencia")
            print("   - fecha_respuesta: (timestamp actual)")
            return True
        else:
            print("\n❌ Error al procesar")
            return False
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_webhook_unknown_contact():
    """
    Prueba el webhook con un número que NO está en el CSV.
    
    Debe manejar esto correctamente sin errores.
    """
    print("\n" + "="*70)
    print("  ❓ Prueba 4: Contacto No Registrado")
    print("="*70)
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "787655334439239"
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Usuario Desconocido"},
                                    "wa_id": "5739999999999"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "5739999999999",  # NO existe en el CSV
                                    "id": "wamid.test789",
                                    "timestamp": "1698165789",
                                    "type": "text",
                                    "text": {
                                        "body": "Hola"
                                    }
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    print(f"\n📤 Enviando respuesta de número NO registrado: +5739999999999")
    print(f"📝 Respuesta: 'Hola'")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"✅ Respuesta: {response.json()}")
        
        if response.status_code == 200:
            print("\n🎉 Webhook manejó correctamente el contacto desconocido!")
            print("   (No debería haber actualizado el CSV)")
            return True
        else:
            print("\n❌ Error al procesar")
            return False
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Ejecuta todas las pruebas del webhook."""
    print("\n" + "🧪 " + "="*66)
    print("  PRUEBAS DEL WEBHOOK - WhatsApp Responses")
    print("🧪 " + "="*66)
    
    print("\n⚠️  IMPORTANTE:")
    print("   1. El servidor debe estar corriendo: python backend/app.py")
    print("   2. Los números de prueba deben existir en bd_envio.csv")
    print("   3. Verifica el archivo CSV después de cada prueba")
    print()
    
    input("Presiona Enter para continuar...")
    
    results = []
    
    # Ejecutar pruebas
    results.append(("Verificación del webhook", test_webhook_verification()))
    results.append(("Respuesta con botón", test_webhook_button_response()))
    results.append(("Respuesta de texto", test_webhook_text_response()))
    results.append(("Contacto no registrado", test_webhook_unknown_contact()))
    
    # Resumen
    print("\n" + "="*70)
    print("  📊 RESUMEN DE PRUEBAS")
    print("="*70)
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n🎯 Resultado: {passed}/{total} pruebas exitosas")
    
    if passed == total:
        print("\n🎉 ¡Todas las pruebas pasaron! El webhook está funcionando correctamente.")
    else:
        print("\n⚠️  Algunas pruebas fallaron. Revisa los logs del servidor.")
    
    print("\n💡 Ahora puedes:")
    print("   1. Configurar ngrok: ngrok http 5000")
    print("   2. Configurar el webhook en Meta for Developers")
    print("   3. Probar con mensajes reales de WhatsApp")
    print()


if __name__ == "__main__":
    main()
