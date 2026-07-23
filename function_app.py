import logging
import sys
import os
import traceback
import azure.functions as func

logging.basicConfig(level=logging.INFO)

def get_pip_list():
    import subprocess
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=columns"], 
                              capture_output=True, text=True, timeout=10)
        return result.stdout + "\n" + result.stderr
    except Exception as e:
        return f"pip list failed: {e}"

def get_sys_path():
    return "\n".join(sys.path)

# Check for .python_packages before importing api
python_packages_path = os.path.join(os.path.dirname(__file__), ".python_packages", "lib", "site-packages")
logging.info(f"Site packages path: {python_packages_path}")
logging.info(f"Exists: {os.path.exists(python_packages_path)}")
if os.path.exists(python_packages_path):
    logging.info(f"Contents: {os.listdir(python_packages_path)[:20]}")

try:
    from api.main import app as fastapi_app
    logging.info("Successfully imported FastAPI app")
    app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
except Exception as e:
    error_msg = f"Import Error: {e}\n\n{traceback.format_exc()}"
    error_msg += f"\n\nPython path:\n{get_sys_path()}"
    error_msg += f"\n\nPip list:\n{get_pip_list()}"
    logging.error(error_msg)
    
    app = func.FunctionApp()
    
    @app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
    def health(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(error_msg, status_code=200, mimetype="text/plain")
