import os

import firebase_admin
from firebase_admin import credentials


def initialize_firebase() -> None:
    """Initialize Firebase Admin SDK once, from a service-account JSON.

    Path comes from FIREBASE_SERVICE_ACCOUNT_JSON (defaults to
    ``firebase_service_account.json`` in the working directory).
    """
    if not firebase_admin._apps:
        service_account_path = os.getenv(
            "FIREBASE_SERVICE_ACCOUNT_JSON", "firebase_service_account.json"
        )
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
