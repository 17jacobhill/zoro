import json
import logging
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
import tiktoken

from backend.utils import get_project_root
from backend.visualization.services.supervisor_agent import SupervisorAgent

logger = logging.getLogger(__name__)


class ChatWatcher:
    TOKEN_INTERVAL = 5000
