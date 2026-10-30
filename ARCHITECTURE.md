# Arquitectura de Tecnocity Admin v1.10.0

```text
GUI (PySide6)
    |
Views / Widgets
    |
StoreService (facade)
    |
+----------------------+----------------------+---------------------+
|                      |                      |                     |
ProductFilterSpec
        |
ProductService   PurchaseService       SaleService      ReturnService
|                |                      |                     |
+----------------+----------------------+---------------------+
                         |
                  InventoryService
                         |
              ReportingService / ExpenseService
                         |
                    ReportService
                         |
              Report definitions + exporters
                         |
            Excel / CSV / PDF / Qt Print
                         |
             Financial Calculations
                         |
                 SQLAlchemy / SQLite
```

## Reglas de dependencias

La interfaz no calcula costos, ganancias ni valoraciones FIFO. La GUI solo recopila/valida entrada superficial y delega la operación al servicio correspondiente. `StoreService` se conserva como fachada de compatibilidad para las vistas existentes.

Las mutaciones que afectan dinero e inventario se ejecutan dentro de una transacción de sesión. Si una parte falla, la transacción se revierte.

## Inventario y FIFO

Cada compra crea una `InventoryLayer`. Una venta consume las capas por fecha/ID y guarda exactamente qué capas se usaron en `SaleLayerAllocation`.

Una devolución no altera retrospectivamente la venta ni su costo original. Crea una nueva capa de inventario con el mismo costo unitario asignado originalmente y registra un movimiento `DEVOLUCION`. Esto permite reconstruir el stock y mantener trazabilidad.

## Ventas y domicilio

La venta separa tres conceptos:

- `shipping_cost`: costo real del domicilio.
- `shipping_charge`: valor de domicilio cobrado al cliente.
- `shipping_payer`: `TIENDA`, `CLIENTE` o `DOMICILIARIO`.

Regla financiera:

```text
Ingreso productos = subtotal - descuento global
Ingreso domicilio = shipping_charge
Ingreso total = ingreso productos + ingreso domicilio

Gasto domicilio = shipping_cost cuando TIENDA o CLIENTE pagan mediante la venta
Gasto domicilio = 0 cuando el cliente paga directamente al domiciliario

Ganancia bruta = ingreso total - COGS
Ganancia neta = ganancia bruta - gasto domicilio - comisión - otros gastos
```

En `DOMICILIARIO`, el costo informado puede conservarse como referencia, pero no se considera ingreso ni gasto de Tecnocity porque el cliente liquida directamente con el domiciliario.

## Devoluciones y cancelaciones

Las ventas nuevas conservan asignaciones FIFO por línea. Las devoluciones parciales/completas:

1. Validan la cantidad pendiente.
2. Restituyen unidades con el costo FIFO original.
3. Registran movimientos de inventario.
4. Crean `SaleReturn` y `SaleReturnItem`.
5. Mantienen los valores financieros originales de la venta.
6. Calculan el impacto económico de la devolución de forma separada.

Una cancelación reutiliza esa misma ruta de compensación para devolver solamente las unidades aún pendientes y cambia el estado a `CANCELADA`.

Los gastos ya incurridos no se borran automáticamente.

## Auditoría

Las operaciones críticas generan `AuditLog`: creación/actualización de productos, compras, ventas, gastos, ajustes de stock, devoluciones, cancelaciones y cambios de entrega.

## Compatibilidad con v1.1

`initialize_database()` realiza migraciones aditivas. No elimina tablas ni datos existentes. Agrega columnas nuevas y las tablas de asignaciones FIFO/devoluciones/auditoría.

Las ventas históricas creadas antes de v1.2 se migran con estado `CONFIRMADA`. Para proteger la integridad, no se permite devolver/cancelar una venta antigua si no existe suficiente información para reconstruir su consumo FIFO exacto.

## Servicios

- `ProductService`: catálogo, búsqueda, edición y estado de productos.
- `InventoryService`: stock, capas FIFO, consumos, devoluciones de inventario, ajustes y movimientos.
- `PurchaseService`: compras y creación de capas FIFO.
- `SaleService`: ventas, previsualización, entrega, consultas de venta y cálculo financiero de la operación.
- `ReturnService`: devoluciones parciales/completas y cancelaciones.
- `ExpenseService`: gastos generales y gastos directos asociados a ventas.
- `ReportingService`: dashboard, históricos, agregaciones, tendencias y auditoría.
- `ReportService`: construye datasets de reportes independientes de Qt.
- `StoreService`: fachada estable; no contiene reglas de negocio ni SQL.

## Directorios

