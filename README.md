# ❄️ Snowflake Account Setup Wizard

A single-file Streamlit application that automates provisioning of databases, roles, and an admin user on a fresh Snowflake trial account.

# access the streamlit comminity domain 
https://app-acc-setup-wizard-hkutz3vrkle6sx3y3gdf2l.streamlit.app/

---

## Features

| Feature | Detail |
|---|---|
| **Connection** | Connects via `snowflake-connector-python` using ACCOUNTADMIN |
| **Databases** | Creates `DEV_DB`, `QA_DB`, `PROD_DB` + any additional DBs you specify |
| **Roles** | Per-DB `ROLE_<DB>_ADMIN` (full access) and `ROLE_<DB>_RO` (read-only) |
| **Admin user** | Creates `admin_user`, grants ACCOUNTADMIN, sets up RSA key-pair auth |
| **Credentials** | Download encrypted private key (`.p8`) + passphrase info file |

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

The app opens at **http://localhost:8501** in your browser.

---

## Wizard Steps

### Step 1 — Connect
Enter your Snowflake **Account Identifier**, **Username**, and **Password**.  
The account identifier looks like `abc12345` or `abc12345.us-east-1`.

### Step 2 — Configure
- Default databases shown: `DEV_DB`, `QA_DB`, `PROD_DB`
- Optionally add extra databases (the `_DB` suffix is added automatically)
- Review the full deployment summary before proceeding

### Step 3 — Deploy
The wizard executes all DDL statements in sequence and displays a live log.  
Objects created:
- Databases
- `ROLE_<DB>_DB_ADMIN` with `ALL PRIVILEGES` on the database
- `ROLE_<DB>_DB_RO` with `USAGE` + `SELECT` (current + future objects)
- `admin_user` with RSA-2048 key-pair auth + ACCOUNTADMIN role

### Step 4 — Download
- ⬇️ **Private key** (`rsa_key_admin_user.p8`) — encrypted PKCS8 PEM
- ⬇️ **Credentials info** (`.txt`) — passphrase + usage instructions

---

## Using the Key Pair

```bash
# Set passphrase as environment variable
export SNOWSQL_PRIVATE_KEY_PASSPHRASE='<passphrase from download>'

# Connect with SnowSQL
snowsql -a <account_identifier> -u admin_user \
        --private-key-path rsa_key_admin_user.p8
```

For Python:
```python
from cryptography.hazmat.primitives.serialization import load_pem_private_key

with open("rsa_key_admin_user.p8", "rb") as f:
    private_key = load_pem_private_key(f.read(), password=b"<passphrase>")
```

---

## Security Notes
- The private key is generated fresh on every deployment run
- The key is encrypted with a random 32-character passphrase
- Never commit the `.p8` file or passphrase to version control
- Store credentials in a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
