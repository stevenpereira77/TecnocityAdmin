# Dependencias y licencias de terceros

La licencia PolyForm Noncommercial de este proyecto solo cubre el código para el que el titular tiene derechos de autor. No reemplaza ni modifica las licencias de Python, Qt/PySide6, ni de las dependencias de terceros.

## Dependencias directas declaradas

| Paquete | Uso principal | Licencia upstream habitual* |
|---|---|---|
| PySide6 / Qt for Python | Interfaz de escritorio y Qt Print Support | LGPLv3/GPLv3 o licencia comercial de Qt, según módulos y distribución |
| SQLAlchemy | ORM y acceso a SQLite | MIT |
| openpyxl | Exportación Excel | MIT |
| ReportLab | Exportación PDF | BSD (ReportLab) |
| google-api-python-client | API de Google Drive | Apache-2.0 |
| google-auth-oauthlib | OAuth para Google Drive | Apache-2.0 |
| google-auth-httplib2 | Transporte/autenticación Google | Apache-2.0 |
| pytest | Pruebas | MIT |
| PyInstaller | Empaquetado de ejecutables | GPL con excepción para aplicaciones empaquetadas; revisa el texto de la versión utilizada |

*La licencia y avisos exactos deben verificarse para las versiones resueltas en cada compilación, incluidas las dependencias transitivas. Esta tabla es una orientación inicial, no un dictamen legal.

## Qt Charts fue retirado del Dashboard

La versión original utilizaba `PySide6.QtCharts`. Ese módulo tiene condiciones de licencia distintas (GPLv3 o comercial en la documentación de Qt) y Qt lo marca como obsoleto desde Qt 6.10. Para esta publicación se sustituyeron sus gráficos por widgets internos dibujados con `QPainter` en `app/widgets/dashboard_charts.py`. El proyecto no importa `PySide6.QtCharts` ni `PySide6.QtGraphs`.

Esto **no elimina** las obligaciones de licencia de PySide6/Qt base. La comunidad de Qt for Python se distribuye con licencias LGPLv3/GPLv3; existen condiciones comerciales separadas. Antes de redistribuir un ejecutable, revisa la licencia aplicable a la versión instalada y el uso que harás de Qt.

## Obligaciones al distribuir una compilación

Si entregas un ejecutable a terceros:

1. Identifica y conserva los textos de licencia y avisos de copyright de cada componente empaquetado.
2. Cumple las obligaciones LGPL/GPL que correspondan a Qt y sus bibliotecas. No asumas que añadir `LICENSE` del proyecto es suficiente.
3. Cuando corresponda LGPL, facilita la información y los medios requeridos para reemplazar/modificar las bibliotecas cubiertas, y conserva los avisos y el texto de licencia exigidos.
4. No empaquetes módulos GPL-only bajo la suposición de que la licencia no comercial del proyecto reemplaza sus términos.
5. Genera un inventario de dependencias y licencias para la versión exacta del ejecutable.

Una herramienta útil para generar un inventario inicial es `pip-licenses` en el mismo entorno de compilación:

```powershell
python -m pip install pip-licenses
pip-licenses --format=markdown --with-urls --with-description > THIRD_PARTY_NOTICES.generated.md
```

Revisa manualmente el resultado antes de publicarlo: la herramienta informa los metadatos instalados, pero no determina por sí sola todas las obligaciones de redistribución de Qt ni sustituye una revisión legal.

## Enlaces oficiales

- [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)
- [Qt for Python: licencias](https://doc.qt.io/qtforpython-6/licenses.html)
- [Qt: obligaciones LGPL](https://www.qt.io/development/open-source-lgpl-obligations)
- [Qt Charts](https://doc.qt.io/qt-6/qtcharts-index.html)
- [SQLAlchemy: licencia](https://www.sqlalchemy.org/license.html)
- [openpyxl: licencia](https://openpyxl.readthedocs.io/en/stable/) (distribución MIT)
- [ReportLab](https://www.reportlab.com/dev/docs/)
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)
- [PyInstaller: licencia](https://pyinstaller.org/en/stable/license.html)

**Nota:** antes de publicar esta aplicación como producto distribuible, valida con asesoría jurídica que la combinación concreta de licencia del proyecto, Qt/PySide6 y componentes empaquetados satisface tus objetivos de uso no comercial y distribución.
