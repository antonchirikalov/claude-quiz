class SchemaError(RuntimeError):
    """Raised when a question record fails validation."""


class QuizError(RuntimeError):
    """Raised for invalid quiz state (e.g. unknown question id)."""
