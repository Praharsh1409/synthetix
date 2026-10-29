"""A reviewable visual-design proposal, bound to the user's current requirements."""
from copy import deepcopy
import json
import re

from artifact_io import public_error

TEXT_FIELDS = {
    'concept': ('Visual idea', 240),
    'composition': ('Layout and hierarchy', 600),
    'typography': ('Typography', 350),
    'surfaces': ('Colour, surfaces and depth', 350),
    'signature_detail': ('Distinctive detail', 350),
}
ANCHORS = ('selected_styles', 'theme', 'palette')
MOTION_POLICY = (
    'Implement only the approved motion below. Respect prefers-reduced-motion: remove '
    'travel and delays, keep content visible and controls usable. Content must be visible '
    'when JavaScript or IntersectionObserver is unavailable. Use short opacity/transform '
    'transitions; never delay state changes, steal focus, animate continuously or hijack scrolling.'
)
GENERATION_DESIGN_RULES = (
    'Execute the approved visual plan as actual CSS, layout and interactions, not comments. '
    'Give the page a recognisable identity tied to its subject. Decide what deserves visual emphasis; '
    'use deliberate grouping, varied proportions, a coherent type scale and consistent spacing tokens. '
    'Avoid a tiny unstyled form floating in an empty viewport, or equal cards for every element. '
    'Minimal does not mean unfinished. Use meaningful inline SVG or CSS details when the subject '
    'benefits; decoration must not imply extra features or fabricated data. Use the selected palette '
    'for clear surface and text roles. Keep the main user action easy to find and phone layouts usable. '
    'Implement polished hover, focus, press, empty, validation and success states. '
    'When motion is approved, implement the specified event-driven animations and reduced-motion '
    'fallback. A short entrance may establish hierarchy; user actions should produce immediate '
    'feedback. Do not reanimate all existing content after every update. Preserve keyboard focus '
    'when updating lists, and compute progress from real state. Do not hide content pending an '
    'observer, use fake loading, force scroll scenes on a short tool, or add infinite ambient effects. '
    'A user request for no motion overrides animation suggestions. Testable functionality, exact '
    'control labels and the approved requirements take priority over presentation details.'
    ' Use valid comma-separated CSS font stacks: for sans-serif, use '
    'font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif. '
    'Never copy an unpunctuated list of font names from prose into CSS. '
    'For a Bento UI tool, implement actual grid regions rather than a full-width form and a loose '
    'percentage at the far edge. Use a bounded workspace around 1040-1200px with balanced gutters, '
    'a clear title around 28-36px, a dominant working panel and a smaller supporting panel. '
    'Use a CSS grid such as minmax(0, 2fr) minmax(240px, 1fr), with a deliberate mobile stack. '
    'This is a structural guide, not a template: adapt it to explicit layout requirements and the '
    'actual content. Keep the first meaningful empty state inside its panel, not floating in a '
    'blank viewport. Buttons and inputs need useful padding and touch targets around 44px. '
    'Give the subject-specific detail real visual presence using CSS or inline SVG. A generic '
    'button glow is not a distinctive visual identity. Use dark ink on bright accent buttons when '
    'white would have insufficient contrast; ordinary text needs about 4.5:1 contrast.'
)
BENTO_STRUCTURE = '''
When implementing the selected Bento UI, use a concrete structural foundation like this,
adapted to the approved content. Set the variables from the chosen theme and palette.
Do not copy example comments or placeholder text into the final interface.
CSS foundation:
body { margin:0; background:var(--page-bg); color:var(--ink);
       font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
* { box-sizing:border-box; }
.app-shell { width:min(1120px,calc(100% - 48px)); margin:40px auto; }
.app-heading { display:flex; justify-content:space-between; align-items:end; gap:24px; margin-bottom:28px; }
.app-heading h1 { font-size:clamp(28px,3vw,36px); line-height:1.1; letter-spacing:-.035em; margin:0; }
.bento { display:grid; grid-template-columns:minmax(0,2fr) minmax(260px,1fr); gap:20px; align-items:start; }
.panel { min-width:0; background:var(--panel-bg); border:1px solid var(--line); border-radius:14px; padding:24px; }
.working-panel { grid-column:1; } .support-panel { grid-column:2; }
button,input,select { font:inherit; min-height:44px; }
:focus-visible { outline:3px solid var(--accent); outline-offset:3px; }
@media(max-width:720px) { .app-shell { width:calc(100% - 32px); margin:24px auto; }
 .bento { grid-template-columns:1fr; } .working-panel,.support-panel { grid-column:1; }
 .app-heading { align-items:start; flex-direction:column; } .panel { padding:20px; } }
Use a meaningful panel title and main action. Put real progress in the supporting panel,
not a loose percentage at the page edge. Place the list or main content in the working panel.
For a task planner, use a small notebook/study composition in its empty state and a real
progress fill; do not add fake tasks. Adapt this foundation for other subjects and layouts.
'''


