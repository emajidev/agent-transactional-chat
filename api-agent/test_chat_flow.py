#!/usr/bin/env python3
"""
Script para probar el flujo completo del chat:
1. Login para obtener token
2. Enviar mensaje: "quiero enviar 100 al 04140220846"
3. Enviar mensaje: "confirmo"
"""

import requests
import json
import sys

BASE_URL = "http://localhost:3000/api/v1"

def login(username="admin", password="admin123"):
    """Hace login y retorna el token"""
    print(f"\n[1] Haciendo login con usuario: {username}")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": username, "password": password},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"❌ Error en login: {response.status_code}")
        print(f"Respuesta: {response.text}")
        # Intentar registrar usuario si no existe
        if response.status_code == 401:
            print("\n[1.1] Intentando registrar usuario...")
            register_response = requests.post(
                f"{BASE_URL}/auth/register",
                json={"username": username, "email": f"{username}@test.com", "password": password},
                headers={"Content-Type": "application/json"}
            )
            if register_response.status_code == 201:
                print("✅ Usuario registrado exitosamente")
                # Intentar login de nuevo
                response = requests.post(
                    f"{BASE_URL}/auth/login",
                    json={"username": username, "password": password},
                    headers={"Content-Type": "application/json"}
                )
            else:
                print(f"❌ Error al registrar: {register_response.status_code}")
                print(f"Respuesta: {register_response.text}")
                return None
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        user_id = data.get("user_id")
        print(f"✅ Login exitoso - User ID: {user_id}")
        return token, user_id
    else:
        print(f"❌ Error en login: {response.status_code}")
        print(f"Respuesta: {response.text}")
        return None, None

def send_chat_message(token, message, conversation_id=None):
    """Envía un mensaje al chat"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    print(f"\n[2] Enviando mensaje: '{message}'")
    if conversation_id:
        print(f"    Conversation ID: {conversation_id}")
    
    response = requests.post(
        f"{BASE_URL}/conversations/chat",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Mensaje procesado exitosamente")
        print(f"   Respuesta: {data.get('response', '')[:200]}")
        print(f"   Conversation ID: {data.get('conversation_id')}")
        print(f"   Status: {data.get('status')}")
        if data.get('state'):
            state = data['state']
            print(f"   Estado:")
            print(f"     - Teléfono: {state.get('recipient_phone')}")
            print(f"     - Monto: {state.get('amount')}")
            print(f"     - Confirmación pendiente: {state.get('confirmation_pending')}")
        return data
    else:
        print(f"❌ Error al enviar mensaje: {response.status_code}")
        print(f"Respuesta: {response.text}")
        return None

def main():
    print("=" * 60)
    print("PRUEBA DEL FLUJO COMPLETO DEL CHAT")
    print("=" * 60)
    
    # 1. Login
    token, user_id = login()
    if not token:
        print("\n❌ No se pudo obtener el token. Asegúrate de que el servidor esté corriendo.")
        sys.exit(1)
    
    # 2. Enviar primer mensaje: "quiero enviar 100 al 04140220846"
    print("\n" + "=" * 60)
    print("PASO 1: Enviar datos de transferencia")
    print("=" * 60)
    response1 = send_chat_message(token, "quiero enviar 100 al 04140220846")
    
    if not response1:
        print("\n❌ Error al enviar el primer mensaje")
        sys.exit(1)
    
    conversation_id = response1.get("conversation_id")
    
    # 3. Enviar segundo mensaje: "confirmo"
    print("\n" + "=" * 60)
    print("PASO 2: Confirmar transacción")
    print("=" * 60)
    response2 = send_chat_message(token, "confirmo", conversation_id)
    
    if not response2:
        print("\n❌ Error al enviar el segundo mensaje")
        sys.exit(1)
    
    # Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    print(f"✅ Flujo completado exitosamente")
    print(f"   Conversation ID: {conversation_id}")
    print(f"   Respuesta final: {response2.get('response', '')[:200]}")
    if response2.get('state'):
        state = response2['state']
        print(f"   Transaction ID: {state.get('transaction_id')}")
        print(f"   Confirmación pendiente: {state.get('confirmation_pending')}")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: No se pudo conectar al servidor.")
        print("   Asegúrate de que el servidor esté corriendo en http://localhost:3000")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Prueba cancelada por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

