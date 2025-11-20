#!/bin/bash

# Script para probar el flujo completo del chat usando curl
# Uso: ./test_chat_flow.sh [username] [password]

BASE_URL="http://localhost:3000/api/v1"
USERNAME=${1:-"admin"}
PASSWORD=${2:-"admin123"}

echo "============================================================"
echo "PRUEBA DEL FLUJO COMPLETO DEL CHAT"
echo "============================================================"

# 1. Login
echo ""
echo "[1] Haciendo login con usuario: $USERNAME"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$USERNAME\", \"password\": \"$PASSWORD\"}")

# Verificar si el login fue exitoso
if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
  TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
  USER_ID=$(echo "$LOGIN_RESPONSE" | grep -o '"user_id":"[^"]*' | cut -d'"' -f4)
  echo "✅ Login exitoso - User ID: $USER_ID"
else
  echo "❌ Error en login"
  echo "Respuesta: $LOGIN_RESPONSE"
  # Intentar registrar usuario
  echo ""
  echo "[1.1] Intentando registrar usuario..."
  REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"$USERNAME\", \"email\": \"$USERNAME@test.com\", \"password\": \"$PASSWORD\"}")
  
  if echo "$REGISTER_RESPONSE" | grep -q "id"; then
    echo "✅ Usuario registrado exitosamente"
    # Intentar login de nuevo
    LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"username\": \"$USERNAME\", \"password\": \"$PASSWORD\"}")
    TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
    USER_ID=$(echo "$LOGIN_RESPONSE" | grep -o '"user_id":"[^"]*' | cut -d'"' -f4)
    echo "✅ Login exitoso - User ID: $USER_ID"
  else
    echo "❌ Error al registrar usuario"
    echo "Respuesta: $REGISTER_RESPONSE"
    exit 1
  fi
fi

if [ -z "$TOKEN" ]; then
  echo "❌ No se pudo obtener el token"
  exit 1
fi

# 2. Enviar primer mensaje: "quiero enviar 100 al 04140220846"
echo ""
echo "============================================================"
echo "PASO 1: Enviar datos de transferencia"
echo "============================================================"
echo ""
echo "[2] Enviando mensaje: 'quiero enviar 100 al 04140220846'"

CHAT_RESPONSE1=$(curl -s -X POST "$BASE_URL/conversations/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "quiero enviar 100 al 04140220846"}')

echo "$CHAT_RESPONSE1" | python3 -m json.tool 2>/dev/null || echo "$CHAT_RESPONSE1"

# Extraer conversation_id
CONVERSATION_ID=$(echo "$CHAT_RESPONSE1" | grep -o '"conversation_id":[0-9]*' | cut -d':' -f2)

if [ -z "$CONVERSATION_ID" ]; then
  echo "❌ No se pudo obtener el conversation_id"
  exit 1
fi

echo ""
echo "✅ Conversation ID: $CONVERSATION_ID"

# 3. Enviar segundo mensaje: "confirmo"
echo ""
echo "============================================================"
echo "PASO 2: Confirmar transacción"
echo "============================================================"
echo ""
echo "[3] Enviando mensaje: 'confirmo'"

CHAT_RESPONSE2=$(curl -s -X POST "$BASE_URL/conversations/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"message\": \"confirmo\", \"conversation_id\": $CONVERSATION_ID}")

echo "$CHAT_RESPONSE2" | python3 -m json.tool 2>/dev/null || echo "$CHAT_RESPONSE2"

# Resumen final
echo ""
echo "============================================================"
echo "RESUMEN FINAL"
echo "============================================================"
echo "✅ Flujo completado"
echo "   Conversation ID: $CONVERSATION_ID"


