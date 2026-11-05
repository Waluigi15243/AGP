from __future__ import annotations

import pandas as pd
import streamlit as st

from src.agent import ProjectAgent
from src.database import get_engine, test_connection
from src.risk_engine import get_project_overview, analyze_risks

st.set_page_config(page_title="Agente de Gestión de Proyectos", page_icon="📊", layout="wide")

st.title("📊 Agente de IA para Gestión de Proyectos")
st.caption("Consulta el estado de los proyectos y analiza riesgos utilizando datos de PostgreSQL.")

with st.sidebar:
    st.header("Conexión")
    st.write("La conexión se configura mediante variables de entorno en `.env`.")
    if st.button("Probar conexión a BD", use_container_width=True):
        try:
            test_connection(get_engine())
            st.success("Conexión correcta.")
        except Exception as exc:
            st.error("No fue posible conectar. Revisa DATABASE_URL y los permisos de la base de datos.")
            st.exception(exc if st.session_state.get("debug", False) else RuntimeError("Detalle oculto por seguridad."))
    st.checkbox("Mostrar errores técnicos (desarrollo)", key="debug", value=False)
    st.divider()
    st.markdown("**Herramientas disponibles**")
    st.markdown("- Resumen de proyectos\n- Análisis de tareas atrasadas\n- Detección de información desactualizada\n- Chat con el agente")

try:
    engine = get_engine()
    overview = get_project_overview(engine)
    risks = analyze_risks(engine)
except Exception as exc:
    st.error("No se pudo cargar información desde Microsoft SQL Server. Verifica la configuración y que el esquema coincida con README.md.")
    if st.session_state.get("debug", False):
        st.exception(exc)
    st.stop()

total_projects = len(overview)
at_risk = int(overview["riesgo_alto"].sum()) if not overview.empty else 0
avg_progress = float(overview["avance_promedio"].mean()) if not overview.empty else 0.0
overdue_count = int(risks["atrasadas"].sum()) if not risks.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Proyectos", total_projects)
c2.metric("Proyectos con riesgo alto", at_risk)
c3.metric("Avance promedio", f"{avg_progress:.1f}%")
c4.metric("Tareas atrasadas", overdue_count)

tab1, tab2, tab3 = st.tabs(["Resumen", "Riesgos", "Agente IA"])

with tab1:
    st.subheader("Estado de los proyectos")
    if overview.empty:
        st.info("No hay proyectos para mostrar.")
    else:
        display = overview.copy()
        display["avance_promedio"] = display["avance_promedio"].map(lambda x: f"{x:.1f}%")
        st.dataframe(display, use_container_width=True, hide_index=True)
        if "nombre" in overview.columns and "avance_promedio" in overview.columns:
            chart_df = overview[["nombre", "avance_promedio"]].set_index("nombre")
            st.bar_chart(chart_df)

with tab2:
    st.subheader("Hallazgos de riesgo")
    if risks.empty:
        st.success("No se detectaron tareas atrasadas ni tareas con actualización antigua.")
    else:
        filter_choice = st.selectbox("Filtrar por tipo", ["Todos", "Tarea atrasada", "Sin actualización reciente"])
        filtered = risks.copy()
        if filter_choice == "Tarea atrasada":
            filtered = filtered[filtered["atrasadas"] == 1]
        elif filter_choice == "Sin actualización reciente":
            filtered = filtered[filtered["desactualizadas"] == 1]
        st.dataframe(filtered, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Pregunta al agente")
    st.caption("Ejemplos: «¿Qué proyectos necesitan atención prioritaria?», «Resume los riesgos» o «¿Qué tareas están atrasadas?»")
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hola. Puedo consultar el resumen de proyectos y analizar riesgos a partir de los datos disponibles en PostgreSQL. ¿Qué necesitas revisar?"}
        ]
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Escribe una pregunta sobre tus proyectos…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Analizando datos…"):
                try:
                    agent = ProjectAgent(engine)
                    answer = agent.ask(st.session_state.messages[-12:])
                    st.markdown(answer)
                except Exception:
                    answer = "No pude completar el análisis. Comprueba la configuración de OPENAI_API_KEY, el acceso a Microsoft SQL Server y los registros de la aplicación."
                    st.error(answer)
                    if st.session_state.get("debug", False):
                        st.exception(Exception("Consulta al agente fallida; revisa la salida de la terminal para el detalle."))
        st.session_state.messages.append({"role": "assistant", "content": answer})
