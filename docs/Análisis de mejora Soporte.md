# Análisis de mejora: Soporte para contenido con autenticación

## Objetivo

Evaluar la posibilidad de mejorar la experiencia del usuario cuando intenta descargar contenido que requiere autenticación en plataformas compatibles con `yt-dlp`, sin intentar eludir restricciones de acceso.

---

# Problema actual

Actualmente la aplicación descarga correctamente contenido público.

Sin embargo, cuando el contenido presenta alguna restricción, la descarga falla.

Ejemplos:

- Video privado
- Video con restricción de edad
- Contenido exclusivo para miembros
- Contenido bloqueado por región
- Contenido que requiere iniciar sesión

El usuario únicamente recibe un error generado por `yt-dlp`, sin una explicación clara ni posibles acciones.

---

# Objetivos

La aplicación debe ser capaz de:

- Detectar automáticamente el motivo del error.
- Mostrar mensajes comprensibles para el usuario.
- Permitir utilizar la sesión existente del navegador cuando sea posible.
- No almacenar credenciales del usuario.
- Mantener la seguridad del proyecto.

---

# Propuesta

## 1. Clasificación de errores

Investigar cómo capturar las excepciones producidas por `yt-dlp`.

Crear un sistema que identifique errores frecuentes, por ejemplo:

| Error detectado | Mensaje mostrado |
|-----------------|------------------|
| Private video | Este video es privado. |
| Members only | Solo disponible para miembros del canal. |
| Age restricted | Este contenido requiere iniciar sesión. |
| Video unavailable | El video ya no está disponible. |
| Geo restriction | El contenido no está disponible en tu región. |

La aplicación debe mostrar mensajes amigables en lugar del error original.

---

## 2. Uso opcional de cookies del navegador

Investigar la integración con:

```
yt-dlp --cookies-from-browser
```

Navegadores compatibles:

- Chrome
- Edge
- Firefox
- Brave

Objetivos:

- No solicitar usuario ni contraseña.
- No almacenar cookies manualmente.
- Aprovechar únicamente la sesión que ya posee el usuario.

Esto permitiría acceder únicamente a contenido para el cual el usuario ya tiene autorización.

Ejemplos:

- Videos con restricción de edad.
- Videos privados compartidos con la cuenta.
- Contenido para miembros (si la cuenta realmente posee la membresía).

No debe permitir acceder a contenido para el cual el usuario no tenga permisos.

---

## 3. Nueva configuración

Agregar una sección similar a:

```
Autenticación

☐ Usar sesión del navegador

Navegador:

( ) Chrome
( ) Edge
( ) Firefox
( ) Brave
```

La configuración debe ser opcional.

---

## 4. Verificación previa

Antes de comenzar la descarga:

1. Analizar la URL.
2. Obtener información mediante `yt-dlp`.
3. Detectar restricciones.
4. Informar al usuario.
5. Iniciar la descarga únicamente cuando sea posible.

Esto evita esperas innecesarias.

---

## 5. Diagnóstico avanzado

Agregar un panel de diagnóstico.

Ejemplo:

✔ URL válida

✔ FFmpeg encontrado

✔ yt-dlp actualizado

✖ Video privado

Sugerencia:

"Inicie sesión en su navegador y habilite la opción 'Usar sesión del navegador'."

---

# Aspectos de seguridad

No implementar:

- Inicio de sesión mediante usuario y contraseña.
- Almacenamiento permanente de cookies.
- Captura de credenciales.
- Métodos para eludir restricciones de acceso.

La aplicación únicamente debe utilizar mecanismos soportados oficialmente por `yt-dlp`.

---

# Beneficios

- Mejor experiencia de usuario.
- Errores comprensibles.
- Compatibilidad con contenido autenticado cuando el usuario posee acceso legítimo.
- Arquitectura preparada para futuras plataformas compatibles con `yt-dlp`.

---

# Preguntas para analizar

1. ¿Cómo detectar correctamente cada excepción generada por `yt-dlp`?

2. ¿Conviene implementar una clase dedicada para interpretar errores?

3. ¿Cuál sería la mejor arquitectura para integrar la autenticación sin acoplarla al resto del código?

4. ¿Cómo detectar automáticamente qué navegadores están disponibles?

5. ¿Cómo informar al usuario cuando las cookies hayan expirado?

6. ¿Es conveniente realizar una fase de análisis antes de iniciar cualquier descarga?

7. ¿Cómo mantener el código preparado para futuras plataformas además de YouTube?

---

# Resultado esperado

Diseñar una solución modular, segura y mantenible que permita utilizar sesiones existentes del navegador cuando el usuario ya posee acceso al contenido, mejorando la experiencia sin intentar eludir restricciones de las plataformas.
