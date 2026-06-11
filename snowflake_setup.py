import streamlit as st
import snowflake.connector
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import secrets
import time

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Snowflake Account Setup",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background: #0f1117; }

    /* Top header banner */
    .header-banner {
        background: linear-gradient(135deg, #29b5e8 0%, #1a6fa8 60%, #0d4a7a 100%);
        border-radius: 14px;
        padding: 28px 36px;
        margin-bottom: 28px;
        display: flex;
        align-items: center;
        gap: 18px;
        box-shadow: 0 4px 32px rgba(41,181,232,0.18);
    }
    .header-banner h1 { color: #fff; margin: 0; font-size: 2rem; font-weight: 700; }
    .header-banner p  { color: rgba(255,255,255,0.82); margin: 6px 0 0; font-size: 1rem; }

    /* Step indicator */
    .step-bar {
        display: flex;
        gap: 0;
        margin-bottom: 30px;
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #2a2d3e;
    }
    .step-item {
        flex: 1;
        padding: 12px 8px;
        text-align: center;
        font-size: 0.8rem;
        font-weight: 600;
        background: #1a1d2e;
        color: #6b7280;
        border-right: 1px solid #2a2d3e;
        transition: all 0.2s;
    }
    .step-item:last-child { border-right: none; }
    .step-item.active  { background: #29b5e8; color: #fff; }
    .step-item.done    { background: #1e4a2e; color: #4ade80; }

    /* Cards */
    .card {
        background: #1a1d2e;
        border: 1px solid #2a2d3e;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 18px;
    }
    .card-title {
        font-size: 1rem;
        font-weight: 700;
        color: #29b5e8;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Log output */
    .log-box {
        background: #0d0f1a;
        border: 1px solid #2a2d3e;
        border-radius: 8px;
        padding: 16px;
        font-family: 'Courier New', monospace;
        font-size: 0.82rem;
        max-height: 360px;
        overflow-y: auto;
        line-height: 1.7;
    }
    .log-ok  { color: #4ade80; }
    .log-err { color: #f87171; }
    .log-inf { color: #93c5fd; }
    .log-hdr { color: #fbbf24; font-weight: 700; }

    /* Status badge */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-green  { background: #1e4a2e; color: #4ade80; }
    .badge-blue   { background: #1a3a5c; color: #60a5fa; }
    .badge-yellow { background: #3d2e0a; color: #fbbf24; }

    /* Input overrides */
    .stTextInput input, .stTextInput textarea {
        background: #0d0f1a !important;
        border-color: #2a2d3e !important;
        color: #e2e8f0 !important;
    }
    div[data-testid="stForm"] {
        background: #1a1d2e;
        border: 1px solid #2a2d3e;
        border-radius: 12px;
        padding: 24px;
    }

    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg,#29b5e8,#1a6fa8);
        border: none;
        border-radius: 8px;
        color: #fff;
        font-weight: 600;
        padding: 10px 28px;
        font-size: 0.95rem;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg,#3fc6f5,#1f80c0);
    }

    /* Download button */
    .stDownloadButton > button {
        background: #1e3a2e !important;
        border: 1px solid #4ade80 !important;
        color: #4ade80 !important;
        font-weight: 600;
        border-radius: 8px;
    }

    /* Divider */
    hr { border-color: #2a2d3e; }

    /* Info / warning overrides */
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
st.markdown("""
<div class="header-banner">
    <div style="font-size:2.6rem">❄️</div>
    <div>
        <h1>Snowflake Account Setup Wizard</h1>
        <p>Automate databases, roles, and admin user provisioning for your new Snowflake trial account</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Session state initialisation
# ─────────────────────────────────────────────
defaults = {
    "step": 1,                  # 1=connect  2=configure  3=deploy  4=done
    "conn": None,
    "account": "",
    "username": "",
    "default_dbs_selected": {"DEV": True, "QA": True, "PROD": True},  # checkboxes for default DBs
    "extra_dbs": [],            # additional DB names (without suffix)
    "extra_dbs_schemas": {},    # {db_name: True/False} — whether to create default schemas
    "deploy_logs": [],
    "private_key_pem": None,
    "passphrase": None,
    "deployment_done": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

DEFAULT_DBS     = ["DEV", "QA", "PROD"]
DEFAULT_SCHEMAS = ["RAW", "SILVER", "GOLD"]

SCHEMA_META = {
    "RAW":    {"icon": "🥩", "desc": "Holds raw / ingested data as-is from sources"},
    "SILVER": {"icon": "🧹", "desc": "Cleaned, validated and conformed data"},
    "GOLD":   {"icon": "⭐", "desc": "Business-logic layer — aggregates, metrics, reports"},
}

# ─────────────────────────────────────────────
# Step indicator
# ─────────────────────────────────────────────
STEPS = ["① Connect", "② Configure", "③ Deploy", "④ Download"]
cols = st.columns(len(STEPS))
for i, (col, label) in enumerate(zip(cols, STEPS), start=1):
    status = "active" if i == st.session_state.step else ("done" if i < st.session_state.step else "")
    col.markdown(f'<div class="step-item {status}">{label}</div>', unsafe_allow_html=True)

st.markdown("")  # spacer

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def log(msg: str, kind: str = "inf"):
    st.session_state.deploy_logs.append((msg, kind))


def render_logs():
    lines = []
    for msg, kind in st.session_state.deploy_logs:
        lines.append(f'<span class="log-{kind}">{msg}</span>')
    st.markdown(
        f'<div class="log-box">{"<br>".join(lines)}</div>',
        unsafe_allow_html=True,
    )


def run_sql(cursor, sql: str, label: str, skip_error: bool = False):
    try:
        cursor.execute(sql)
        log(f"✅  {label}", "ok")
        return True
    except Exception as e:
        err = str(e).split("\n")[0]
        if skip_error:
            log(f"⚠️  {label} — skipped ({err})", "inf")
        else:
            log(f"❌  {label} — {err}", "err")
        return False


def generate_key_pair():
    passphrase = secrets.token_urlsafe(32)
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase.encode()),
    )
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # Strip PEM headers — Snowflake ALTER USER needs raw base64
    pub_clean = (
        public_key_pem.decode()
        .replace("-----BEGIN PUBLIC KEY-----", "")
        .replace("-----END PUBLIC KEY-----", "")
        .replace("\n", "")
        .strip()
    )
    return private_key_pem, pub_clean, passphrase


# ─────────────────────────────────────────────
# STEP 1 — Connect
# ─────────────────────────────────────────────
if st.session_state.step == 1:
    st.markdown('<div class="card-title">🔌 Snowflake Connection</div>', unsafe_allow_html=True)
    st.markdown(
        "Enter your Snowflake trial account credentials. "
        "The wizard will connect using the **ACCOUNTADMIN** role.",
    )

    with st.form("connect_form"):
        account = st.text_input(
            "Account Identifier",
            placeholder="e.g. abc12345.us-east-1  or  abc12345",
            help="Found in your Snowflake welcome email or under Admin → Accounts.",
        )
        username = st.text_input("Username", placeholder="e.g. your_email@company.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("🔗 Connect to Snowflake", type="primary", use_container_width=True)

    if submitted:
        if not account or not username or not password:
            st.error("All fields are required.")
        else:
            with st.spinner("Connecting…"):
                try:
                    conn = snowflake.connector.connect(
                        account=account.strip(),
                        user=username.strip(),
                        password=password,
                        role="ACCOUNTADMIN",
                        login_timeout=30,
                    )
                    conn.cursor().execute("SELECT CURRENT_ACCOUNT()")
                    st.session_state.conn = conn
                    st.session_state.account = account.strip()
                    st.session_state.username = username.strip()
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"Connection failed: {e}")

# ─────────────────────────────────────────────
# STEP 2 — Configure
# ─────────────────────────────────────────────
elif st.session_state.step == 2:
    st.markdown(
        f'<span class="badge badge-green">Connected as {st.session_state.username} @ {st.session_state.account}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # ── Default databases ──
    st.markdown('<div class="card-title">🗄️ Default Databases</div>', unsafe_allow_html=True)
    st.info(
        "Select which default databases to create. At least one must be selected. "
        "The **`_DB`** suffix is automatically appended to every database name.",
        icon="ℹ️",
    )
    dcols = st.columns(3)
    for col, name in zip(dcols, DEFAULT_DBS):
        current = st.session_state.default_dbs_selected.get(name, True)
        checked = col.checkbox(f"**{name}_DB**", value=current, key=f"defdb_{name}")
        st.session_state.default_dbs_selected[name] = checked
        badge_cls = "badge-blue" if checked else "badge-yellow"
        badge_lbl = "✅ Will be created" if checked else "⏭️ Will be skipped"
        col.markdown(
            f'<div class="card" style="text-align:center;padding:14px">'
            f'<div style="font-size:1.5rem">{"🗄️" if checked else "🚫"}</div>'
            f'<div style="color:{"#e2e8f0" if checked else "#6b7280"};font-weight:700;margin-top:4px">{name}_DB</div>'
            f'<div style="margin-top:8px"><span class="badge {badge_cls}">{badge_lbl}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Default schemas ──
    st.markdown('<div class="card-title">🏗️ Default Schemas (created in every database)</div>', unsafe_allow_html=True)
    st.info(
        "Three medallion-architecture schemas are created automatically inside **each** database. "
        "Schema-level RW and RO roles are also provisioned per schema.",
        icon="ℹ️",
    )
    scols = st.columns(3)
    for col, schema in zip(scols, DEFAULT_SCHEMAS):
        meta = SCHEMA_META[schema]
        rw_role = f"ROLE_&lt;DB&gt;_{schema}_RW"
        ro_role = f"ROLE_&lt;DB&gt;_{schema}_RO"
        col.markdown(
            f'<div class="card" style="text-align:center">'
            f'<div style="font-size:1.5rem">{meta["icon"]}</div>'
            f'<div style="color:#e2e8f0;font-weight:700;margin-top:6px">{schema}</div>'
            f'<div style="color:#94a3b8;font-size:0.75rem;margin:6px 0 10px">{meta["desc"]}</div>'
            f'<div style="font-size:0.7rem;color:#60a5fa">🔏 {rw_role}<br>👁️ {ro_role}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Extra databases ──
    st.markdown('<div class="card-title">➕ Additional Databases (optional)</div>', unsafe_allow_html=True)
    st.caption(
        "⚠️ **Note:** The `_DB` suffix is automatically added to every database name."
    )

    new_db = st.text_input(
        "Database name (without suffix)",
        placeholder="e.g. STAGING → will become STAGING_DB",
        key="new_db_input",
    )
    if st.button("Add Database"):
        name_clean = new_db.strip().upper().replace(" ", "_").replace("-", "_")
        if not name_clean:
            st.warning("Please enter a database name.")
        elif name_clean in DEFAULT_DBS or name_clean in st.session_state.extra_dbs:
            st.warning(f"**{name_clean}** is already in the list.")
        else:
            st.session_state.extra_dbs.append(name_clean)
            st.session_state.extra_dbs_schemas[name_clean] = True   # default: include schemas
            st.rerun()

    if st.session_state.extra_dbs:
        st.markdown("**Custom databases:**")
        for i, db in enumerate(st.session_state.extra_dbs):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"`{db}_DB`  <span class='badge badge-yellow'>Custom</span>", unsafe_allow_html=True)
            current_val = st.session_state.extra_dbs_schemas.get(db, True)
            include_schemas = c2.checkbox(
                "Create RAW / SILVER / GOLD schemas",
                value=current_val,
                key=f"schema_cb_{db}",
            )
            st.session_state.extra_dbs_schemas[db] = include_schemas
            if c3.button("✕", key=f"rm_{i}"):
                st.session_state.extra_dbs.pop(i)
                st.session_state.extra_dbs_schemas.pop(db, None)
                st.rerun()
    else:
        st.caption("No additional databases added yet.")

    st.markdown("---")

    # ── Deployment summary ──
    selected_default_dbs = [db for db in DEFAULT_DBS if st.session_state.default_dbs_selected.get(db, True)]
    all_dbs = selected_default_dbs + st.session_state.extra_dbs
    st.markdown('<div class="card-title">📋 Deployment Summary</div>', unsafe_allow_html=True)

    if not all_dbs:
        st.error("⚠️ No databases selected. Please select at least one database to proceed.")
    else:
        for db in all_dbs:
            is_default  = db in DEFAULT_DBS
            has_schemas = is_default or st.session_state.extra_dbs_schemas.get(db, True)
            badge       = "Default" if is_default else "Custom"
            badge_cls   = "badge-blue" if is_default else "badge-yellow"
            schema_note = ", ".join([f"`{s}`" for s in DEFAULT_SCHEMAS]) if has_schemas else "_no schemas_"
            st.markdown(
                f"**{db}_DB** <span class='badge {badge_cls}'>{badge}</span>  "
                f"— `ROLE_{db}_DB_ADMIN` · `ROLE_{db}_DB_RO`  "
                f"— Schemas: {schema_note}",
                unsafe_allow_html=True,
            )
            if has_schemas:
                for schema in DEFAULT_SCHEMAS:
                    st.markdown(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;↳ `{schema}` — "
                        f"`ROLE_{db}_{schema}_RW` · `ROLE_{db}_{schema}_RO`",
                        unsafe_allow_html=True,
                    )

        # Skipped default DBs
        skipped = [db for db in DEFAULT_DBS if not st.session_state.default_dbs_selected.get(db, True)]
        if skipped:
            st.markdown("")
            for db in skipped:
                st.markdown(
                    f"~~{db}_DB~~ <span class='badge badge-yellow'>⏭️ Skipped</span>",
                    unsafe_allow_html=True,
                )

    st.markdown("**admin_user** — ACCOUNTADMIN + RSA key-pair auth")

    st.markdown("")
    col_back, col_go = st.columns([1, 3])
    if col_back.button("← Back"):
        st.session_state.step = 1
        st.rerun()
    deploy_disabled = len(all_dbs) == 0
    if col_go.button(
        "🚀 Start Deployment",
        type="primary",
        use_container_width=True,
        disabled=deploy_disabled,
    ):
        st.session_state.step = 3
        st.rerun()

# ─────────────────────────────────────────────
# STEP 3 — Deploy
# ─────────────────────────────────────────────
elif st.session_state.step == 3:

    selected_default_dbs = [db for db in DEFAULT_DBS if st.session_state.default_dbs_selected.get(db, True)]
    all_dbs = selected_default_dbs + st.session_state.extra_dbs

    if not st.session_state.deployment_done:
        st.markdown('<div class="card-title">⚙️ Deploying Objects…</div>', unsafe_allow_html=True)
        progress_bar = st.progress(0, text="Starting…")
        log_placeholder = st.empty()

        conn = st.session_state.conn
        cur = conn.cursor()

        # ── Use ACCOUNTADMIN ──
        # Calculate total ticks: per DB = 2 (db-level roles) + per schema (if any) = 3 schemas × 2 roles = 6
        def db_ticks(db):
            has = (db in selected_default_dbs) or st.session_state.extra_dbs_schemas.get(db, True)
            return 3 + (len(DEFAULT_SCHEMAS) * 2 if has else 0)
        total_steps = sum(db_ticks(d) for d in all_dbs) + 4  # +4 for user steps
        _counter = [0]   # mutable list avoids nonlocal (module-level scope)

        def tick(label):
            _counter[0] += 1
            pct = min(int(_counter[0] / total_steps * 100), 99)
            progress_bar.progress(pct, text=label)
            with log_placeholder.container():
                render_logs()

        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "hdr")
        log("  SNOWFLAKE ACCOUNT SETUP — Starting…", "hdr")
        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "hdr")

        run_sql(cur, "USE ROLE ACCOUNTADMIN", "Switch to ACCOUNTADMIN")

        # ── DATABASES ──
        log("", "inf")
        log("── DATABASES ──────────────────────────────────────", "hdr")
        for db in all_dbs:
            db_name = f"{db}_DB"
            run_sql(cur, f'CREATE DATABASE IF NOT EXISTS "{db_name}"', f"Create database {db_name}")
            tick(f"Created {db_name}")

        # ── DB-LEVEL ROLES ──
        log("", "inf")
        log("── DB-LEVEL ROLES ─────────────────────────────────", "hdr")
        for db in all_dbs:
            db_name    = f"{db}_DB"
            admin_role = f"ROLE_{db}_DB_ADMIN"
            ro_role    = f"ROLE_{db}_DB_RO"

            # Admin role — full DB access
            run_sql(cur, f'CREATE ROLE IF NOT EXISTS "{admin_role}"', f"Create role {admin_role}")
            run_sql(cur, f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" TO ROLE "{admin_role}"',
                    f"Grant ALL on {db_name} → {admin_role}")
            run_sql(cur, f'GRANT ALL PRIVILEGES ON FUTURE SCHEMAS IN DATABASE "{db_name}" TO ROLE "{admin_role}"',
                    f"Grant FUTURE schemas → {admin_role}")
            run_sql(cur, f'GRANT ALL PRIVILEGES ON ALL SCHEMAS IN DATABASE "{db_name}" TO ROLE "{admin_role}"',
                    f"Grant ALL existing schemas → {admin_role}", skip_error=True)
            run_sql(cur, f'GRANT ALL PRIVILEGES ON FUTURE TABLES IN DATABASE "{db_name}" TO ROLE "{admin_role}"',
                    f"Grant FUTURE tables → {admin_role}")
            run_sql(cur, f'GRANT ALL PRIVILEGES ON ALL TABLES IN DATABASE "{db_name}" TO ROLE "{admin_role}"',
                    f"Grant ALL existing tables → {admin_role}", skip_error=True)
            tick(f"DB admin role: {admin_role}")

            # RO role — read-only DB access
            run_sql(cur, f'CREATE ROLE IF NOT EXISTS "{ro_role}"', f"Create role {ro_role}")
            run_sql(cur, f'GRANT USAGE ON DATABASE "{db_name}" TO ROLE "{ro_role}"',
                    f"Grant USAGE on {db_name} → {ro_role}")
            run_sql(cur, f'GRANT USAGE ON FUTURE SCHEMAS IN DATABASE "{db_name}" TO ROLE "{ro_role}"',
                    f"Grant USAGE FUTURE schemas → {ro_role}")
            run_sql(cur, f'GRANT USAGE ON ALL SCHEMAS IN DATABASE "{db_name}" TO ROLE "{ro_role}"',
                    f"Grant USAGE ALL schemas → {ro_role}", skip_error=True)
            run_sql(cur, f'GRANT SELECT ON FUTURE TABLES IN DATABASE "{db_name}" TO ROLE "{ro_role}"',
                    f"Grant SELECT FUTURE tables → {ro_role}")
            run_sql(cur, f'GRANT SELECT ON ALL TABLES IN DATABASE "{db_name}" TO ROLE "{ro_role}"',
                    f"Grant SELECT ALL tables → {ro_role}", skip_error=True)
            run_sql(cur, f'GRANT SELECT ON FUTURE VIEWS IN DATABASE "{db_name}" TO ROLE "{ro_role}"',
                    f"Grant SELECT FUTURE views → {ro_role}")
            run_sql(cur, f'GRANT SELECT ON ALL VIEWS IN DATABASE "{db_name}" TO ROLE "{ro_role}"',
                    f"Grant SELECT ALL views → {ro_role}", skip_error=True)
            tick(f"DB RO role: {ro_role}")

        # ── SCHEMAS + SCHEMA-LEVEL ROLES ──
        log("", "inf")
        log("── SCHEMAS & SCHEMA-LEVEL ROLES ───────────────────", "hdr")
        for db in all_dbs:
            db_name     = f"{db}_DB"
            has_schemas = (db in selected_default_dbs) or st.session_state.extra_dbs_schemas.get(db, True)
            if not has_schemas:
                log(f"⏭️  {db_name} — schema creation skipped (user choice)", "inf")
                continue

            log(f"", "inf")
            log(f"  ▸ {db_name}", "hdr")
            for schema in DEFAULT_SCHEMAS:
                meta    = SCHEMA_META[schema]
                rw_role = f"ROLE_{db}_{schema}_RW"
                ro_role = f"ROLE_{db}_{schema}_RO"

                # Create schema
                run_sql(cur,
                        f'CREATE SCHEMA IF NOT EXISTS "{db_name}"."{schema}" '
                        f'COMMENT = \'{meta["desc"]}\'',
                        f"Create schema {db_name}.{schema}  {meta['icon']}")

                # ── RW role ──
                run_sql(cur, f'CREATE ROLE IF NOT EXISTS "{rw_role}"', f"Create role {rw_role}")
                run_sql(cur, f'GRANT USAGE ON DATABASE "{db_name}" TO ROLE "{rw_role}"',
                        f"Grant DB USAGE → {rw_role}")
                run_sql(cur, f'GRANT ALL PRIVILEGES ON SCHEMA "{db_name}"."{schema}" TO ROLE "{rw_role}"',
                        f"Grant ALL on schema → {rw_role}")
                run_sql(cur, f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA "{db_name}"."{schema}" TO ROLE "{rw_role}"',
                        f"Grant ALL tables → {rw_role}", skip_error=True)
                run_sql(cur, f'GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA "{db_name}"."{schema}" TO ROLE "{rw_role}"',
                        f"Grant FUTURE tables → {rw_role}")
                run_sql(cur, f'GRANT ALL PRIVILEGES ON ALL VIEWS IN SCHEMA "{db_name}"."{schema}" TO ROLE "{rw_role}"',
                        f"Grant ALL views → {rw_role}", skip_error=True)
                run_sql(cur, f'GRANT ALL PRIVILEGES ON FUTURE VIEWS IN SCHEMA "{db_name}"."{schema}" TO ROLE "{rw_role}"',
                        f"Grant FUTURE views → {rw_role}")
                run_sql(cur, f'GRANT ALL PRIVILEGES ON ALL STAGES IN SCHEMA "{db_name}"."{schema}" TO ROLE "{rw_role}"',
                        f"Grant ALL stages → {rw_role}", skip_error=True)
                run_sql(cur, f'GRANT ALL PRIVILEGES ON FUTURE STAGES IN SCHEMA "{db_name}"."{schema}" TO ROLE "{rw_role}"',
                        f"Grant FUTURE stages → {rw_role}")
                tick(f"Schema RW role: {rw_role}")

                # ── RO role ──
                run_sql(cur, f'CREATE ROLE IF NOT EXISTS "{ro_role}"', f"Create role {ro_role}")
                run_sql(cur, f'GRANT USAGE ON DATABASE "{db_name}" TO ROLE "{ro_role}"',
                        f"Grant DB USAGE → {ro_role}")
                run_sql(cur, f'GRANT USAGE ON SCHEMA "{db_name}"."{schema}" TO ROLE "{ro_role}"',
                        f"Grant USAGE on schema → {ro_role}")
                run_sql(cur, f'GRANT SELECT ON ALL TABLES IN SCHEMA "{db_name}"."{schema}" TO ROLE "{ro_role}"',
                        f"Grant SELECT tables → {ro_role}", skip_error=True)
                run_sql(cur, f'GRANT SELECT ON FUTURE TABLES IN SCHEMA "{db_name}"."{schema}" TO ROLE "{ro_role}"',
                        f"Grant SELECT FUTURE tables → {ro_role}")
                run_sql(cur, f'GRANT SELECT ON ALL VIEWS IN SCHEMA "{db_name}"."{schema}" TO ROLE "{ro_role}"',
                        f"Grant SELECT views → {ro_role}", skip_error=True)
                run_sql(cur, f'GRANT SELECT ON FUTURE VIEWS IN SCHEMA "{db_name}"."{schema}" TO ROLE "{ro_role}"',
                        f"Grant SELECT FUTURE views → {ro_role}")
                run_sql(cur, f'GRANT READ ON ALL STAGES IN SCHEMA "{db_name}"."{schema}" TO ROLE "{ro_role}"',
                        f"Grant READ stages → {ro_role}", skip_error=True)
                run_sql(cur, f'GRANT READ ON FUTURE STAGES IN SCHEMA "{db_name}"."{schema}" TO ROLE "{ro_role}"',
                        f"Grant READ FUTURE stages → {ro_role}")
                tick(f"Schema RO role: {ro_role}")

        # ── ADMIN USER + KEY PAIR ──
        log("", "inf")
        log("── ADMIN USER & KEY PAIR ───────────────", "hdr")

        private_key_pem, pub_key_b64, passphrase = generate_key_pair()
        st.session_state.private_key_pem = private_key_pem
        st.session_state.passphrase      = passphrase
        log("🔑  RSA-2048 key pair generated (encrypted with random passphrase)", "ok")
        tick("Key pair generated")

        run_sql(cur, "CREATE USER IF NOT EXISTS admin_user PASSWORD='' MUST_CHANGE_PASSWORD=FALSE",
                "Create user admin_user")
        tick("User created")

        run_sql(cur,
                f"ALTER USER admin_user SET RSA_PUBLIC_KEY='{pub_key_b64}'",
                "Attach RSA public key to admin_user")
        tick("Public key attached")

        run_sql(cur, "GRANT ROLE ACCOUNTADMIN TO USER admin_user",
                "Grant ACCOUNTADMIN → admin_user")
        run_sql(cur, "ALTER USER admin_user SET DEFAULT_ROLE = ACCOUNTADMIN",
                "Set default role ACCOUNTADMIN for admin_user")
        tick("Role granted")

        progress_bar.progress(100, text="Deployment complete!")
        log("", "inf")
        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "hdr")
        log("  ✅  ALL DONE — Deployment successful!", "ok")
        log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "hdr")

        with log_placeholder.container():
            render_logs()

        st.session_state.deployment_done = True
        time.sleep(0.5)
        st.rerun()

    else:
        # Already deployed — show summary + proceed button
        st.success("✅ Deployment finished successfully!", icon="🎉")
        render_logs()
        st.markdown("")
        if st.button("⬇️ Proceed to Download Credentials", type="primary", use_container_width=True):
            st.session_state.step = 4
            st.rerun()

# ─────────────────────────────────────────────
# STEP 4 — Download Credentials
# ─────────────────────────────────────────────
elif st.session_state.step == 4:

    st.markdown('<div class="card-title">🎉 Setup Complete — Download Your Credentials</div>', unsafe_allow_html=True)

    selected_default_dbs = [db for db in DEFAULT_DBS if st.session_state.default_dbs_selected.get(db, True)]
    all_dbs = selected_default_dbs + st.session_state.extra_dbs

    # ── Summary table ──
    st.markdown("### 🗄️ Objects Created")
    for db in all_dbs:
        db_name     = f"{db}_DB"
        admin_role  = f"ROLE_{db}_DB_ADMIN"
        ro_role     = f"ROLE_{db}_DB_RO"
        has_schemas = (db in selected_default_dbs) or st.session_state.extra_dbs_schemas.get(db, True)

        with st.expander(f"**{db_name}**", expanded=False):
            st.markdown(f"**DB-level roles:**")
            st.markdown(f"- `{admin_role}` — full read/write on entire database")
            st.markdown(f"- `{ro_role}` — read-only on entire database")
            if has_schemas:
                st.markdown(f"**Schemas & schema-level roles:**")
                for schema in DEFAULT_SCHEMAS:
                    meta    = SCHEMA_META[schema]
                    rw_role = f"ROLE_{db}_{schema}_RW"
                    ro_role_s = f"ROLE_{db}_{schema}_RO"
                    st.markdown(
                        f"- {meta['icon']} **{schema}** — _{meta['desc']}_  \n"
                        f"  `{rw_role}` (read/write) · `{ro_role_s}` (read-only)"
                    )
            else:
                st.markdown("_Schemas skipped for this database._")

    st.markdown("**admin_user** — ACCOUNTADMIN role + RSA key-pair authentication enabled")

    st.markdown("---")

    # ── Download section ──
    st.markdown("### 🔑 Download Credentials")
    st.warning(
        "**Save these files now.** The private key cannot be recovered after you leave this page.",
        icon="⚠️",
    )

    private_key_pem = st.session_state.private_key_pem
    passphrase      = st.session_state.passphrase

    if private_key_pem and passphrase:
        # Build a passphrase info file
        info_content = (
            f"Snowflake admin_user Key-Pair Credentials\n"
            f"==========================================\n"
            f"Account       : {st.session_state.account}\n"
            f"User          : admin_user\n"
            f"Auth method   : RSA key-pair\n"
            f"Private key   : rsa_key_admin_user.p8  (PKCS8, PEM, encrypted)\n"
            f"Passphrase    : {passphrase}\n\n"
            f"Usage with SnowSQL:\n"
            f"  snowsql -a {st.session_state.account} -u admin_user \\\n"
            f"          --private-key-path rsa_key_admin_user.p8\n\n"
            f"Environment variable for passphrase:\n"
            f"  export SNOWSQL_PRIVATE_KEY_PASSPHRASE='{passphrase}'\n"
        )

        col_key, col_info = st.columns(2)
        with col_key:
            st.download_button(
                label="⬇️  Download Private Key (.p8)",
                data=private_key_pem,
                file_name="rsa_key_admin_user.p8",
                mime="application/x-pem-file",
                use_container_width=True,
            )
            st.caption("Encrypted PKCS8 PEM — keep this file secret and never commit to version control.")

        with col_info:
            st.download_button(
                label="⬇️  Download Credentials Info (.txt)",
                data=info_content,
                file_name="snowflake_admin_credentials.txt",
                mime="text/plain",
                use_container_width=True,
            )
            st.caption("Contains the passphrase and usage instructions.")

        st.markdown("")
        with st.expander("👁️  View passphrase (click to reveal)"):
            st.code(passphrase, language=None)
            st.caption("This is the encryption passphrase for your private key file.")

    st.markdown("---")

    # ── Next steps ──
    st.markdown("### 🚀 Next Steps")
    st.markdown("""
1. **Store credentials securely** — use a password manager or secrets vault (e.g. AWS Secrets Manager, HashiCorp Vault).
2. **Configure key-pair auth** — point your Snowflake client to the `.p8` file and set the `SNOWSQL_PRIVATE_KEY_PASSPHRASE` env var.
3. **Assign roles to users** — grant `ROLE_<DB>_DB_ADMIN` or `ROLE_<DB>_DB_RO` to team members as appropriate.
4. **Create warehouses** — virtual warehouses (compute clusters) are not included in this setup; create them under **Admin → Warehouses** in the Snowflake UI.
""")

    st.markdown("")
    if st.button("🔄 Run a New Setup", use_container_width=True):
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()