@echo off
setlocal
cd /d "%~dp0.."

where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: No se encontro el lanzador de Python (py).
    echo Instala Python 3.12 y vuelve a intentarlo.
    exit /b 1
)

if not exist ".venv-build\Scripts\python.exe" (
    py -3.12 -m venv .venv-build
    if errorlevel 1 goto :error
)

call ".venv-build\Scripts\activate.bat"
if errorlevel 1 goto :error

python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements-build.txt
if errorlevel 1 goto :error
python -m PyInstaller --noconfirm --clean TecnocityAdmin.spec
if errorlevel 1 goto :error

echo.
echo Compilacion terminada.
echo Ejecutable: dist\TecnocityAdmin\TecnocityAdmin.exe
echo Distribuye la carpeta completa dist\TecnocityAdmin, no solo el .exe.
exit /b 0

:error
echo.
echo ERROR: la compilacion fallo. Revisa el mensaje anterior.
exit /b 1
