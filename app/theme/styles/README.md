# Arquitectura de temas

Tecnocity Admin usa una única hoja QSS tokenizada (`assets/app.qss`) y una paleta semántica completa por tema (`app/theme/palette.py` + `app/theme/themes.py`).

Para añadir un nuevo tema:

1. Crear otro `ThemeDefinition` con un `ThemePalette` completo en `app/theme/themes.py`.
2. Mantener selectores y medidas comunes en `assets/app.qss`.
3. Definir una serie de colores de gráficos (`chart_series`) con suficiente contraste.
4. Ejecutar la suite de pruebas antes de empaquetar.

Los tamaños de botones, campos, tablas, scrollbars y tarjetas no deben depender del tema. El tema cambia tokens de color, no geometría.
