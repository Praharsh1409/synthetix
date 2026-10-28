import json
import os
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import patch
try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import APITimeoutError,InternalServerError
import generate_ui,synthetix,nebius_tasks
from artifact_io import public_error


def response(content,reason='stop'):
    return NS(choices=[NS(finish_reason=reason,message=NS(content=content))])


class ModelFailureTests(unittest.TestCase):
    def check_generation_rejected(self,value):
        with patch('generate_ui.OpenAI') as factory,patch.dict(os.environ,{'NEBIUS_API_KEY':'audit-placeholder-key'}):
            factory.return_value.chat.completions.create.return_value=value
            with self.assertRaises(RuntimeError):generate_ui.generate_html('Audit fixture')

    def test_missing_choices_rejected(self):self.check_generation_rejected(NS(choices=[]))
    def test_truncated_html_rejected(self):self.check_generation_rejected(response('<!DOCTYPE html><html></html>','length'))
    def test_non_html_rejected(self):self.check_generation_rejected(response('A model explanation'))
    def test_unfinished_response_is_not_accepted(self):self.check_generation_rejected(response('<!DOCTYPE html><html></html>','tool_calls'))
    def test_malformed_message_gets_a_clear_model_error(self):self.check_generation_rejected(NS(choices=[NS(finish_reason='stop',message=None)]))

    def test_invalid_json_plan_rejected(self):
        with patch('nebius_tasks.OpenAI') as factory,patch.dict(os.environ,{'NEBIUS_API_KEY':'audit-placeholder-key'}):
            factory.return_value.chat.completions.create.return_value=response('{not JSON')
            with self.assertRaisesRegex(ValueError,'invalid plan'):nebius_tasks.ask_json('Plan','Audit')

    def test_timeout_is_preserved_as_failed_generation(self):
        error=APITimeoutError(request=httpx.Request('POST','https://model.invalid'))
        with tempfile.TemporaryDirectory() as temp,patch.object(synthetix,'PROJECT_FOLDER',Path(temp)),patch.object(synthetix,'generate_html',side_effect=error):
            result=synthetix.run_pipeline('Audit timeout')
            self.assertEqual(result['status'],'generation_failed')
            self.assertIn('timed out',result['error'].lower())

    def test_http_error_never_copies_secret_response_body(self):
        response_=httpx.Response(503,request=httpx.Request('POST','https://model.invalid'))
        secret='audit-only-sensitive-key'
        error=InternalServerError(secret,response=response_,body={'error':secret})
        with patch.dict(os.environ,{'NEBIUS_API_KEY':secret}):
            self.assertNotIn(secret,public_error(error))
            self.assertIn('503',public_error(error))

    def test_public_error_redacts_credentials(self):
        with patch.dict(os.environ,{'NEBIUS_API_KEY':'audit-sensitive-value'}):
            self.assertNotIn('audit-sensitive-value',public_error(RuntimeError('Failed: audit-sensitive-value')))
