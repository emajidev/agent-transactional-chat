# Chat Front - Frontend para Transferencias

Frontend React con TypeScript para el sistema de chat de transferencias.

## Características

- 🔐 Autenticación con usuario y contraseña
- 💬 Chat interactivo para realizar transferencias
- 🎨 Interfaz moderna con Tailwind CSS
- 🔒 Rutas protegidas
- 📱 Diseño responsive

## Instalación

```bash
npm install
```

## Desarrollo

```bash
npm run dev
```

La aplicación se ejecutará en `http://localhost:5173`

## Build

```bash
npm run build
```

## Configuración

El frontend está configurado para conectarse a la API en `http://localhost:3000` mediante un proxy configurado en `vite.config.ts`.

## Estructura

- `src/components/` - Componentes React
- `src/contexts/` - Contextos de React (Autenticación)
- `src/services/` - Servicios para llamadas a la API
- `src/App.tsx` - Componente principal con routing
- `src/main.tsx` - Punto de entrada

