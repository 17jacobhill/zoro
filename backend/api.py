import argparse
from flask import Flask
from flask_cors import CORS
import logging
from pathlib import Path
import shutil
import socket
import subprocess
import time
import webbrowser

from backend.utils import get_project_root
from backend.routes.visualization_api import visualization_bp
from backend.routes.knowledge_api import knowledge_bp
from backend.visualization.services import visualization_manager as vm


DEFAULT_BACKEND_HOST = "0.0.0.0"
DEFAULT_BACKEND_PORT = 5010
DEFAULT_FRONTEND_HOST = "127.0.0.1"
DEFAULT_FRONTEND_PORT = 5274

def create_app():
    app = Flask(__name__)
    
    CORS(app, 
         origins=["http://localhost:5274", "http://127.0.0.1:5274"],
         methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization"])
    
    log_path = get_project_root() / ".zoro" / "logs" / "zoro-api.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Logging to %s", str(log_path))

    recovered_count = vm.recover_sessions_after_restart()
    if recovered_count:
        logger.info("Recovered %s visualization session(s): polling -> paused", recovered_count)
    
    app.register_blueprint(visualization_bp)
    app.register_blueprint(knowledge_bp)
    
    logger.info("Registered blueprints: visualization, knowledge")
    
    return app


def _frontend_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _detect_npm_binary() -> str | None:
    candidates = ["npm.cmd", "npm"] if shutil.which("npm.cmd") else ["npm"]
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    return None


def _start_frontend_dev_server(frontend_dir: Path, host: str, port: int) -> tuple[subprocess.Popen | None, str]:
    frontend_url = _frontend_url(host, port)

    if _port_is_open(host, port):
        return None, f"Frontend already running at {frontend_url}"

    if not (frontend_dir / "package.json").exists():
        return None, f"Frontend package.json not found at {frontend_dir}"

    npm_binary = _detect_npm_binary()
    if not npm_binary:
        return None, "npm was not found on PATH, so the frontend was not launched automatically"

    command = [npm_binary, "run", "dev", "--", "--host", host, "--port", str(port)]
    process = subprocess.Popen(command, cwd=frontend_dir)

    deadline = time.time() + 20
    while time.time() < deadline:
        if process.poll() is not None:
            return process, "Frontend dev server exited before it became reachable"
        if _port_is_open(host, port):
            return process, f"Launched frontend dev server at {frontend_url}"
        time.sleep(0.25)

    return process, f"Frontend launch was started, but {frontend_url} was not reachable yet"


def _stop_frontend_process(process: subprocess.Popen | None) -> None:
    if not process or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def serve_api(
    host: str = DEFAULT_BACKEND_HOST,
    port: int = DEFAULT_BACKEND_PORT,
    *,
    debug: bool = True,
    use_reloader: bool = False,
):
    app = create_app()
    print(f"Starting Zoro API on http://localhost:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)


def backend_only_main():
    main(["--backend-only"])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Start Zoro locally. By default this launches the API, starts the local frontend when possible, and opens the UI in a browser."
    )
    parser.add_argument("--backend-host", default=DEFAULT_BACKEND_HOST)
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--frontend-host", default=DEFAULT_FRONTEND_HOST)
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    parser.add_argument("--backend-only", action="store_true", help="Start only the Flask API")
    parser.add_argument("--no-frontend", action="store_true", help="Do not launch the frontend dev server")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    parser.add_argument("--no-debug", action="store_true", help="Disable Flask debug mode")
    args = parser.parse_args(argv)

    frontend_process = None
    frontend_url = _frontend_url(args.frontend_host, args.frontend_port)

    if not args.backend_only and not args.no_frontend:
        frontend_dir = get_project_root() / "frontend"
        frontend_process, frontend_message = _start_frontend_dev_server(
            frontend_dir, args.frontend_host, args.frontend_port
        )
        print(frontend_message)
    elif not args.backend_only:
        print(f"Skipping frontend launch. Open {frontend_url} yourself if it is already running.")

    if not args.backend_only and not args.no_browser:
        if _port_is_open(args.frontend_host, args.frontend_port):
            try:
                webbrowser.open(frontend_url, new=1)
                print(f"Opened Zoro UI at {frontend_url}")
            except Exception as error:
                print(f"Could not open the browser automatically: {error}")
                print(f"Open {frontend_url} manually.")
        else:
            print(f"Frontend is not reachable yet. When it is ready, open {frontend_url}")

    try:
        serve_api(
            host=args.backend_host,
            port=args.backend_port,
            debug=not args.no_debug,
            use_reloader=False,
        )
    finally:
        _stop_frontend_process(frontend_process)

if __name__ == '__main__':
    main()
