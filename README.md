# ❄️ Snowflake Account Setup Wizard

A single-file Streamlit application that automates provisioning of databases, schemas, roles, and an admin user on a fresh Snowflake trial account — following a medallion architecture pattern (RAW → SILVER → GOLD).

---

#  access the streamlit comminity domain 
https://app-acc-setup-wizard-hkutz3vrkle6sx3y3gdf2l.streamlit.app/

## Features

| Feature | Detail |
|---|---|
| **Connection** | Connects via `snowflake-connector-python` using `ACCOUNTADMIN` |
| **Databases** | Creates `DEV_DB`, `QA_DB`, `PROD_DB` by default + optional custom databases |
| **DB-level roles** | `ROLE_<DB>_DB_ADMIN` (full access) and `ROLE_<DB>_DB_RO` (read-only) per database |
| **Schemas** | `RAW`, `SILVER`, `GOLD` created inside every database (medallion architecture) |
| **Schema-level roles** | `ROLE_<DB>_<SCHEMA>_RW` (read/write) and `ROLE_<DB>_<SCHEMA>_RO` (read-only) per schema |
| **Admin user** | Creates `admin_user`, grants `ACCOUNTADMIN`, sets up RSA-2048 key-pair auth |
| **Credentials** | Download encrypted private key (`.p8`) + passphrase info file at the end |

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
streamlit run snowflake_setup.py
```

Opens at **http://localhost:8501** in your browser.

---

## Wizard Steps

### Step 1 — Connect
Enter your Snowflake **Account Identifier**, **Username**, and **Password**.
The wizard connects using the `ACCOUNTADMIN` role.

> Account identifier format: `abc12345` or `abc12345.us-east-1`  
> Find it in your Snowflake welcome email or under **Admin → Accounts**.

---

### Step 2 — Configure

**Default databases** (always created):

| Database | Suffix enforced |
|---|---|
| DEV | `DEV_DB` |
| QA | `QA_DB` |
| PROD | `PROD_DB` |

**Additional databases** (optional):
- Enter any name; the `_DB` suffix is appended automatically.
- Each custom database has a checkbox: **"Create RAW / SILVER / GOLD schemas"** (enabled by default). Uncheck to skip schemas for that database entirely.

**Deployment summary** is shown before you proceed — lists every database, schema, and role that will be created.

---

### Step 3 — Deploy

The wizard runs all DDL in sequence and streams a live colour-coded log.

#### Objects created per database

**Database**
```
CREATE DATABASE <DB>_DB
```

**DB-level roles**

| Role | Privileges |
|---|---|
| `ROLE_<DB>_DB_ADMIN` | `ALL PRIVILEGES` on database, all current + future schemas, tables, views |
| `ROLE_<DB>_DB_RO` | `USAGE` on database + all schemas; `SELECT` on all current + future tables and views |

**Schemas** (RAW, SILVER, GOLD — skippable on custom databases)

| Schema | Purpose |
|---|---|
| `RAW` | Raw / ingested data as-is from source systems |
| `SILVER` | Cleaned, validated and conformed data |
| `GOLD` | Business-logic layer — aggregates, metrics, reports |

**Schema-level roles** (created for each schema)

| Role | Privileges |
|---|---|
| `ROLE_<DB>_<SCHEMA>_RW` | `USAGE` on DB + `ALL PRIVILEGES` on schema, tables, views, stages (current + future) |
| `ROLE_<DB>_<SCHEMA>_RO` | `USAGE` on DB + schema; `SELECT` on tables/views; `READ` on stages (current + future) |

**Full role inventory example for `DEV_DB`:**
```
ROLE_DEV_DB_ADMIN        — full access, entire DEV_DB
ROLE_DEV_DB_RO           — read-only, entire DEV_DB

ROLE_DEV_RAW_RW          — read/write on DEV_DB.RAW
ROLE_DEV_RAW_RO          — read-only  on DEV_DB.RAW

ROLE_DEV_SILVER_RW       — read/write on DEV_DB.SILVER
ROLE_DEV_SILVER_RO       — read-only  on DEV_DB.SILVER

ROLE_DEV_GOLD_RW         — read/write on DEV_DB.GOLD
ROLE_DEV_GOLD_RO         — read-only  on DEV_DB.GOLD
```

**Admin user**
```
CREATE USER admin_user
GRANT ROLE ACCOUNTADMIN TO USER admin_user
ALTER USER admin_user SET RSA_PUBLIC_KEY = '...'   -- RSA-2048
```

---

### Step 4 — Download Credentials

After deployment you can download:

- ⬇️ **`rsa_key_admin_user.p8`** — encrypted PKCS8 PEM private key (unique per run)
- ⬇️ **`snowflake_admin_credentials.txt`** — passphrase + ready-to-use connection commands

> ⚠️ **Save these files immediately.** The private key is generated in-memory and cannot be recovered once you close the page.

An expandable summary lists every database, schema, and role that was provisioned.

---

## Role Naming Convention

```
ROLE_<DATABASE>_DB_ADMIN        — full database access
ROLE_<DATABASE>_DB_RO           — read-only database access
ROLE_<DATABASE>_<SCHEMA>_RW     — read/write schema access
ROLE_<DATABASE>_<SCHEMA>_RO     — read-only schema access
```

Where `<DATABASE>` is the database name **without** the `_DB` suffix (e.g. `DEV`, `PROD`, `STAGING`).

---

## Using the Key Pair

```bash
# Store the passphrase in an environment variable
export SNOWSQL_PRIVATE_KEY_PASSPHRASE='<passphrase from credentials file>'

# Connect with SnowSQL
snowsql -a <account_identifier> -u admin_user \
        --private-key-path rsa_key_admin_user.p8
```

Python connector:
```python
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import snowflake.connector

with open("rsa_key_admin_user.p8", "rb") as f:
    private_key = load_pem_private_key(f.read(), password=b"<passphrase>")

conn = snowflake.connector.connect(
    account="<account_identifier>",
    user="admin_user",
    private_key=private_key,
    role="ACCOUNTADMIN",
)
```

---

## Next Steps After Setup

1. **Create virtual warehouses** — not provisioned by this wizard; add them under **Admin → Warehouses** in the Snowflake UI.
2. **Assign roles to team members** — use schema-level roles for fine-grained access:
   - Data engineers loading raw data → `ROLE_<ENV>_RAW_RW`
   - Data analysts reading clean data → `ROLE_<ENV>_SILVER_RO` / `ROLE_<ENV>_GOLD_RO`
   - dbt / transformation service accounts → `ROLE_<ENV>_SILVER_RW`, `ROLE_<ENV>_GOLD_RW`
3. **Store credentials securely** — AWS Secrets Manager, HashiCorp Vault, or your CI/CD secrets store.
4. **Rotate the key pair periodically** — re-run the wizard or use `ALTER USER admin_user SET RSA_PUBLIC_KEY = '...'`.

---

## Security Notes

- The RSA-2048 private key is generated fresh in-memory on every run — never stored to disk by the app
- The key is encrypted with a random 32-character URL-safe passphrase
- `admin_user` has no password set — key-pair is the only authentication method
- Never commit `.p8` files or passphrases to version control
- Revoke or rotate the key via `ALTER USER admin_user UNSET RSA_PUBLIC_KEY` if compromised

---

## Dependencies

```
streamlit>=1.35.0
snowflake-connector-python>=3.10.0
cryptography>=42.0.0
```