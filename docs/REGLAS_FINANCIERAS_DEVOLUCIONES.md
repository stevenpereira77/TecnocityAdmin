# Reglas financieras para devoluciones y cancelaciones

Este documento resume las reglas que aplica el servicio de devoluciones de Tecnocity Admin v1.10.0.

## 1. Base reembolsable de cada línea

Cada línea conserva su `line_total` original, que ya incluye el descuento específico de esa línea. Las devoluciones parciales se calculan acumulativamente contra ese valor. Los importes anteriores se recuperan del detalle histórico de `SaleReturnItem`; cuando se devuelve la última cantidad pendiente, se reembolsa exactamente el saldo que quede de la línea.

Esta regla evita acumular errores de redondeo al devolver unidades de una misma línea en fechas diferentes.

## 2. Descuento general de la venta

El descuento global se asigna proporcionalmente a la base de productos devuelta acumulada, usando el subtotal original como denominador. El descuento objetivo acumulado se redondea a dos decimales; el descuento de la devolución actual es ese objetivo menos lo ya devuelto. Cuando se devuelve toda la base restante, se asigna el saldo exacto del descuento global.

Por ejemplo, en una venta con dos unidades de $100.000 y descuento global de $20.000, cada unidad debe generar un reembolso de $90.000. Las dos devoluciones suman $180.000, no $185.000.

## 3. Domicilio y utilidad

El domicilio solo se devuelve cuando la operación solicita explícitamente devolverlo, y nunca por encima del cobro original pendiente. La utilidad efectiva resta de la utilidad de la venta el efecto de cada reembolso y el costo FIFO correspondiente a los productos que regresan al inventario.

## 4. Validación antes de mutar el inventario

Antes de reconstruir las capas FIFO se validan las líneas, cantidades agregadas, saldos de productos, descuentos y domicilio. Si el detalle histórico de devoluciones no coincide con los totales guardados, la operación se rechaza para evitar registrar una cifra financiera que no pueda reconciliarse.

## 5. Pruebas de regresión

`tests/test_return_financials.py` cubre:

- Descuento global repartido entre dos devoluciones parciales.
- Redondeo de descuentos de línea en tres devoluciones separadas.
- Repartición de centavos de descuento global.
- Cancelación después de una devolución parcial.
- Solicitudes con líneas duplicadas que exceden la cantidad vendida.
- Cálculo de total y utilidad efectivos desde la fachada pública.

Los registros históricos ya persistidos no se modifican automáticamente: si una versión anterior registró un reembolso incorrecto, debe revisarse contra los comprobantes del negocio antes de cualquier ajuste contable.
