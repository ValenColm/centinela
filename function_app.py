import logging
import traceback
import azure.functions as func

logging.basicConfig(level=logging.INFO)

try:
    from api.main import app as fastapi_app
    logging.info("Successfully imported FastAPI app")
    app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
except Exception as e:
    error_msg = f"Import Error: {e}\n\n{traceback.format_exc()}"
    logging.error(error_msg)
    
    app = func.FunctionApp()
    
    @app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
    def health(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(error_msg, status_code=200, mimetype="text/plain")
