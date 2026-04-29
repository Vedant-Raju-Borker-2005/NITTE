import os
from sentinelhub import SHConfig

# IDs provided by user (non-secret identifiers)
account_id = os.getenv("SH_ACCOUNT_ID", "e9b5f235-7cc4-44be-90c7-d5562e0976e0")
user_id = os.getenv("SH_USER_ID", "13ef2add-3c51-4185-9377-05375eb3adfd")

# NOTE: Real Sentinel auth requires OAuth client credentials.
# Use env vars first; fall back to provided credentials for local development.
client_id = os.getenv("SH_CLIENT_ID", "f49b27d5-dcfb-4544-aa9c-7a42122ac4d6")
client_secret = os.getenv("SH_CLIENT_SECRET", "UDH7cIgg78zm8blnV7RyTys2vGhB33MP")

# macOS/Python SSL chain hardening for requests/sentinelhub.
try:
    import certifi  # type: ignore

    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except Exception:
    pass

config = SHConfig(
    use_defaults=True,
    sh_client_id=client_id,
    sh_client_secret=client_secret,
)

# Attach non-secret metadata for diagnostics.
config.sh_account_id = account_id  # type: ignore[attr-defined]
config.sh_user_id = user_id  # type: ignore[attr-defined]

# Keep requests bounded to avoid hanging the API.
config.download_timeout_seconds = int(os.getenv("SENTINELHUB_TIMEOUT", "10"))
config.max_download_attempts = int(os.getenv("SENTINELHUB_ATTEMPTS", "1"))
config.download_sleep_time = float(os.getenv("SENTINELHUB_SLEEP", "2.0"))