def generation_guidance(prompt):
    selected = re.search(r'^Design styles \(primary first\):\s*(.+)$', prompt, re.M)
    return GENERATION_DESIGN_RULES + (BENTO_STRUCTURE if selected and 'Bento UI' in selected.group(1).split(' + ') else '')


def fingerprint(state):
    from design_interview import digest, requirement_values
    return digest(requirement_values(state))


def motion_allowed(state):
    values = state['requirements']
    text = ' '.join(values[key]['value'] for key in ('interactions', 'accessibility', 'exclusions'))
    return not re.search(r'\b(no animations?|no motion|without animations?|without motion|static only|motion[- ]free)\b', text, re.I)


def validate_plan(value, state):
    expected = set(TEXT_FIELDS) | {'anchors', 'motion'}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError('The AI design proposal has an invalid structure. Your original requirements were kept.')
    anchors = {key: state['requirements'][key]['value'] for key in ANCHORS}
    if value['anchors'] != anchors:
        raise ValueError('The design proposal changed your selected style, theme or palette. It was not applied.')
    result = {'anchors': anchors}
    for key, (_, limit) in TEXT_FIELDS.items():
        text = value[key]
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= limit:
            raise ValueError('The AI returned an empty or oversized design recommendation.')
        result[key] = text.strip()
    motions = value['motion']
    if not isinstance(motions, list) or len(motions) > 3 or (motions and not motion_allowed(state)):
        raise ValueError('The animation proposal conflicts with the supported limits or your motion preference.')
    result['motion'] = []
    for item in motions:
        if not isinstance(item, dict) or set(item) != {'trigger', 'effect', 'duration_ms'}:
            raise ValueError('The AI returned an invalid animation proposal.')
        if any(not isinstance(item[key], str) or not 1 <= len(item[key].strip()) <= 180 for key in ('trigger', 'effect')):
            raise ValueError('Describe each animation and the event that triggers it.')
        if type(item['duration_ms']) is not int or not 80 <= item['duration_ms'] <= 600:
            raise ValueError('Use bounded animation durations between 80 and 600 milliseconds.')
        result['motion'].append(dict(item))
    return result


def current(state):
    record = state.get('visual_refinement')
    if not isinstance(record, dict) or record.get('requirements_hash') != fingerprint(state):
        return None
    if record.get('status') == 'ready':
        try:
            validate_plan(record.get('plan'), state)
        except ValueError:
            return None
    elif record.get('status') not in ('failed', 'skipped'):
        return None
    return record


def proposal_text(state):
    record = current(state)
    if not record or record['status'] != 'ready':
        return ''
    plan = record['plan']
    lines = ['Visual execution plan (AI proposal, reviewed as part of this brief)',
             'The project requirements above take priority. This plan adds presentation details, not features or business claims.']
    lines += [label + ': ' + plan[key] for key, (label, _) in TEXT_FIELDS.items()]
    if plan['motion']:
        lines.append('Purposeful motion:')
        lines += [f"- {item['trigger']}: {item['effect']} ({item['duration_ms']} ms)." for item in plan['motion']]
        lines.append(MOTION_POLICY)
    else:
        lines.append('Motion: no animated entrances or animated interactions; keep state changes immediate.')
    return '\n'.join(lines)


def record_result(state, status, plan=None, error=None):
    from design_interview import invalidate, now
    result = deepcopy(state)
    invalidate(result)
    result['visual_refinement'] = {'requirements_hash': fingerprint(state), 'status': status,
                                   'at': now(), 'plan': plan, 'error': error}
    return result


