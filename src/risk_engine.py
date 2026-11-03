from __future__ import annotations

from datetime import date
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from src.config import STALE_DAYS

# Esquema de referencia documentado en README.md:
# proyectos(id, nombre, estado, fecha_inicio, fecha_fin_planificada)
# tareas(id, proyecto_id, nombre, estado, porcentaje_avance, fecha_limite, fecha_actualizacion)
# Ajusta los nombres de tabla/columna si tu esquema existente es diferente.

OVERVIEW_SQL = text("""
SELECT
    p.id,
    p.nombre,
    p.estado,
    p.fecha_inicio,
    p.fecha_fin_planificada,
    COUNT(t.id) AS total_tareas,
    COALESCE(ROUND(AVG(t.porcentaje_avance)::numeric, 1), 0) AS avance_promedio,
    SUM(CASE WHEN t.id IS NOT NULL
              AND t.estado NOT IN ('completada', 'cancelada')
              AND t.fecha_limite < CURRENT_DATE THEN 1 ELSE 0 END) AS tareas_atrasadas,
    CASE
      WHEN SUM(CASE WHEN t.id IS NOT NULL
                     AND t.estado NOT IN ('completada', 'cancelada')
                     AND t.fecha_limite < CURRENT_DATE THEN 1 ELSE 0 END) > 0
        OR (p.fecha_fin_planificada < CURRENT_DATE AND LOWER(COALESCE(p.estado, '')) NOT IN ('completado', 'completada', 'cancelado', 'cancelada'))
      THEN TRUE ELSE FALSE
    END AS riesgo_alto
FROM proyectos p
LEFT JOIN tareas t ON t.proyecto_id = p.id
GROUP BY p.id, p.nombre, p.estado, p.fecha_inicio, p.fecha_fin_planificada
ORDER BY p.fecha_fin_planificada NULLS LAST, p.nombre
""")

RISKS_SQL = text("""
SELECT
    p.nombre AS proyecto,
    t.id AS tarea_id,
    t.nombre AS tarea,
    t.estado,
    t.porcentaje_avance,
    t.fecha_limite,
    t.fecha_actualizacion,
    CASE WHEN t.estado NOT IN ('completada', 'cancelada')
              AND t.fecha_limite < CURRENT_DATE THEN 1 ELSE 0 END AS atrasadas,
    CASE WHEN t.estado NOT IN ('completada', 'cancelada')
              AND (t.fecha_actualizacion IS NULL
                   OR t.fecha_actualizacion < CURRENT_DATE - (:stale_days * INTERVAL '1 day'))
         THEN 1 ELSE 0 END AS desactualizadas
FROM tareas t
JOIN proyectos p ON p.id = t.proyecto_id
WHERE LOWER(COALESCE(t.estado, '')) NOT IN ('completada', 'completado', 'cancelada', 'cancelado')
  AND (
      t.fecha_limite < CURRENT_DATE
      OR t.fecha_actualizacion IS NULL
      OR t.fecha_actualizacion < CURRENT_DATE - (:stale_days * INTERVAL '1 day')
  )
ORDER BY atrasadas DESC, desactualizadas DESC, t.fecha_limite NULLS LAST
LIMIT 500
""")

def get_project_overview(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(OVERVIEW_SQL, conn)

def analyze_risks(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(RISKS_SQL, conn, params={"stale_days": STALE_DAYS})

def list_projects(engine: Engine, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    query = text("""
        SELECT id, nombre, estado, fecha_inicio, fecha_fin_planificada
        FROM proyectos
        ORDER BY fecha_fin_planificada NULLS LAST, nombre
        LIMIT :limit
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()
    return [dict(row) for row in rows]

def get_risk_summary(engine: Engine) -> dict:
    overview = get_project_overview(engine)
    risks = analyze_risks(engine)
    return {
        "total_proyectos": int(len(overview)),
        "proyectos_riesgo_alto": int(overview["riesgo_alto"].sum()) if not overview.empty else 0,
        "avance_promedio": round(float(overview["avance_promedio"].mean()), 1) if not overview.empty else 0,
        "tareas_atrasadas": int(risks["atrasadas"].sum()) if not risks.empty else 0,
        "tareas_desactualizadas": int(risks["desactualizadas"].sum()) if not risks.empty else 0,
        "riesgos": risks.head(100).where(pd.notnull(risks.head(100)), None).to_dict(orient="records"),
    }
