# CHANGELOG

## Preparación de publicación de v1.10.0 — 2026-10-30

- Se preparó una distribución de código fuente sin entornos virtuales, cachés, bases de datos de trabajo, preferencias locales ni credenciales OAuth.
- Se incorporó la licencia PolyForm Noncommercial 1.0.0 y documentación sobre sus límites y las licencias de terceros.
- Se reemplazaron los gráficos de Qt Charts por widgets `QPainter` basados en la paleta semántica del Dashboard.
- Se separó el almacenamiento de datos de usuario de la carpeta del ejecutable PyInstaller.
- Se añadió especificación PyInstaller, script de compilación Windows, guía de instalación y pipelines de pruebas/compilación.
- Se reforzaron exclusiones para SQLite, tokens, credenciales, respaldos, logs, entornos virtuales y archivos generados.

## v1.10.0 — Catálogo visual de productos

- Formulario de producto con selección, vista previa, ampliación y eliminación de foto.
- Imágenes optimizadas y miniaturas para mantener las tablas ligeras y proporcionadas.
- Columnas de miniaturas en Productos e Inventario; clic en la foto para ampliarla.
- Creación rápida de un producto con foto desde el módulo Compras, con selección automática para la operación.
- Imágenes almacenadas como BLOB en SQLite: respaldos/restauraciones existentes incluyen las fotos automáticamente.
- Migración aditiva para `image_path`, `image_thumbnail_data` e `image_data`, sin alterar registros existentes.
- Pruebas de regresión para persistencia, eliminación, tamaño máximo, migración, consulta diferida y respaldos.

## v1.9.0 — Escalabilidad y rendimiento

- Dashboard convertido a agregaciones SQL: no materializa todo el histórico de ventas, devoluciones y gastos en memoria.
- Carga diferida de páginas: el shell arranca sin construir módulos ocultos.
- Navegación con refresh dirigido; `refresh_all()` solo toca módulos ya cargados.
- Productos e Inventario con paginación y consultas acotadas.
- Inventario sin N+1 para el valor FIFO y movimientos con límite seguro.
- SQLite configurado con WAL, `busy_timeout`, `foreign_keys`, caché temporal y `synchronous=NORMAL`.
- Índices compuestos para fechas, devoluciones, líneas de venta, inventario, movimientos y auditoría.
- Pruebas y benchmark de escalabilidad añadidos.

## v1.8.1 — Sistema visual coherente y resistente a cambios de tema

- Unificada la apariencia en un QSS tokenizado con paleta semántica.
- Modos claro, oscuro y futurista morado comparten medidas y componentes, evitando deformaciones al cambiar de tema.
- El Dashboard aplica colores dinámicos a fondos, ejes, leyendas, líneas, barras y gráficos circulares.
- El tema se aplica a toda la QApplication y a su QPalette para evitar controles nativos con colores heredados.

## v1.7.0 — Configuración, backups y Google Drive

- Nuevo centro de configuración profesional y extensible, separado de la lógica de negocio.
- Persistencia de preferencias en `data/config/settings.json` con valores predeterminados y escritura atómica.
- Nuevo `BackupManager` para snapshots SQLite consistentes mediante la API de backup de SQLite.
- Verificación de integridad local mediante `PRAGMA integrity_check`.
- Historial persistente de ejecuciones de respaldo fuera de la base operativa.
- Integración Google Drive mediante OAuth 2.0 con cuenta seleccionable desde la interfaz.
- Carpeta de respaldos creada/gestionada automáticamente y correo adicional compartido en modo lectura.
- Verificación remota por tamaño y MD5 cuando Google Drive devuelve el checksum.
- Restauración desde archivo local o Google Drive con respaldo `PreRestore_...` previo.
- Automatización diaria mediante Windows Task Scheduler y opción de comprobación al iniciar.
- Retención configurable de copias locales.
- Las credenciales OAuth y tokens quedan fuera del repositorio mediante `.gitignore`.


## v1.6.0 — Filtros avanzados de productos

- Búsqueda global del catálogo por ID, SKU, nombre, categoría, marca y descripción.
- Filtros por categoría, marca, estado, stock, ID exacto/rango y precio mínimo/máximo.
- Presets de fecha de registro.
- Ordenamiento ascendente/descendente por ID, SKU, nombre, categoría, marca, precio, stock o fecha.
- Nueva especificación `ProductFilter` separada de Qt para mantener la lógica reusable y escalable.
- `ProductService` ejecuta los filtros en SQLAlchemy, no en la interfaz.
- Se conserva compatibilidad con la fachada `StoreService`.
- Pruebas de regresión para combinaciones de filtros y ordenamiento.