- `app/models`: entidades SQLAlchemy.
- `app/database`: motor, sesiones, creación y migraciones.
- `app/repositories`: base para acceso a datos especializado.
- `app/services`: reglas de negocio y transacciones.
- `app/calculations`: cálculos financieros centralizados.
- `app/controllers`: coordinación futura entre UI y servicios.
- `app/views`: ventanas y composición principal.
- `app/widgets`: pantallas funcionales; `dashboard_charts.py` dibuja gráficos con `QPainter` sin importar Qt Charts.
- `app/reports`: definiciones, generación de datasets y exportadores profesionales.
- `app/utils`: utilidades transversales.
- `tests`: pruebas automatizadas.
- `data`: SQLite local.
- `assets`: estilos y futuros recursos.
- `logs`: registros técnicos.

## Catálogo y filtros avanzados

El catálogo separa la especificación de consulta (`ProductFilter`) de la interfaz Qt.
La GUI construye una especificación tipada y `ProductService` la convierte en filtros y
ordenamiento SQLAlchemy. Esto evita filtrar grandes cantidades de datos en memoria y
permite reutilizar la misma consulta en futuras vistas, reportes o APIs.

Soporta búsqueda por ID/SKU/nombre/categoría/marca/descripción, ID exacto o por rango,
categoría, marca, estado, estado de stock, rango de precio, fecha de registro y
ordenamiento ascendente/descendente por ID, SKU, nombre, categoría, marca, precio,
stock o fecha.


## Configuración y backups v1.7.0

```text
SettingsPage (PySide6)
        |
SettingsStore  <---->  JSON persistente (data/config/settings.json)
        |
        +---- BackupManager
                 |
        +--------+---------+
        |                  |
 Local SQLite        GoogleDriveProvider
 snapshot             OAuth 2.0 / Drive API
        |                  |
 BackupHistory       carpeta + uploads + verificación

WindowsBackupScheduler
        |
Windows Task Scheduler
        |
run.py --backup-now
```

`SettingsStore` mantiene los valores y defaults, mientras `SETTINGS_SECTIONS` funciona como registro de metadatos para añadir futuras secciones sin mezclar preferencias con reglas de negocio. `BackupManager` coordina, pero no contiene detalles de Qt ni de Google OAuth. El proveedor de Google está aislado para permitir añadir otro almacenamiento remoto en el futuro.

El respaldo solo contiene la base SQLite operativa. Los tokens OAuth y credenciales no se incluyen en el respaldo ni deben versionarse.

## Apariencia configurable v1.8.1

La capa visual se mantiene desacoplada de las páginas de configuración mediante `app/theme`:

```text
app/theme/
├── __init__.py
├── manager.py          # aplicación y persistencia del tema
├── palette.py          # tokens semánticos de color
└── themes.py           # definiciones de los temas disponibles
```

`ThemeManager` resuelve el tema guardado y compone la hoja QSS tokenizada en `assets/app.qss` usando los valores de `ThemePalette`. `AppearanceSection` presenta y edita la preferencia; `MainWindow` aplica el stylesheet a nivel de aplicación y notifica a las páginas abiertas. El Dashboard actualiza los colores de sus gráficos mediante `set_palette()`.

## Escalabilidad v1.9.0

La capa de presentación usa `LazyPageHost` para construir cada módulo solo cuando se abre. El `MainWindow` conserva la fachada `refresh_all()` por compatibilidad, pero no crea ni refresca páginas ocultas.

El Dashboard consulta `ReportingService`, que usa agregaciones SQL y subconsultas agrupadas de devoluciones. Las listas grandes no se materializan para obtener métricas.

`app/database/indexes.py` es el único punto para declarar nuevos índices de lectura. `app/database/engine.py` centraliza los pragmas de SQLite.

Productos e Inventario separan consulta paginada de consulta completa para conservar compatibilidad con servicios existentes y evitar llenar `QTableWidget` con decenas de miles de filas.


## Dashboard y gráficos

El Dashboard consulta `ReportingService` para recuperar datos agregados. La presentación se separa en cuatro widgets reutilizables definidos en `app/widgets/dashboard_charts.py`: tendencia, distribución tipo dona y barras horizontales. Se dibujan con `QPainter` y leen sus colores de `ThemePalette`; no dependen de `PySide6.QtCharts` ni de `PySide6.QtGraphs`.

## Ejecución empaquetada

`app/utils/paths.py` identifica la carpeta de recursos del bundle PyInstaller. `AppSettings.load()` mantiene la base de datos, preferencias, respaldos y logs en el directorio de datos del usuario cuando la aplicación está congelada, en lugar de escribir dentro de la carpeta de instalación. El punto de entrada de escritorio es `run.py` y la especificación de distribución Windows está en `TecnocityAdmin.spec`.
