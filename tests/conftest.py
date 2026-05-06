import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _is_outside_repo(module_file: str | None) -> bool:
    if not module_file:
        return False
    module_path = Path(module_file).resolve()
    return ROOT not in module_path.parents and module_path != ROOT


for module_name, module in list(sys.modules.items()):
    if module_name == "backend" or module_name.startswith("backend."):
        if _is_outside_repo(getattr(module, "__file__", None)):
            sys.modules.pop(module_name, None)
