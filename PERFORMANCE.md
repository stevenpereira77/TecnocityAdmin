# Rendimiento Tecnocity Admin v1.9.0

## Problema observado

Las versiones anteriores materializaban el histórico completo de ventas, devoluciones y gastos para calcular el Dashboard. Además, `MainWindow` construía todas las páginas al iniciar y refrescaba módulos ocultos al navegar.

## Solución

1. Dashboard con agregaciones SQL y subconsultas de devoluciones/FIFO.
2. Carga diferida (`LazyPageHost`) para páginas secundarias.
3. Navegación con refresh dirigido y compatibilidad de `refresh_all()` sin instanciar módulos ocultos.
4. Productos e Inventario paginados.
5. Inventario sin N+1 al calcular el valor FIFO.
6. Movimientos acotados por límite.
7. SQLite con WAL, `busy_timeout`, claves foráneas, caché temporal y `PRAGMA optimize`.
8. Índices compuestos centralizados en `app/database/indexes.py`.

## Referencia de laboratorio

Con una base sintética de aproximadamente 100.000 productos, 150.000 ventas, 345.829 líneas de venta y 300.000 gastos:

- Dashboard mes: ~0,5 s.
- Dashboard 30 días: ~0,4 s.
- Dashboard histórico: ~3,2 s.
- Productos primera página: ~0,03 s.
- Inventario primera página: ~0,24 s.
- Movimientos recientes (100): ~0,01 s.

Los tiempos dependen del hardware, almacenamiento y estado de la caché de SQLite. El script `tools/benchmark_performance.py` permite repetir la medición.
