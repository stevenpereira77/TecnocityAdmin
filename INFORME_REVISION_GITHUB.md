# Informe de revisión para publicación en GitHub

**Proyecto:** Tecnocity Admin v1.10.0  
**Fecha:** 30 de octubre de 2026  
**Objetivo:** preparar el código fuente para un repositorio público con licencia no comercial.

## Resultado general

La copia preparada conserva el código de la aplicación, las pruebas, los recursos visuales y la documentación técnica. Se excluyeron archivos locales y generados que no deben publicarse. Se añadió una guía de instalación/compilación, reglas para contribuciones, seguridad, licencia y automatización básica de CI.

## Revisión del archivo original

El `.rar` contenía aproximadamente 11.161 entradas y cerca de 903 MB de datos al descomprimir. La carpeta `.venv` ocupaba la mayor parte del contenido y reunía alrededor de 11.000 archivos de intérprete, paquetes y cachés. No debe formar parte del repositorio: cada colaborador debe crear su propio entorno desde `requirements.txt`.

Se retiraron de la copia pública:

- `.venv/`, `__pycache__/`, `*.pyc` y cachés de pruebas.
- La base de datos de ejecución `data/tecnocity_admin.db`.
- Preferencias locales `data/config/settings.json`.
- Registros locales de `logs/`.
- Cualquier carpeta de respaldos o archivos OAuth locales.

La base de datos original no contenía registros en las tablas de negocio, pero aun así se excluyó porque es un archivo de ejecución que debe generarse en cada instalación. El programa crea la base y sus carpetas cuando inicia.

## Protección de datos y secretos

- Se reforzó `.gitignore` para bases SQLite, archivos WAL/SHM, preferencias, credenciales OAuth, tokens, respaldos, logs, archivos temporales, entornos virtuales y compilaciones.
- Se inspeccionó el contenido fuente buscando archivos de credenciales y patrones comunes de claves privadas, tokens y API keys. No se encontraron archivos `client_secret.json` o `token.json` ni coincidencias con esos patrones.
- El código conserva las rutas y nombres de archivo que necesita para que cada usuario configure OAuth; eso no equivale a incluir las credenciales.
- Se añadieron recomendaciones para no compartir bases de datos, fotografías privadas, datos de clientes ni respaldos en incidencias públicas.

Esta revisión reduce los riesgos visibles en el archivo de origen, pero no sustituye una auditoría de seguridad ni garantiza que no exista información sensible con formatos no detectados.

## Cambios técnicos para la publicación

1. **Licencia:** se incorporó PolyForm Noncommercial 1.0.0. Permite usos no comerciales dentro de sus términos y no concede permiso comercial automático. Una licencia no comercial no es una licencia Open Source aprobada por OSI.
2. **Gráficos del Dashboard:** se retiró la dependencia de `PySide6.QtCharts` y se crearon widgets propios con `QPainter`, conservando los gráficos de tendencia, dona y barras y su adaptación a los temas.
3. **Datos al compilar:** en modo PyInstaller, la base, configuración, respaldos y logs se guardan en `%LOCALAPPDATA%\Tecnocity Admin\` en Windows, fuera de la carpeta de instalación.
4. **Compilación:** se agregaron `TecnocityAdmin.spec`, `requirements-build.txt`, `tools/build_windows.bat` y `docs/BUILD_WINDOWS.md`.
5. **Mantenimiento:** se añadieron workflows de GitHub Actions para pruebas en Windows con Python 3.11, 3.12 y 3.13 y compilación manual bajo demanda.
6. **Documentación:** se prepararon README, arquitectura revisada, changelog, guía de contribución, seguridad, licencias de terceros y checklist de prepublicación.

## Validaciones realizadas

| Validación | Resultado |
|---|---|
| Análisis sintáctico de archivos Python y `.spec` | 100 archivos procesados sin errores |
| Suite automatizada | **120 passed, 7 skipped** |
| Comprobación de archivos incluidos en un commit simulado | 131 archivos; 0 archivos prohibidos |
| Pruebas de patrones `.gitignore` con archivos centinela | Correcto |
| Archivos SQLite, credenciales, logs y `.pyc` presentes en el paquete final | 0 |
| Búsqueda de imports `PySide6.QtCharts` y `PySide6.QtGraphs` en código de aplicación | Ningún uso; los gráficos se dibujan con `QPainter` |

### Pruebas omitidas

- Seis pruebas de GUI se omitieron porque el entorno de revisión no tenía PySide6 instalado.
- Una prueba de estrés se omitió porque no estaba definida la variable `TECNOCITY_STRESS_DB` y no se proporcionó la base de datos sintética de estrés.

Se intentó instalar las dependencias para validar esas áreas, pero el entorno no pudo resolver el índice de paquetes por falta de acceso de red. Por ello, no se afirma que la interfaz gráfica se haya ejecutado aquí ni que se haya producido un `.exe`.

## Antes de distribuir un ejecutable

- Ejecuta `tools\build_windows.bat` en Windows con Python 3.12.
- Prueba el resultado en un equipo Windows limpio, sin Python instalado.
- Comprueba base de datos, imágenes, reportes, impresión y restauración de respaldos.
- Genera un inventario de licencias para las versiones exactas de las dependencias.
- Revisa los avisos y obligaciones LGPL/GPL de Qt/PySide6. La licencia PolyForm del proyecto no reemplaza las licencias de terceros.
- Si el proyecto contiene código de terceros o trabajo de colaboradores, confirma que tienes autorización para publicarlo bajo PolyForm Noncommercial.

## Recomendación final

El paquete está preparado como **repositorio fuente público con licencia no comercial**, no como software Open Source aprobado por OSI ni como ejecutable ya probado. La publicación en GitHub debe hacerse después de confirmar titularidad/licencia y revisar la pantalla final del primer commit. Los pasos están en [docs/PREPUBLICACION_GITHUB.md](docs/PREPUBLICACION_GITHUB.md).
