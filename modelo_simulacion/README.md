# Modelo de microsimulación: detención del descenso en el segundo periodo

Prototipo de la **Fase 1b** del protocolo «Detención del descenso fetal en los estrechos medio e inferior» (`informes/Protocolo_simulacion_IA_detencion_expulsivo.pdf`). Los resultados preliminares están en `informes/Anexo_resultados_prototipo_simulacion.pdf`.

> **Advertencia.** Es un prototipo ilustrativo. De los 26 parámetros inciertos, 8 provienen de la literatura y 18 son supuestos (marcados como `tipo: supuesto` en `parametros.yaml`). Los supuestos deben calibrarse con la auditoría local antes de usar los resultados para decidir políticas. No sirve para decisiones clínicas individuales.

## Estrategias comparadas
| Clave | Estrategia |
|---|---|
| E1 | Práctica actual: cesárea predominante |
| E2 | Tiempo adecuado de expulsivo y cambios de posición; si no nace → cesárea |
| E3 | E2 + rotación manual de OP/OT |
| E4 | E3 + ventosa/fórceps si es elegible (plano bajo; plano medio solo con competencia ≥ 0.7); si falla → cesárea |

## Archivos
- `parametros.yaml`: valores, distribuciones, tipo (literatura o supuesto) y fuente de cada parámetro; política; pesos del índice de daño (juicio de valor).
- `modelo.py`: el simulador (microsimulación individual con NumPy).
- `analisis.py`: caso base, barrido de competencia, análisis probabilístico, emulador de IA (*gradient boosting*), índices de Sobol, EVPI y análisis de sensibilidad a los pesos.
- `resultados/`: tablas CSV, `resumen.json` y figuras PNG.

## Uso
Instala las dependencias:

```bash
pip install numpy pandas pyyaml matplotlib scikit-learn
```

Corrida completa (≈1 minuto):

```bash
python analisis.py
```

Corrida corta de prueba:

```bash
python analisis.py --rapido
```

Para calibrar con datos del hospital, edita los valores `base` y `dist` en `parametros.yaml`. Empieza por `p_plano_medio`, `p_diag_prematuro` y `p_mala_posicion`, que se obtienen de la auditoría, y vuelve a correr el análisis. La semilla es fija, así que los resultados se pueden reproducir.
