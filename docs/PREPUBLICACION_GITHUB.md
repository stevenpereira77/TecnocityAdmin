# Lista de comprobación antes de publicar en GitHub

## Revisión técnica completada para esta copia

- [x] Se excluyó `.venv/` y los paquetes instalados.
- [x] Se excluyeron `__pycache__/`, `*.pyc`, cachés y archivos temporales.
- [x] Se retiró la base SQLite local del paquete fuente.
- [x] Se retiró `data/config/settings.json` (preferencias locales).
- [x] Se reforzó `.gitignore` para bases SQLite, WAL/SHM, respaldos, informes, logs, tokens y credenciales OAuth.
- [x] Se mantuvo la estructura modular, documentación, pruebas y recursos QSS.
- [x] Se retiró el uso de `PySide6.QtCharts` del Dashboard y se reemplazaron las visualizaciones con widgets `QPainter`.
- [x] Se añadió guía de ejecución, pruebas y compilación Windows.
- [x] Se añadió licencia no comercial y una guía inicial de terceros.
- [x] `compileall` completó sin errores y la suite local pasó con pruebas omitidas por dependencias/condiciones de entorno.

## Antes de pulsar «Publish repository»

- [ ] Confirma que tienes los derechos para licenciar y publicar todos los archivos del proyecto.
- [ ] Sustituye cualquier nombre/identidad de proyecto que no quieras hacer público.
- [ ] Comprueba la pestaña **Security** y activa el reporte privado de vulnerabilidades si está disponible.
- [ ] Configura el repositorio como **Public** solo cuando hayas revisado esta lista.
- [ ] Selecciona `LICENSE` (PolyForm Noncommercial) y no el preset MIT/Apache del asistente de GitHub.
- [ ] No marques «Add a README» ni «Add a license» en GitHub porque estos archivos ya están incluidos.
- [ ] Verifica que el primer commit no incluya `data/`, `.venv/`, `dist/`, `build/`, `*.db`, `client_secret.json` ni `token.json`.
- [ ] Si ya habías hecho commits con credenciales o datos privados, eliminarlos del último commit no basta: rota las credenciales y limpia el historial.
- [ ] Antes de ofrecer un `.exe`, compílalo en Windows, pruébalo en una máquina limpia y publica el inventario/avisos de licencias correspondiente.

## Comandos para publicar por primera vez

Crea un repositorio vacío en GitHub y copia su URL HTTPS. Luego, dentro de la carpeta extraída de este paquete:

```powershell
git init
git add .
git status --short
git diff --cached --stat
git commit -m "Publica Tecnocity Admin v1.10.0"
git branch -M main
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

Reemplaza `USUARIO/REPOSITORIO` por la dirección real de tu repositorio. Antes del `git commit`, revisa `git status` para comprobar que no haya archivos privados.
