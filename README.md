# Agente IA para gestión de proyectos

Aplicación de referencia con Python, Streamlit, Microsoft SQL Server y API de OpenAI. Está diseñada para consultar estado y riesgos usando herramientas predefinidas de solo lectura; el modelo **no genera ni ejecuta SQL libre**.

## Requisitos

- Python 3.11 o superior.
- Microsoft SQL Server accesible desde el equipo donde se ejecuta Streamlit.
- Una API key de OpenAI con acceso al modelo configurado.
- Esquema de base de datos existente compatible con el esquema de referencia siguiente, o adaptación de `src/risk_engine.py`.

## Estructura

```text
agente_gestion_proyectos/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── src/
    ├── __init__.py
    ├── config.py
    ├── database.py
    ├── risk_engine.py
    └── agent.py
```

## Esquema esperado

La implementación de ejemplo asume estas tablas y nombres:

```sql
CREATE TABLE proyectos (
    id BIGINT PRIMARY KEY,
    nombre TEXT NOT NULL,
    estado TEXT NOT NULL,
    fecha_inicio DATE,
    fecha_fin_planificada DATE
);

CREATE TABLE tareas (
    id BIGINT PRIMARY KEY,
    proyecto_id BIGINT NOT NULL REFERENCES proyectos(id),
    nombre TEXT NOT NULL,
    estado TEXT NOT NULL,
    porcentaje_avance NUMERIC(5,2) NOT NULL DEFAULT 0,
    fecha_limite DATE,
    fecha_actualizacion TIMESTAMP
);
```

**No ejecutes este DDL si ya tienes tablas existentes.** Compara los nombres y tipos con tu esquema real y adapta las consultas en `src/risk_engine.py`. Si el estado de tus tareas utiliza otros valores, actualiza los filtros que excluyen tareas completadas/canceladas.

## Instalación local

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Abre `.env` y define `DATABASE_URL`, `OPENAI_API_KEY` y, si corresponde, `OPENAI_MODEL`.

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

### Ejecutar

Desde la carpeta del proyecto:

```bash
streamlit run app.py
```

Streamlit mostrará una URL local, normalmente `http://localhost:8501`.

## Seguridad antes de usar datos reales

1. **Usuario Microsoft SQL Server de solo lectura.** No conectes la aplicación con el usuario propietario ni con un superusuario. Como ejemplo, un administrador de base de datos puede ejecutar (ajusta base, esquema y rol):

   ```sql
   CREATE ROLE agente_lectura LOGIN PASSWORD 'usa-un-secreto-largo';
   GRANT CONNECT ON DATABASE gestion_proyectos TO agente_lectura;
   GRANT USAGE ON SCHEMA public TO agente_lectura;
   GRANT SELECT ON TABLE public.proyectos, public.tareas TO agente_lectura;
   ```

   Si las tablas están en otro esquema, ajusta los permisos. La política de permisos debe revisarse para impedir accesos a tablas no autorizadas.

2. Mantén `.env` fuera del control de versiones y nunca subas la clave de OpenAI a Git.
3. Usa TLS para conexiones remotas a Microsoft SQL Server y restringe el acceso de red.
4. Limita el acceso a Streamlit detrás de autenticación/proxy cuando se despliegue para un equipo. Esta demo no incorpora autenticación de usuarios ni autorización por proyecto.
5. Revisa si los datos de proyectos pueden enviarse a un proveedor externo. Minimiza los datos compartidos con el LLM y cumple las políticas de tu organización.
6. Las consultas son de solo lectura y están definidas en código. No añadas una herramienta que ejecute directamente texto SQL generado por el modelo.
7. Los errores técnicos se ocultan por defecto en la interfaz. Activa el modo de desarrollo solo localmente.
8. Configura límites de uso/costos en la cuenta de API y supervisa registros y errores.

## Cómo detecta riesgos

- Tarea atrasada: no está completada/cancelada y su `fecha_limite` es anterior al día actual.
- Información desactualizada: tarea activa sin fecha de actualización o sin cambios durante `STALE_DAYS` días.
- Riesgo alto de proyecto: existe al menos una tarea atrasada o la fecha planificada de fin ya pasó y el proyecto no está marcado como terminado/cancelado.

Estas son reglas iniciales, no un modelo predictivo. Deben ajustarse a la metodología de gestión, calendario laboral, dependencias, criticidad y tolerancia de riesgo de tu organización.

## Solución de problemas

- **Error de conexión:** revisa host, puerto, nombre de base de datos, credenciales, SSL y permisos.
- **No existe la relación:** las tablas o el esquema tienen nombres diferentes; adapta las consultas de `src/risk_engine.py`.
- **Error de API:** comprueba la clave, el acceso al modelo y los límites de la cuenta.
- **Fechas/estados no coinciden:** normaliza los valores de estado en las consultas SQL.

## Límites conocidos de esta versión

- El esquema se considera conocido y fijo; no descubre automáticamente las tablas.
- No modifica proyectos ni tareas.
- No reemplaza el juicio del jefe de proyecto; presenta alertas basadas en reglas.
- La app no incluye autenticación multiusuario ni separación de datos por equipo.
- Debes probar las consultas contra una copia de desarrollo antes de usarla en producción.
