# Guía para contribuir

Gracias por tu interés en mejorar Tecnocity Admin. Antes de proponer cambios:

1. Revisa `README.md`, `ARCHITECTURE.md` y la documentación del módulo que modificarás.
2. Trabaja con Python 3.11, 3.12 o 3.13.
3. Crea un entorno virtual e instala `requirements-dev.txt`.
4. Mantén las reglas de negocio dentro de `app/services/` y evita trasladarlas a widgets o vistas.
5. Usa `Decimal` para cálculos monetarios. No sustituyas cálculos financieros por `float`.
6. Agrega o actualiza pruebas para cada corrección o funcionalidad.
7. Ejecuta `python -m compileall -q app tests tools run.py` y `python -m pytest -q` antes de enviar cambios.
8. No agregues bases de datos de usuarios, fotografías privadas, tokens, credenciales OAuth, logs ni respaldos.

Las contribuciones se publican bajo los términos de `LICENSE`. La licencia no concede permisos comerciales. Antes de enviar código, confirma que tienes derecho a compartirlo y que no estás copiando material incompatible de terceros.

Para cambios visuales, conserva la paleta semántica centralizada y prueba los temas claro, oscuro y futurista. Para cambios financieros, documenta la regla y añade casos de prueba de bordes.
