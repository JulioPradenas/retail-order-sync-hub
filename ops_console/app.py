"""Panel de control local del Retail Order Sync Hub.

Un tablero para levantar/bajar el stack, ver el estado de cada contenedor y
abrir los dashboards sin tocar la terminal. Pensado para demos de portfolio.

    uv run --group console streamlit run ops_console/app.py
    # o: make console

Corre LOCAL: ejecuta `make`/`docker` en tu máquina. No exponer públicamente.
"""

from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]

# (etiqueta, fragmento del nombre de contenedor) — el stack y la observabilidad.
SERVICES = [
    ("Odoo (ERP)", "odoo-1"),
    ("Postgres app", "app_db"),
    ("Pub/Sub emulator", "pubsub-emulator"),
    ("OTel collector", "otel-collector"),
    ("Webhook receiver", "webhook_receiver"),
    ("paris-mock", "paris_mock"),
    ("Outbox worker", "outbox_worker"),
    ("Subscriber", "subscriber"),
    ("Reconciler", "reconciler"),
    ("Grafana", "obs-grafana"),
    ("Prometheus", "obs-prometheus"),
    ("Tempo", "obs-tempo"),
]

LINKS = [
    ("Grafana", "http://localhost:3000", "Dashboards Comex Ops + Pipeline Health"),
    ("Prometheus", "http://localhost:9090", "Métricas y targets"),
    ("Tempo", "http://localhost:3200", "Trazas distribuidas"),
    ("Odoo", "http://localhost:8069", "ERP (admin/admin)"),
    ("Webhook health", "http://localhost:8000/health", "Receiver"),
    ("paris-mock", "http://localhost:9100/orders", "Marketplace mock"),
]

HEALTH = [
    ("Webhook receiver", "http://localhost:8000/health"),
    ("Grafana", "http://localhost:3000/api/health"),
    ("Prometheus", "http://localhost:9090/-/ready"),
]


def running_containers() -> set[str]:
    """Nombres de contenedores docker en ejecución."""
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def is_up(fragment: str, names: set[str]) -> bool:
    return any(fragment in name for name in names)


def run_make(target: str) -> tuple[bool, str]:
    """Corre un target del Makefile y devuelve (ok, salida combinada)."""
    try:
        result = subprocess.run(
            ["make", target],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return result.returncode == 0, (result.stdout + result.stderr)[-4000:]


def health(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def action_button(label: str, target: str, *, help_text: str) -> None:
    if st.button(label, help=help_text, use_container_width=True):
        with st.spinner(f"make {target}…"):
            ok, output = run_make(target)
        if ok:
            st.success(f"make {target} OK")
        else:
            st.error(f"make {target} falló")
        if output.strip():
            st.code(output, language="bash")


st.set_page_config(page_title="ROSH — Panel de control", page_icon="🛒", layout="wide")
st.title("Retail Order Sync Hub — Panel de control")
st.caption("Levanta el stack, mira el estado y abre los dashboards sin usar la terminal.")

names = running_containers()
total_up = sum(is_up(frag, names) for _, frag in SERVICES)
st.metric("Servicios arriba", f"{total_up} / {len(SERVICES)}")

col_state, col_actions = st.columns([1, 1])

with col_state:
    st.subheader("Estado de servicios")
    if st.button("Refrescar estado", use_container_width=True):
        st.rerun()
    for label, fragment in SERVICES:
        badge = ":green[● arriba]" if is_up(fragment, names) else ":red[○ abajo]"
        st.write(f"{badge}  {label}")

with col_actions:
    st.subheader("Acciones")
    st.markdown("**Stack operacional**")
    action_button("Levantar stack (make up)", "up", help_text="Odoo, Postgres, Pub/Sub, workers")
    action_button("Migrar BD (make migrate)", "migrate", help_text="Alembic upgrade head")
    action_button("Seed Odoo (make seed)", "seed", help_text="Órdenes demo reproducibles")
    action_button("Generar DLQ demo (make chaos)", "chaos", help_text="10 entradas en el DLQ")
    action_button(
        "Generar sync outcomes (make sync-demo)",
        "sync-demo",
        help_text="Encola órdenes que el worker falla → retry/dlq en vivo en Grafana",
    )

    st.markdown("**Observabilidad**")
    action_button(
        "Levantar observabilidad (make obs-up)", "obs-up", help_text="Grafana + Prometheus + Tempo"
    )
    action_button(
        "Generar tráfico de webhooks (make webhook-demo)",
        "webhook-demo",
        help_text="40 webhooks en vivo para poblar los paneles de Grafana",
    )
    action_button(
        "Bajar observabilidad (make obs-down)", "obs-down", help_text="Detiene observabilidad"
    )

    st.markdown("**Apagado**")
    action_button("Bajar stack (make down)", "down", help_text="Detiene el stack operacional")

st.divider()
st.subheader("Accesos rápidos")
link_cols = st.columns(3)
for i, (label, url, desc) in enumerate(LINKS):
    with link_cols[i % 3]:
        st.link_button(label, url, use_container_width=True, help=desc)

st.divider()
st.subheader("Health checks")
if st.button("Verificar salud"):
    for label, url in HEALTH:
        ok = health(url)
        st.write(f"{':green[OK]' if ok else ':red[sin respuesta]'}  {label} — `{url}`")
