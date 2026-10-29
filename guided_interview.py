"""Deterministic decisions around a model-driven, single-question interview."""
from copy import deepcopy
import re

import design_interview as d

CORE = ('purpose', 'audience', 'goals', 'pages', 'functionality')
VISUAL = ('theme', 'palette', 'layout')
QUESTIONS = {
    'purpose': 'What should this website help people do?',
    'audience': 'Who is this website mainly for?',
    'goals': 'What is the main action a visitor should take?',
    'pages': 'Which pages or sections should be included?',
    'functionality': 'Which interaction must work, and what should happen when someone uses it?',
    'theme': 'Which light or dark direction suits your website?',
    'palette': 'Which colour direction would you like?',
    'layout': 'How should the content be arranged?',
}


def next_field(state):
    for field in CORE:
        if not state['requirements'][field]['value'].strip():
            return field
    if state.get('design_confirmed'):
        for field in VISUAL:
            if not state['requirements'][field]['value'].strip():
                return field
    return None


def step(state):
    if state.get('summary_approval') or state.get('approved_brief'):
        return 'brief'
    if any(not state['requirements'][key]['value'].strip() for key in CORE):
        return 'idea'
    if not state.get('design_confirmed'):
        return 'design'
    return 'details' if next_field(state) else 'brief'


def valid_options(options):
    if not isinstance(options, list) or len(options) != 3:
        raise ValueError('The AI must provide three distinct suggestions for this decision.')
    seen_labels, seen_values = set(), set()
    for option in options:
        if not isinstance(option, dict):
            raise ValueError('An AI suggestion must include a label, answer and explanation.')
        for key, maximum in [('label', 110), ('value', 1200), ('reason', 500)]:
            if not isinstance(option.get(key), str) or not 1 <= len(option[key].strip()) <= maximum:
                raise ValueError('An AI suggestion is incomplete. Retry or use a custom answer.')
        label = re.sub(r'\s+', ' ', option['label']).strip().casefold()
        value = re.sub(r'\s+', ' ', option['value']).strip().casefold()
        if label in seen_labels or value in seen_values or label == 'custom answer':
            raise ValueError('AI suggestions must be distinct. Retry or use a custom answer.')
        seen_labels.add(label); seen_values.add(value)
    return deepcopy(options)


def question(state):
    field = next_field(state)
    if not field:
        return None
    for item in state.get('questions', []):
        if item['field'] == field:
            try:
                options = valid_options(item.get('options'))
            except ValueError:
                options = []
            return {'field': field, 'text': item['text'], 'options': options}
    return {'field': field, 'text': QUESTIONS[field], 'options': []}


def answer(state, field, value):
    current = next_field(state)
    if field != current:
        raise ValueError('That question has already been answered. Reload the current decision.')
    if not isinstance(value, str) or not value.strip() or len(value) > 1200:
        raise ValueError('Enter an answer containing 1 to 1,200 characters.')
    result = deepcopy(state)
    # A failed next-question request must not trap an already saved answer in a retry loop.
    result.update(pending=False, last_error=None)
    result = d.update_requirements(result, {field: value})
    result['answered_fields'] = list(dict.fromkeys([*result.get('answered_fields', []), field]))
    result['questions'] = []
    result = d.queue_message(result, d.FIELDS[field] + ': ' + value.strip())
    result['pending_answer'] = {'field': field, 'value': value.strip()}
    if result.get('design_confirmed') and next_field(result) is None:
        # All decisions are saved directly. No final model round-trip is needed just
        # to say the interview is complete, and its failure must not block approval.
        result.update(pending=False, last_error=None)
        result.pop('pending_answer', None)
    return result


def select_styles(state, names, acknowledge=False):
    from design_styles import compatibility
    if not names:
        raise ValueError('Choose at least one design style.')
    result = deepcopy(state)
    result.update(pending=False, last_error=None)
    result = d.update_requirements(result, {'selected_styles': ' + '.join(names)})
    if compatibility(names):
        if not acknowledge:
            raise ValueError('Review and acknowledge the trade-offs for this combination.')
        result['conflict_ack'] = d.digest(names)
    result['design_confirmed'] = True
    result['questions'] = []
    result['answered_fields'] = list(dict.fromkeys([*result.get('answered_fields', []), 'selected_styles']))
    if next_field(result):
        result = d.queue_message(result, 'My chosen design styles are ' + ' + '.join(names) + '. Continue with the next undecided design detail.')
    return result


def style_options(state):
    """Only real, validated model proposals can be labelled AI suggestions."""
    for rec in state.get('recommendations', []):
        if rec['field'] != 'selected_styles' or len(rec['alternatives']) != 2:
            continue
        values = [{'label': rec['value'], 'value': rec['value'], 'reason': rec['reason'], 'tradeoff': rec['tradeoff']}]
        values += [{'label': alt['value'], 'value': alt['value'], 'reason': alt['tradeoff'], 'tradeoff': alt['tradeoff']} for alt in rec['alternatives']]
        try:
            valid_options(values)
            for option in values:
                d.validate_response_style(option['value'])
        except ValueError:
            continue
        return values
    return []


def approve(state, draft):
    """The user explicitly approves the displayed summary and exact brief together."""
    result = deepcopy(state)
    if result['pending']:
        raise ValueError('Finish the current decision before approving the website brief.')
    # The final approval includes review of design-dependent decisions shown in this brief.
    result['style_recheck'] = []
    if not result.get('summary_approval'):
        result = d.confirm_summary(result)
    return d.approve_brief(d.edit_brief(result, draft))


def build_request(state, counter=False):
    d.build_spec(state)
    return {'workflow': 'interview_build', 'interview_id': state['id'],
            'revision': state['revision'], 'approval_hash': state['approved_brief']['hash'],
            'use_counter_checks': bool(counter)}
