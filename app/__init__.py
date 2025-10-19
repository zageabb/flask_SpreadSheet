import logging
import logging.config
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session as SQLModelSession, create_engine

from .config import config_by_name, DevelopmentConfig
from .services.database import close_db, get_session, run_migrations
from .services.sheets import SheetRepository, SheetService


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def handle_bad_request(error):
        app.logger.warning("Bad request: %s", error)
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            response = {"error": "bad_request", "message": getattr(error, "description", str(error))}
            return jsonify(response), 400
        return render_template("400.html", error=error), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        app.logger.info("Not found: %s", error)
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            response = {"error": "not_found", "message": getattr(error, "description", str(error))}
            return jsonify(response), 404
        return render_template("404.html", error=error), 404

    @app.errorhandler(500)
    def handle_internal_error(error):
        app.logger.error("Internal server error", exc_info=error)
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            response = {"error": "internal_server_error", "message": "An unexpected error occurred."}
            return jsonify(response), 500
        return render_template("500.html", error=error), 500


def create_app(config_name: str | None = None) -> Flask:
    load_dotenv()

    package_root = Path(__file__).resolve().parent
    project_root = package_root.parent

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )

    config_key = (config_name or os.getenv("FLASK_CONFIG", "development")).lower()
    config_object = config_by_name.get(config_key, DevelopmentConfig)
    app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)

    database_name = app.config.get("DATABASE_NAME", "spreadsheet.db")
    database_path = os.path.join(app.instance_path, database_name)
    app.config["DATABASE_PATH"] = database_path
    database_url = f"sqlite:///{database_path}"
    app.config["DATABASE_URL"] = database_url

    engine = create_engine(
        database_url,
        echo=app.config.get("SQL_ECHO", False),
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, class_=SQLModelSession, expire_on_commit=False)
    app.extensions["sqlmodel"] = {"engine": engine, "session_factory": session_factory}

    logging_config = app.config.get("LOGGING_CONFIG")
    if logging_config:
        logging_path = Path(logging_config)
        if not logging_path.is_absolute():
            logging_path = Path(app.root_path).parent / logging_path
        if logging_path.exists():
            logging.config.fileConfig(logging_path, disable_existing_loggers=False)
        else:
            logging.basicConfig(level=app.config.get("LOG_LEVEL", logging.INFO))
            app.logger.warning("Logging configuration file not found at %s", logging_path)
    else:
        logging.basicConfig(level=app.config.get("LOG_LEVEL", logging.INFO))

    from .blueprints.main import main_bp

    app.register_blueprint(main_bp)

    app.teardown_appcontext(close_db)

    with app.app_context():
        run_migrations()
        service = SheetService(SheetRepository(get_session()))
        service.ensure_default_sheet()
        close_db()

    register_error_handlers(app)

    return app
