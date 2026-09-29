
## Dashboard Streamlit

Desde la carpeta raíz del proyecto, instala las dependencias y ejecuta:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app/streamlit_app.py
```

El dashboard lee los eventos procesados y la bitácora `data/historical/alertas_enviadas.csv`. Las alertas de Telegram se filtran para enviar únicamente partidos de la fecha actual del sistema. El resumen gerencial semanal se mantiene sin cambios.

Las métricas de rentabilidad del dashboard son simuladas con una unidad por alerta y solo se calculan cuando existe un resultado final que puede cruzarse con la alerta. No equivalen a apuestas realmente ejecutadas.
