import unittest
import re
from pathlib import Path
from studio_examples import example_html
from browser_safety import isolated_page, load_document, empty_report

def luminance(value):
    rgb=[int(value[i:i+2],16)/255 for i in (0,2,4)]
    rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(a*b for a,b in zip(rgb,[.2126,.7152,.0722]))

def contrast(first,second):
    hi,lo=sorted([luminance(first),luminance(second)],reverse=True)
    return (hi+.05)/(lo+.05)

class GraphiteThemeTests(unittest.TestCase):
    def test_motion_and_control_states_in_isolated_browser(self):
        root=Path(__file__).resolve().parents[1]
        css=(root/'site.css').read_text(encoding='utf-8')+(root/'graphite.css').read_text(encoding='utf-8')
        source='<html><style>'+css+'</style><div class="st-key-workbench"><div class="stButton"><button kind="primary">Build</button><button disabled>Unavailable</button></div></div></html>'
        with isolated_page(empty_report()) as page:
            page.emulate_media(reduced_motion='no-preference')
            load_document(page,source)
            button=page.get_by_role('button',name='Build',exact=True)
            self.assertEqual(button.evaluate('(e)=>getComputedStyle(e).color'),'rgb(16, 17, 20)')
            button.hover()
            page.wait_for_timeout(240)
            self.assertEqual(button.evaluate('(e)=>getComputedStyle(e).backgroundColor'),'rgb(138, 162, 255)')
            button.focus()
            self.assertEqual(button.evaluate('(e)=>getComputedStyle(e).outlineWidth'),'3px')
            disabled=page.get_by_role('button',name='Unavailable',exact=True)
            self.assertEqual(disabled.evaluate('(e)=>getComputedStyle(e).opacity'),'1')
            self.assertEqual(disabled.evaluate('(e)=>getComputedStyle(e).color'),'rgb(168, 175, 189)')
            page.emulate_media(reduced_motion='reduce')
            self.assertEqual(button.evaluate('(e)=>getComputedStyle(e).transitionDuration'),'0s')
            self.assertEqual(page.locator('.st-key-workbench').evaluate('(e)=>getComputedStyle(e).animationName'),'none')

    def test_text_and_control_tokens_meet_contrast_targets(self):
        css=(Path(__file__).resolve().parents[1]/'graphite.css').read_text(encoding='utf-8')
        tokens=dict(re.findall(r'--([\w-]+):#([0-9A-Fa-f]{6})',css))
        for background in [tokens[key] for key in ['color-bg','color-surface','color-hover']]:
            for text in [tokens[key] for key in ['color-text','color-secondary-text']]:
                self.assertGreaterEqual(contrast(text,background),4.5)
            for boundary in [tokens['color-control'],tokens['accent-hover']]:
                self.assertGreaterEqual(contrast(boundary,background),3)
        for action in [tokens['color-accent'],tokens['accent-hover']]:
            self.assertGreaterEqual(contrast(tokens['action-ink'],action),4.5)
        for text,background in [('88D3A1','183025'),('F1C775','352B18'),('FFAAA7','382121')]:
            self.assertGreaterEqual(contrast(text,background),4.5)

    def test_bright_preview_keeps_its_authored_palette(self):
        document=example_html('Photographer portfolio','Editorial')
        self.assertIn('background:#eee9df;color:#242824',document)
        self.assertNotIn('#101114',document)
        self.assertNotIn('#6B8AFF',document)
        self.assertNotIn('filter:invert',document)
