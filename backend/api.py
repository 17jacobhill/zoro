from flask import Flask
from flask_cors import CORS
import logging
from pathlib import Path

from backend.utils import get_project_root
from backend.routes.learner_routes import learner_bp
from backend.routes.assistant_routes import assistant_bp
from backend.routes.enforcement_routes import enforcement_bp
from backend.routes.visualization_routes import visualization_bp
from backend.routes.knowledge_routes import knowledge_bp

def create_app():
    app = Flask(__name__)
    
    CORS(app, 
         origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
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
    
    app.register_blueprint(learner_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(enforcement_bp)
    app.register_blueprint(visualization_bp)
    app.register_blueprint(knowledge_bp)
    
    logger.info("Registered blueprints: learner, assistant, enforcement, visualization, knowledge")
    
    return app

def main():
    app = create_app()
    print("Starting Zoro API on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)

if __name__ == '__main__':
    main()