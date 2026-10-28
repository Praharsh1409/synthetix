"""Atomic local checkpoints and credential-safe public errors."""
import json
import os
from pathlib import Path
import tempfile


def write_text(path, text):
    path=Path(path)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='',
                                         dir=path.parent,prefix=path.name+'.',suffix='.tmp',delete=False) as file:
            temporary=Path(file.name)
            file.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path, value):
    write_text(path,json.dumps(value,indent=2))


def public_error(error):
    status=getattr(error,'status_code',None)
    if status:
        return f'The model service returned HTTP {status}. Check service access and availability, then retry.'
    message=str(error)[:2000] or type(error).__name__
    for key,value in os.environ.items():
        if len(value)>6 and any(word in key.upper() for word in ('API_KEY','TOKEN','SECRET','PASSWORD')):
            message=message.replace(value,'[redacted]')
    return message
