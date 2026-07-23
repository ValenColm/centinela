import logging
import traceback
import azure.functions as func

try:
    from api.main import app as fastapi_app
    logging.info("Successfully imported FastAPI app")
    app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
except Exception as e:
    logging.error(f"Failed to import FastAPI app: {e}")
    logging.error(traceback.format_exc())
    
    # Fallback: simple health check
    app = func.FunctionApp()
    
    @app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
    def health(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(f"Import Error: {str(e)}", status_code=500)
