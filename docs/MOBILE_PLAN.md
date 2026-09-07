# Plan: Port Mobile — YT-DownLoader

## Arquitectura General

```
┌────────────────────┐        HTTP/SSE         ┌─────────────────────────┐
│   Android App      │ ◄─────────────────────► │   ASP.NET 8 Backend     │
│   (Flutter)        │   REST + Server-Sent    │   + yt-dlp (Python)     │
│                    │   Events (progreso)     │   + ffmpeg              │
└────────────────────┘                        └─────────────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  Almacenamiento  │
                                              │  (local / S3)    │
                                              └─────────────────┘
```

## 1. Backend — ASP.NET 8

### Tecnologías
- **ASP.NET 8** (Web API / Minimal APIs)
- **yt-dlp** invocado vía `Process` (subprocess) o binding Python interop
- **ffmpeg** para conversión de audio (mp3) y muxing de video (mp4)
- **SignalR** o **Server-Sent Events** para progreso en tiempo real
- **Redis** (opcional) para cola de descargas y caché de resultados

### Endpoints

#### Descarga
```
POST   /api/downloads
Body:  { "url": "...", "format": "audio|video", "quality": "128|256|320|best", "platform": "auto" }
Response: { "id": "guid", "status": "queued", "createdAt": "..." }
```

#### Progreso (SSE o WebSocket)
```
GET    /api/downloads/{id}/progress
Response (SSE stream):
  event: progress
  data: { "percent": 45.2, "speed": "2.5MiB/s", "eta": "0:32", "status": "downloading" }

  event: complete
  data: { "status": "completed", "fileName": "song.mp3", "fileSize": 5242880, "downloadUrl": "/api/downloads/{id}/file" }

  event: error
  data: { "status": "failed", "error": "Video privado o no disponible" }
```

#### Descarga de archivo
```
GET    /api/downloads/{id}/file
Response: stream binario del archivo (audio/video)
Headers: Content-Disposition, Content-Length, Content-Type
```

#### Estado
```
GET    /api/downloads/{id}
Response: { "id": "guid", "status": "completed", "title": "...", "duration": 210, "thumbnail": "...", "platform": "youtube" }
```

#### Cancelar
```
DELETE /api/downloads/{id}
Response: { "status": "cancelled" }
```

#### Info del video (preview sin descargar)
```
POST   /api/resolve
Body:  { "url": "..." }
Response: { "title": "...", "duration": 210, "thumbnail": "...", "platform": "youtube", "formats": [...] }
```

### Lógica de negocio a portar (desde Python → C#)

| Función Python actual | Equivalente ASP.NET |
|---|---|
| `detectar_plataforma(url)` | `PlatformDetector.Detect(url)` — regex por plataforma |
| `es_youtube(url)` | `PlatformDetector.IsYouTube(url)` |
| `PLATFORM_REGEX` | `Dictionary<Plataforma, Regex>` estático |
| `descargar_musica()` + yt-dlp progress hooks | `DownloadService.ExecuteAsync()` — llama yt-dlp vía Process, parsea stdout JSON para progreso |
| Selección de formato (audio/video/quality) | `FormatSelector.GetArgs(format, quality)` — genera args de yt-dlp |
| `find_ffmpeg()` | `FFmpegLocator.Find()` — busca ffmpeg en PATH o ruta configurable |
| Config JSON (~/.yt-downloader/config.json) | `IOptions<T>` + `appsettings.json` o SQLite |
| `check_for_update()` | `UpdateService.CheckVersionAsync()` — GitHub Releases API |
| Manejo de errores por plataforma (no-technical) | `ErrorMapper.Map(stderr)` — traduce stderr de yt-dlp a mensajes amigables |

### Estructura del proyecto

```
YT-DownLoader.Api/
├── Controllers/
│   └── DownloadsController.cs
├── Services/
│   ├── DownloadService.cs          # Orquesta llamadas a yt-dlp
│   ├── FormatSelector.cs           # Selección de formato/calidad
│   ├── PlatformDetector.cs         # Detección de plataforma
│   ├── FFmpegLocator.cs            # Ubicación de ffmpeg
│   ├── ErrorMapper.cs              # Errores amigables
│   └── UpdateService.cs            # Check de actualizaciones
├── Models/
│   ├── DownloadRequest.cs
│   ├── DownloadProgress.cs
│   ├── DownloadResult.cs
│   └── VideoInfo.cs
├── Hubs/                           # SignalR para progreso en tiempo real
│   └── DownloadHub.cs
├── Middleware/
│   └── RateLimitMiddleware.cs      # Anti-abuso
├── appsettings.json
└── Program.cs
```

### Manejo de yt-dlp desde C#

```csharp
// Ejecutar yt-dlp como proceso hijo, parsear progreso en tiempo real
var process = new Process
{
    StartInfo = new ProcessStartInfo
    {
        FileName = "yt-dlp",
        Arguments = BuildArgs(request),
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        UseShellExecute = false,
    }
};

// yt-dlp imprime progreso en stderr con --progress
// Ejemplo de línea: "[download]  45.2% of 11.58MiB at 2.50MiB/s ETA 00:32"
// Parsear y emitir vía SignalR/SSE al cliente
```

