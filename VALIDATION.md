# Validación Tecnocity Admin v1.10.0

## Suite automática

- En la revisión de preparación para GitHub del 30 de octubre de 2026: **120 pruebas pasan y 7 se omiten** en el entorno de validación.
- Se omiten 6 pruebas de GUI porque PySide6 no está instalado en el entorno de validación. Se omite 1 prueba de estrés porque requiere configurar `TECNOCITY_STRESS_DB`.
- Se ejecutó análisis sintáctico (`compileall`) sobre `app`, `tests`, `tools` y `run.py` sin errores.
- La instalación de las dependencias para ejecutar los tests de GUI y PyInstaller no fue posible en este entorno porque no tuvo acceso al índice de paquetes de Internet. La compilación del ejecutable Windows debe realizarse en Windows siguiendo `docs/BUILD_WINDOWS.md`.
- La prueba de auditoría usa la fecha de ejecución de los registros, no la fecha histórica de la venta; el rango de esa prueba se ajustó para que no falle al cambiar el mes.

## Validación de escalabilidad

Con la base sintética de estrés:

- 100.000 productos.
- 150.000 ventas.
- 345.829 líneas de venta.
- 300.000 gastos.
- 400.000 registros de auditoría.

Resultados medidos en el entorno de validación:

| Operación | Tiempo aproximado |
| --- | ---: |
| Dashboard mes | 0,53 s |
| Dashboard 30 días | 0,51 s |
| Dashboard histórico | 3,62 s |
| Productos primera página | 0,01 s |
| Inventario primera página | 0,32 s |
| Movimientos recientes | 0,01 s |

La implementación anterior del Dashboard fue incapaz de terminar la misma consulta en el benchmark de 300 s; la versión 1.9.0 no materializa el histórico y completa el período mensual en menos de un segundo en este entorno.

## Reglas financieras de devoluciones y cancelaciones

- El descuento global se distribuye acumulativamente sobre la base original devuelta; la suma de devoluciones parciales coincide con el descuento original y el último movimiento absorbe los centavos residuales.
- Los descuentos por línea se concilian contra el importe original de cada línea; no se crean ni se pierden centavos al devolver unidades en operaciones separadas.
- Las devoluciones y cancelaciones pasan por la misma lógica de cálculo.
- Las cantidades duplicadas en una solicitud se agregan antes de validar el saldo disponible, evitando devolver más unidades de las vendidas.
- Las pruebas de regresión cubren importes típicos y una matriz de cinco escenarios con distintos precios, cantidades, descuentos por línea y descuentos globales; el total acumulado devuelto coincide con el importe original en todos ellos.
- `StoreService.effective_sale_values()` delega al servicio de devoluciones, donde vive la regla financiera correspondiente.

## Imágenes de productos v1.10.0

- La imagen completa y su miniatura se guardan en columnas BLOB de `products`; los respaldos SQLite incluyen ambas automáticamente.
- Las consultas de lista difieren la carga de la imagen completa y solo recuperan miniaturas, evitando cargar el archivo de foto completo para todos los productos listados.
- Se valida el formato mediante firma del archivo, se limita la fuente a 20 MB y el resultado optimizado a 2 MB. La interfaz convierte las imágenes seleccionadas a JPEG optimizado y genera miniaturas separadas.
- La migración comprueba la existencia de columnas antes de añadirlas y conserva las filas del catálogo anterior.

## Integridad

- `compileall`: OK.
- Pruebas de catálogo visual: persistencia BLOB, eliminación de foto, límites de tamaño, columnas de migración y contenido del respaldo: OK.
- `PRAGMA integrity_check`: OK durante las pruebas de base de datos.
- `foreign_key_check`: sin errores.
- Índices críticos creados y detectables mediante SQLAlchemy inspector.
