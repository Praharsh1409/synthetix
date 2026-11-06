"""Server-side AI boundary. No inference provider is enabled in this release."""

UNAVAILABLE_MESSAGE = (
    'AI planning, website generation and automatic repair are temporarily unavailable '
    'while a replacement backend is being developed. Import HTML, preview it, run browser '
    'checks, inspect saved versions and download your code without an AI connection.'
)


class AIUnavailableError(RuntimeError):
    """The requested operation needs a configured, verified inference backend."""


def available():
    return False


def request_completion(*, messages, max_tokens):
    """Fail before network activity; never infer credentials or return sample output."""
    raise AIUnavailableError(UNAVAILABLE_MESSAGE)
