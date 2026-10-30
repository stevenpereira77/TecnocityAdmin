# Configurar Google Drive para Tecnocity Admin

Tecnocity Admin usa OAuth 2.0 para conectar una cuenta de Google Drive desde la aplicación. No es necesario editar código para seleccionar la cuenta ni el correo destino.

## 1. Preparar Google Cloud

1. Crea o selecciona un proyecto en Google Cloud.
2. Habilita la **Google Drive API**.
3. Configura la pantalla de consentimiento de Google Auth Platform.
4. Crea un cliente OAuth 2.0 de tipo **Desktop app** y descarga el JSON de credenciales.

Google documenta este flujo para aplicaciones de escritorio y la instalación de las bibliotecas cliente de Python en su quickstart oficial.  

## 2. Instalar las dependencias

Desde la carpeta del proyecto:

```text
python -m pip install -r requirements.txt
```

## 3. Conectar la cuenta desde Tecnocity

En **Configuración → Google Drive**:

1. Pulsa **Seleccionar credenciales…** y elige el JSON descargado de Google Cloud.
2. Pulsa **Conectar / cambiar cuenta**.
3. El navegador abrirá el consentimiento de Google. Selecciona la cuenta que quieres usar.
4. Después de autorizar, Tecnocity mostrará el correo conectado.
5. Escribe el **Correo destino / compartido** si quieres dar acceso a una segunda cuenta.
6. Define el nombre de la carpeta y guarda.
7. Usa **Crear respaldo y verificar ahora** para comprobar todo el flujo.

El respaldo se guarda en una carpeta propia de Tecnocity en la cuenta conectada. En Google Drive, los archivos creados mediante OAuth pertenecen a la cuenta que autorizó la aplicación; si indicas otro correo, Tecnocity comparte la carpeta con ese correo en modo lectura para que pueda consultar los respaldos. La copia no se transfiere automáticamente a "Mi unidad" de la segunda cuenta.

## 4. Respaldo automático

En **Configuración → Automatización**:

1. Activa **Programar respaldo automático diario**.
2. Define la hora en formato 24 horas, por ejemplo `23:00`.
3. Pulsa **Guardar automatización**.
4. Pulsa **Configurar tarea automática de Windows**.

La tarea de Windows ejecuta:

```text
python run.py --backup-now
```

Así el respaldo puede ejecutarse aunque la ventana de Tecnocity esté cerrada. La tarea debe poder ejecutarse con el mismo usuario/entorno con el que se configuró el programa.

También puedes activar **Comprobar al iniciar Tecnocity si falta un respaldo del día**.

## 5. Verificación

Cada respaldo de Google Drive verifica automáticamente:

- tamaño local vs. tamaño remoto
- MD5 local vs. MD5 devuelto por Google Drive cuando está disponible
- integridad de la copia SQLite con `PRAGMA integrity_check`

El resultado queda guardado en el historial local de respaldos.

## 6. Restauración

Antes de reemplazar la base actual, Tecnocity crea un archivo:

```text
PreRestore_YYYY-MM-DD_HH-MM-SS.db
```

Puedes restaurar desde:

- un archivo `.db` local
- un respaldo almacenado en Google Drive

Después de restaurar se recomienda reiniciar Tecnocity para que todas las vistas carguen nuevamente la base restaurada.

## Seguridad

No subas al repositorio estos archivos:

```text
data/config/google/client_secret.json
data/config/google/token.json
data/config/settings.json
data/backups/*
```

Ya están incluidos en `.gitignore`.

La API usa el alcance `drive.file`, limitado a archivos que la aplicación crea o administra con ese acceso. Revisa siempre los permisos mostrados por Google antes de autorizar.