# Changelog

## 1.6.0

### Corrección del rango personalizado del Dashboard
- Evitada la excepción no controlada cuando la fecha inicial supera temporalmente la fecha final.
- Los selectores de fecha personalizado ahora quedan mutuamente limitados para mantener rangos válidos.
- La inicialización del rango personalizado se realiza de forma atómica para evitar refrescos intermedios.
- `refresh()` maneja únicamente `ValueError` de rango y muestra la validación en el propio Dashboard, sin ocultar otras excepciones.
- Añadidas pruebas de regresión para la validación del rango personalizado.


## 1.5.1

### Corrección visual del Dashboard
- Corregido el descuadre entre los paneles “Productos más rentables” y “Alertas y operación”.
- El bloque inferior del Dashboard ahora usa dos paneles simétricos y adaptables al ancho disponible.
- Se mantienen las tablas, métricas y datos existentes sin cambios funcionales.

## 1.5.0

### Centro de reportes profesional
- Nuevo centro de reportes profesional con 8 reportes operativos/financieros.
- Vista previa con búsqueda, ordenamiento y filtros por período.
- Exportación Excel con formato profesional mediante openpyxl.
- Exportación CSV UTF-8 con BOM.
- Generación PDF multipágina mediante reportlab.
- Impresión nativa mediante Qt Print Support.
- Exportaciones separadas del dominio y de PySide6 para facilitar mantenimiento y crecimiento.
- Los reportes distinguen devoluciones comerciales de restituciones internas generadas por cancelaciones.

## 1.4.0 - Dashboard ejecutivo

- Dashboard con filtros Hoy, este mes, 7/30/90 días, año, mes anterior, historial y rango personalizado.
- KPIs de ventas, utilidad, gastos, margen, ticket promedio, operaciones, inventario y productos activos.
- Comparación automática contra período anterior.
- Gráfico de tendencia de ventas, utilidad y gastos.
- Gráfico de ventas por método de pago.
- Gráfico de productos más vendidos y tabla de productos más rentables.
- Gráfico de gastos por categoría.
- Alertas de stock bajo y agotados.
- Dashboard envuelto en scroll para resoluciones menores y pantallas de altura limitada.
- Pruebas de contrato del dashboard y regresión de reporting.

## 1.3.0

### Arquitectura
- Separado el antiguo `StoreService` monolítico en `ProductService`, `InventoryService`, `PurchaseService`, `SaleService`, `ReturnService`, `ExpenseService` y `ReportingService`.
- `StoreService` queda como fachada de compatibilidad para no romper la GUI ni llamadas existentes.
- Centralizados auditoría, sesiones y numeración documental en `BaseService`.
- Constantes de negocio de ventas/domicilios movidas a `services/constants.py`.
- Añadidas pruebas de regresión para la composición de servicios.

### Integridad
- Corregida la acumulación del COGS de devoluciones cuando una devolución contiene varias líneas.

## 1.2.3

### Interfaz de Ventas
- Bloque "Pago, descuento y domicilio" rediseñado en cuadrícula de dos columnas (etiqueta sobre campo): los campos ya no se aplastan ni se solapan.
- Las páginas Compras/Ventas van dentro de un área con scroll; funciona bien en pantallas de poca altura.
- Tablas del carrito e historial se ajustan al contenido (ya no se cortan "Total original" ni "Ganancia actual").
- Los campos de domicilio se habilitan según quién paga (Tecnocity / cliente en la venta / cliente al domiciliario) y hay un texto de ayuda que explica el efecto en total y ganancia.
- Si el cliente paga directo al domiciliario, el costo real queda en 0 y deshabilitado (no es gasto de Tecnocity).
- Los errores de validación (por ejemplo descuento mayor al subtotal) se muestran en línea en vez de dejar el total en 0 sin explicación.

### Corrección
- El cobro del domicilio copiaba solo el primer dígito del costo al escribirlo (12000 quedaba en 1). Ahora sigue al costo hasta que el usuario lo edite manualmente.

## v1.9.0 — Apariencia configurable

- Nuevo módulo `app/theme` con registro extensible de temas.
- Modos visuales: claro, oscuro y futurista morado.
- Selección y persistencia del tema desde Configuración, sin tocar código.
- Aplicación inmediata del tema a toda la ventana.
- QSS de cada tema aislado para facilitar mantenimiento y nuevas apariencias.
- Configuración de apariencia persistida junto con el resto de preferencias.
