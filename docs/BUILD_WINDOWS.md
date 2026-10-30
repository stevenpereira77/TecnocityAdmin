# Instalación, compilación y distribución en Windows

Esta guía describe cómo ejecutar el código fuente y cómo generar una distribución de escritorio mediante PyInstaller.

## 1. Entorno de desarrollo

Instala Python 3.12 (compatible también con 3.11 y 3.13) y abre PowerShell en la carpeta del repositorio:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run.py
```

Para verificar el código y ejecutar pruebas:

```powershell
python -m compileall -q app tests tools run.py
python -m pytest -q
```

## 2. Crear la aplicación ejecutable

La compilación debe realizarse en Windows para producir una distribución Windows. No se debe intentar construir el ejecutable de Windows desde Linux o macOS.

Opción automática: ejecuta `tools\build_windows.bat` desde el Explorador o desde CMD. El script crea `.venv-build`, instala las dependencias de ejecución y PyInstaller y compila usando `TecnocityAdmin.spec`.

Opción manual desde PowerShell:

```powershell
py -3.12 -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean TecnocityAdmin.spec
```

El resultado se genera en:

```text
dist/TecnocityAdmin/TecnocityAdmin.exe
```

Es una distribución **onedir**: entrega la carpeta `dist/TecnocityAdmin` completa. No copies únicamente el `.exe`, porque necesita las bibliotecas Qt y otros archivos incluidos en esa carpeta.

## 3. Ubicación de datos de usuario

En modo código fuente, la aplicación crea `data/` y `logs/` dentro del repositorio. En modo compilado, los archivos de usuario se guardan en `%LOCALAPPDATA%\Tecnocity Admin\`, separados de los archivos de instalación. Esto evita perder o mezclar la base de datos al actualizar la aplicación.

Puedes cambiar las rutas mediante estas variables de entorno:

- `TECNOCITY_DATA_DIR`: carpeta de base de datos, configuración y respaldos.
- `TECNOCITY_LOGS_DIR`: carpeta de registros.
- `TECNOCITY_ASSETS_DIR`: carpeta de recursos visuales.

No incluyas carpetas de datos, registros o credenciales en el paquete público.

## 4. Prueba en una máquina limpia

Antes de publicar una versión compilada:

1. Copia la carpeta `dist/TecnocityAdmin` a un equipo Windows donde no exista Python.
2. Ejecuta `TecnocityAdmin.exe` y verifica que abre la ventana principal.
3. Comprueba que se crea la carpeta `%LOCALAPPDATA%\Tecnocity Admin`.
4. Registra un producto y una compra de prueba; cierra y vuelve a abrir la aplicación para confirmar persistencia.
5. Revisa Dashboard, reportes Excel/CSV/PDF e impresión.
6. Prueba un respaldo local y su restauración con una base de datos desechable.
7. Si se configura Google Drive, utiliza credenciales de prueba propias y verifica que no se copien al directorio de distribución.

## 5. Archivos de distribución y firma

- No publiques `build/`, `dist/`, `.venv-build/`, bases de datos ni configuraciones privadas en el repositorio fuente.
- Si distribuyes la aplicación a terceros, incluye los avisos de licencia aplicables y cumple las obligaciones de Qt/PySide6 indicadas en [Licencias de terceros](THIRD_PARTY_LICENSES.md).
- La firma de código y un instalador MSI/EXE firmado son pasos de distribución independientes; esta configuración no genera firma ni instalador.
- Para publicar un artefacto compilado, crea una GitHub Release y adjunta el paquete completo generado, acompañado de los avisos de licencias de esa versión.

## 6. Limitación de esta entrega

El archivo fuente incluye el `.spec` y el script de compilación, pero no un ejecutable Windows ya compilado. La compilación final debe realizarse y probarse en Windows con las dependencias correspondientes.