## 2. Mobile — Flutter

### Por qué Flutter
- UI nativa compilada (no WebView)
- Soporte Android nativo, iOS preparado para futuro
- Material Design 3 se alinea con el HUD de la app desktop
- Comunidad grande, paquetes para HTTP, WebSocket, notificaciones

### Estructura del proyecto

```
yt_downloader_mobile/
├── lib/
│   ├── main.dart
│   ├── app.dart
│   ├── core/
│   │   ├── api/
│   │   │   ├── api_client.dart             # HTTP client (Dio)
│   │   │   ├── download_api.dart           # Endpoints de descarga
│   │   │   └── sse_client.dart             # Server-Sent Events listener
│   │   ├── models/
│   │   │   ├── download_request.dart
│   │   │   ├── download_progress.dart
│   │   │   ├── download_result.dart
│   │   │   └── video_info.dart
│   │   ├── services/
│   │   │   ├── download_service.dart        # Lógica de cola local
│   │   │   └── storage_service.dart         # SharedPreferences / archivos
│   │   └── theme/
│   │       ├── app_theme.dart               # Tokens HUD (port del desktop)
│   │       └── app_colors.dart
│   ├── features/
│   │   ├── home/
│   │   │   ├── home_screen.dart
│   │   │   └── widgets/
│   │   │       ├── url_input.dart
│   │   │       ├── format_selector.dart     # Chips Audio/Video (port del desktop)
│   │   │       ├── quality_picker.dart
│   │   │       └── platform_badge.dart
│   │   ├── queue/
│   │   │   ├── queue_screen.dart
│   │   │   └── widgets/
│   │   │       ├── queue_card.dart          # Tarjeta con progreso circular
│   │   │       └── progress_ring.dart       # Canvas ring (port del desktop)
│   │   └── settings/
│   │       ├── settings_screen.dart
│   │       └── widgets/
│   │           ├── server_config.dart       # URL del backend
│   │           └── quality_default.dart
│   └── utils/
│       ├── platform_regex.dart              # Port de PLATFORM_REGEX
│       └── error_messages.dart              # Port de mensajes por plataforma
├── assets/
│   └── fonts/
├── pubspec.yaml
└── android/
```

### UI — Port del desktop

| Widget desktop (CustomTkinter) | Widget mobile (Flutter) |
|---|---|
| SegmentedControl Audio/Video | `ChoiceChip` o custom segmentado |
| PillToggle (Subtítulos, Playlist) | `SwitchListTile` o custom pills |
| Canvas ring progress | `CustomPaint` con `CircularProgressIndicator` custom |
| QueueCard | `Card` + `LinearProgressIndicator` + badge |
| URL input (JetBrains Mono) | `TextField` + `TextStyle(fontFamily: 'JetBrains Mono')` |
| Status bar | `BottomNavigationBar` o `SnackBar` |
| Empty state placeholder | `Center` + `Column` con icono y texto |

### Paquetes Flutter necesarios

```yaml
dependencies:
  dio: ^5.4.0                    # HTTP client
  flutter_riverpod: ^2.5.0       # State management
  go_router: ^14.0.0             # Navegación
  share_plus: ^9.0.0             # Compartir archivos
  path_provider: ^2.1.0          # Acceso a directorios
 permission_handler: ^11.0.0     # Permisos de almacenamiento
  flutter_local_notifications: ^17.0.0  # Notificaciones de descarga completa
```

## 3. Comunicación Backend ↔ Mobile

### REST API
- Crear descarga: `POST /api/downloads`
- Info de video: `POST /api/resolve`
- Cancelar: `DELETE /api/downloads/{id}`
- Descargar archivo: `GET /api/downloads/{id}/file`

### Server-Sent Events (progreso)
- `GET /api/downloads/{id}/progress`
- Eventos: `progress`, `complete`, `error`
- Más simple que WebSocket, suficiente para unidireccional (backend → mobile)

### Flujo completo

```
1. Usuario pega URL → POST /api/resolve (preview: título, duración, thumbnail)
2. Usuario selecciona formato/calidad → POST /api/downloads
3. Backend inicia descarga yt-dlp → emite eventos SSE de progreso
4. Mobile escucha SSE → actualiza UI en tiempo real (ring, %, velocidad)
5. Descarga completa → evento "complete" con URL del archivo
6. Mobile descarga archivo →保存 localmente o comparte
```

## 4. Futuro: iOS

Si se extiende a iOS:
- Flutter ya soporta iOS con el mismo código
- Backend no cambia (es independiente del cliente)
- Solo ajustes de permisos (NSAppTransportSecurity, almacenamiento)

## 5. Orden de implementación sugerido

1. **Backend ASP.NET 8**: Endpoints básicos + yt-dlp integration
2. **Flutter**: UI base + conexión al backend
3. **Progreso en tiempo real**: SSE backend → Flutter listener
4. **Manejo de cola**: Múltiples descargas simultáneas
5. **Notificaciones**: Descarga completa
6. **Settings**: URL del backend, calidad por defecto
7. **Polish**: Animaciones, errores amigables, empty states
