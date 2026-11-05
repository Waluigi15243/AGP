from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL

load_dotenv()


@st.cache_resource
def get_engine() -> Engine:
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    port = os.getenv("DB_PORT", "1433")

    missing = [
        name
        for name, value in {
            "DB_SERVER": server,
            "DB_NAME": database,
            "DB_USERNAME": username,
            "DB_PASSWORD": password,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            f"Faltan variables en .env: {', '.join(missing)}"
        )

    connection_url = URL.create(
        "mssql+pyodbc",
        username=username,
        password=password,
        host=server,
        port=int(port) if port else None,
        database=database,
        query={
            "driver": os.getenv(
                "DB_DRIVER",
                "ODBC Driver 18 for SQL Server",
            ),
            "Encrypt": os.getenv("DB_ENCRYPT", "yes"),
            "TrustServerCertificate": os.getenv(
                "DB_TRUST_SERVER_CERTIFICATE", "no"
            ),
        },
    )

    return create_engine(
        connection_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        pool_timeout=30,
        hide_parameters=True,
        connect_args={"timeout": 15},
    )


def test_connection(engine: Engine) -> dict:
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT
                    @@SERVERNAME AS servidor,
                    DB_NAME() AS base_datos
            """)
        ).mappings().one()

        return dict(result)
        
