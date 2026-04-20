"""
Default task type definitions for zoro.

These types are used by TaskCategorizer to match tasks to predefined categories.
"""

DEFAULT_TASK_TYPES = [
    {"name": "planning", "description": "Designing approach, architecting solution, organizing work"},
    {"name": "code-style", "description": "Formatting, naming conventions, readability, documentation"},
    {"name": "testing", "description": "Verifying correctness, writing tests, checking behavior"},
    {"name": "debugging", "description": "Fixing errors, bugs, or broken functionality"},
    {"name": "checking-with-user", "description": "Confirming requirements, aligning on approach, getting approval"}
]
