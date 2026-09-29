# Tabla maestra de cuotas

La aplicación lee `master_odds.csv` en esta carpeta. Cada fila debe representar una captura de un mercado en una ejecución; no se deben sobrescribir capturas anteriores.

Columnas esperadas: timestamp_consulta, run_id, sport, competition, season, fecha_partido, local, visitante, mercado, probabilidad_modelo, cuota_teorica, casa_apuestas, cuota_real, edge, es_alerta, resultado_real.

El proyecto inicial no contenía un histórico completo de cuotas por mercado: solo `data/historical/alertas_enviadas.csv`, que guarda alertas enviadas. La aplicación presenta esa bitácora como respaldo, claramente identificada, pero no la confunde con la tabla maestra completa. Para medir evolución y CLV se deben persistir snapshots de todas las cuotas en cada ejecución.
