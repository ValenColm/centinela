"""Azure Functions ASGI entry point for the Centinela ingestion API."""

import azure.functions as func

from api.main import app


azure_app = func.AsgiFunctionApp(app=app, http_auth_level=func.AuthLevel.ANONYMOUS)