def failed(state, error):
    return record_result(state, 'failed', error=public_error(error))


def skip(state):
    return record_result(state, 'skipped')


def refine(state, ask=None):
    from design_interview import blockers, render_brief, requirement_values
    from nebius_tasks import ask_json
    missing = [item for item in blockers(state) if not item.startswith('Review style-dependent decisions:')]
    if missing:
        raise ValueError('Finish the important requirements before refining the visual design.')
    requirements = requirement_values(state)
    system = (
        'Act as a product art director. Refine the presentation of this specific website before coding. '
        'The user has already chosen the purpose, audience, functionality, styles, theme and palette. '
        'Those are fixed constraints. Do not replace them, add features/pages, introduce sample tasks '
        'or fake statistics, invent imagery/business claims, or change data persistence. '
        'Choose one visual organising idea drawn from the actual subject; describe a visible motif or '
        'composition, not merely the product name, chosen colours and list of features. '
        'Return concrete implementation decisions, not adjectives such as premium. '
        'For an app, prioritise its main task and meaningful empty states, a deliberate grid with '
        'different spans where useful, readable density, and computed rather than decorative metrics. '
        'For a landing page, establish a distinct opening composition and varied section rhythm, '
        'confident editorial hierarchy and inline subject-specific artwork only where useful. '
        'Do not turn a working tool into a marketing page. Minimalism still needs hierarchy and identity. '
        'Explain how to apply the chosen palette to backgrounds, surfaces, text and the main action. '
        'Specify a confident type scale: app titles usually 28-36px and body 14-18px; respect explicit '
        'user sizes. Specify spacing, responsive changes, hover/press/focus, empty and error states. '
        'The signature_detail must be one subject-specific visual element with a clear shape or '
        'composition; a generic hover glow, plain cards or a repetition of functionality is not a '
        'signature. Use a real grid and balanced panels when Bento UI is selected. Avoid glows. '
        'Provide readable colour contrast, including dark text on bright accent-filled buttons if needed. '
        'Use compatible system font stacks, CSS shapes or inline SVG; no external assets or packages. '
        'If motion_allowed is true, propose two or three short meaningful animations tied to actual '
        'events: entry, user actions, filtering, progress or disclosure. Choose only events the brief '
        'supports. A short page needs no forced scroll reveal. Do not hide content by default or '
        'delay clicks/data changes. Respect reduced motion. If motion_allowed is false, return motion=[]. '
        'Do not recommend constant ambient motion, particles, scroll hijacking or decoration unrelated '
        'to the subject. Respect user-selected bold styles rather than forcing a universal minimal theme. '
        'Return exactly anchors (copy selected_styles, theme and palette strings unchanged from input), '
        'concept (under 240 characters), composition (under 600), typography (under 350), surfaces '
        '(under 350), signature_detail (under 350), motion (up to three objects with trigger, effect '
        'strings under 180 characters and duration_ms integer between 80 and 600). No HTML or code.'
    )
    schema = {**{key:'' for key in TEXT_FIELDS},
              'anchors': {key: requirements[key] for key in ANCHORS},
              'motion': [{'trigger':'', 'effect':'', 'duration_ms':180}] if motion_allowed(state) else []}
    context = {
        'initial_idea': state['initial_request'], 'requirements': requirements,
        'motion_allowed': motion_allowed(state),
        'required_json_shape': schema,
    }
    request = ask or ask_json
    reply = request(system, json.dumps(context))
    try:
        plan = validate_plan(reply, state)
    except ValueError as error:
        # One bounded schema correction; unusable output never reaches the brief.
        reply = request(system + ' Correct the JSON schema of the previous proposal. '
                        'Return the required_json_shape object at the top level, not inside another key. '
                        'Fill all empty text fields with concise project-specific decisions. '
                        'Use exactly the anchors object supplied in required_json_shape. '
                        'Preserve all field limits; remove extra properties.',
                        json.dumps({**context, 'invalid_proposal':reply, 'validation_error':str(error)}))
        plan = validate_plan(reply, state)
    result = record_result(state, 'ready', plan=plan)
    if len(render_brief(result)) > 12000:
        raise ValueError('The combined brief is too long. Shorten the requirements or continue without refinement.')
    return result
