"""Questionnaire definitions matching the Helix service export format."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

TYPES = json.loads(Path(__file__).with_name('question_types.json').read_text())
WIDGETS = {'DescriptionWidget', 'SectionWidget'}


def build_questionnaire(questions: list, workflow: dict, name: str, now: int) -> dict | None:
    if not questions:
        return None
    inputs, names, ids = [], set(), set()

    def build(items, nested=False):
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError('Use at most 100 questions per group.')
        result = []
        for spec in items:
            if not isinstance(spec, dict) or spec.get('type') not in TYPES:
                raise ValueError('Choose a supported question type.')
            kind = spec['type']
            label = spec.get('label', '')
            if not isinstance(label, str) or not label.strip() or len(label) > 200:
                raise ValueError('Each question needs a label (1–200 characters).')
            label = label.strip()
            if kind not in WIDGETS and label.casefold() in names:
                raise ValueError('Each question label must be unique.')
            if kind not in WIDGETS:
                names.add(label.casefold())
            q = deepcopy(TYPES[kind]['question'])
            config = spec.get('config', {})
            if not isinstance(config, dict):
                raise ValueError('Question settings must be a JSON object.')
            q.update(deepcopy(config))
            q['type'] = kind
            q['id'] = spec.get('id') or str(uuid4())
            if not isinstance(q['id'], str) or q['id'] in ids:
                raise ValueError('Question IDs must be unique text values.')
            ids.add(q['id'])
            q.pop('template', None)
            q.pop('processInputId', None)
            q['title' if kind == 'SectionWidget' else 'label'] = label
            if kind not in WIDGETS:
                if not isinstance(spec.get('required', False), bool):
                    raise ValueError('Question required must be true or false.')
                q['required'] = spec.get('required', False)
                if not nested:
                    param = deepcopy(TYPES[kind]['input'])
                    param.update(id=536870912 + len(inputs), name=label, owner=None,
                                 lastChangedBy=None, lastUpdateTime=now)
                    q['processInputId'] = param['id']
                    inputs.append(param)
                else:
                    q['processInputId'] = None
            if 'options' in spec:
                options = spec['options']
                if not isinstance(options, list) or any(not isinstance(v, str) or not v.strip() for v in options):
                    raise ValueError('Question choices must be a list of nonempty text values.')
                q['options'] = [{'dataValue': v, 'displayValue': v, 'disabled': False} for v in options]
                q['staticDataValues'] = options
            if kind == 'RepeatableGroup':
                if nested:
                    raise ValueError('Repeatable groups cannot contain another repeatable group.')
                q['pageItems'] = build(spec.get('pageItems', config.get('pageItems', [])), True)
                if not q['pageItems']:
                    raise ValueError('Add at least one question to a repeatable group.')
            result.append(q)
        return result

    items = build(questions)
    workflow['inputParams'] = inputs
    group = str(uuid4())
    representation = {'id': str(uuid4().int % 10**14), 'guid': None, 'createDate': None,
                      'modifiedDate': None, 'rxId': None, 'summary': None, 'serviceRevisionId': None,
                      'workflowId': workflow['guid'], 'questionnaireGroupId': group, 'name': name,
                      'bulkRequestedForUserLimit': 1, 'importMode': None,
                      'pages': [{'id': str(uuid4()), 'externalId': None, 'perUser': False,
                                 'title': '', 'pageItems': items}],
                      'actions': [], 'showActions': False, 'useDefaultLanguage': False}
    return {'jsonRepresentation': json.dumps(representation), 'version': 0, 'name': name,
            'questionnaireGroupId': group, 'bulkRequestedForUserLimit': 1}
