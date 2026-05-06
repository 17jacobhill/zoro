from __future__ import annotations

import logging

from flask import Blueprint, jsonify

visualization_bp = Blueprint("visualization", __name__)
logger = logging.getLogger(__name__)


def handle_error(endpoint_name, error, status_code=500):
    logger.error(f"Error in {endpoint_name}: {str(error)}", exc_info=True)
    return jsonify({"success": False, "error": str(error)}), status_code
