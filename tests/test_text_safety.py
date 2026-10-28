import unittest
from text_safety import markdown_text


class LiteralTextTests(unittest.TestCase):
    def test_image_and_link_syntax_is_literal(self):
        source='![audit](http://127.0.0.1/canary)'
        escaped=markdown_text(source)
        self.assertNotIn('![',escaped)
        self.assertIn('\\!\\[audit\\]',escaped)
        self.assertIn('http\\:',escaped)

    def test_plain_words_stay_readable(self):
        self.assertEqual(markdown_text('Counter 42 works'),'Counter 42 works')
