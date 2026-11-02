import unittest
from intent_checks import check_intent
from studio_examples import EXAMPLES, STYLES, example_html

class StudioExamplesTests(unittest.TestCase):
    def test_each_example_and_style_filters_real_browser_content(self):
        for name,item in EXAMPLES.items():
            for style in STYLES:
                with self.subTest(example=name,style=style):
                    checks=[{'action':'click','by':'css','selector':'[data-filter="'+item['options'][1]+'"]'},
                            {'action':'expect_text','by':'css','selector':'#result','text':'Showing 1 item · '+item['options'][1]},
                            {'action':'expect_visible','by':'css','selector':'[data-category]:not([hidden])'},
                            {'action':'expect_text','by':'css','selector':'[data-category]:not([hidden]) h2','text':item['labels'][0]}]
                    result=check_intent(example_html(name,style),checks)
                    self.assertTrue(result['passed'],result)

    def test_missing_handler_demo_fails_same_assertion(self):
        checks=[{'action':'click','by':'css','selector':'[data-filter="Landscapes"]'},
                {'action':'expect_text','by':'css','selector':'#result','text':'Showing 1 item · Landscapes'}]
        self.assertFalse(check_intent(example_html('Photographer portfolio',broken=True),checks)['passed'])
