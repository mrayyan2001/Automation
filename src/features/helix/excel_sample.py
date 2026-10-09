"""Flatten the static service sample into editable workbook input rows."""
from copy import deepcopy
from html.parser import HTMLParser
from uuid import uuid4

from openpyxl.styles import Alignment, Font

from features.helix.excel_questions import QUESTION_TYPES, MULTI_TYPES, TABLE_TYPES, SHEETS


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('p', 'div'):
            self.parts.append('\n')


def _text(value):
    parser = _PlainText()
    parser.feed(value or '')
    return ''.join(parser.parts).strip()


def fill_excel_sample(workbook, spec, sample):
    sample = deepcopy(sample)
    # The reference contains a dynamic-only single dropdown. Use its static
    # checkbox choices for a connector-free example of that supported type.
    choice = next(q for q in sample['questions'] if q['type'] == 'Checkbox')
    sample['questions'].append({'id': str(uuid4()), 'type': 'Dropdown',
                               'label': 'Static single choice dropdown', 'required': False,
                               'config': {'options': deepcopy(choice['config']['options']),
                                          'defaultAnswer': choice['config']['options'][0]['dataValue']}})
    template = next(t for t in spec['templates'] if t['id'] == sample['templateId'])
    category_paths = dict(spec['categories'])

    def write(name, number, values):
        sheet = workbook[name]
        headers = spec['headers'] if name == 'Services' else SHEETS[name]
        for column, header in enumerate(headers, 1):
            if header not in values or values[header] is None:
                continue
            cell = sheet.cell(number, column, values[header])
            if isinstance(values[header], str):
                cell.data_type = 's'

    service_row = {'Service name': sample['name'], 'Service template': template['name'], 'Tags': ', '.join(sample.get('tags', []))}
    for index, identifier in enumerate(sample.get('categoryIds', []), 1):
        service_row[f'Category {index}'] = category_paths[identifier]
    for header, (template_id, field_id) in spec['columns'].items():
        if template_id == template['id']:
            service_row[header] = sample['fieldValues'].get(field_id, '')
    write('Services', 2, service_row)
    workbook['Services'].row_dimensions[2].height = 45

    flattened = []
    def flatten(items, parent=None):
        for q in items:
            flattened.append((q, parent))
            if q.get('pageItems'):
                flatten(q['pageItems'], q['id'])
    flatten(sample['questions'])
    keys = {q['id']: f'q{index:02}' for index, (q, _) in enumerate(flattened, 1)}
    type_names = {value: name for name, value in QUESTION_TYPES.items()}
    comparisons = {'EQUALS': 'Equals', 'NOT_EQUALS': 'Does not equal', 'INCLUDES': 'Includes',
                   'NOT_INCLUDES': 'Does not include', 'STARTS_WITH': 'Starts with', 'ENDS_WITH': 'Ends with'}
    counters = {'Choices': 2, 'Table rows': 2, 'Conditions': 2}
    def append(name, values):
        write(name, counters[name], values)
        counters[name] += 1

    def limit(value):
        if not value or value.get('limitType') == 'NO_LIMIT':
            return ''
        if value.get('limitType') == 'SPECIFIC':
            return value['specificLimit']
        return f"today{value['relativeLimit']['numberOfUnits']:+d}"

    for number, (q, parent) in enumerate(flattened, 2):
        c = q.get('config', {})
        owner = {'Service name': sample['name'], 'Question key': keys[q['id']]}
        row = {**owner, 'Parent group key': keys[parent] if parent else '',
               'Type': type_names[q['type']], 'Label': q['label'],
               'Required': 'Yes' if q.get('required') else 'No', 'Help text': _text(c.get('description'))}
        for header, setting in [('Hidden', 'hidden'), ('Read-only', 'readOnly'), ('Rich text', 'isRTF')]:
            if setting in c:
                row[header] = 'Yes' if c[setting] else 'No'
        for header, setting in [('Maximum characters', 'maxLength'), ('Minimum number', 'minValue'),
                                ('Maximum number', 'maxValue'), ('Number step', 'step'), ('Text rows', 'numberOfRows'),
                                ('Group limit', 'instanceLimit'), ('Group output', 'outputFormat'), ('Timezone', 'timezoneId'),
                                ('Validation pattern', 'regex'), ('Validation message', 'regexCustomErrorMessage')]:
            row[header] = c.get(setting)
        row['Earliest date'] = limit(c.get('min'))
        row['Latest date'] = limit(c.get('max'))
        defaults = c.get('defaultAnswers', []) if q['type'] in MULTI_TYPES else [c['defaultAnswer']] if c.get('defaultAnswer') is not None else []
        if not c.get('options') and q['type'] not in TABLE_TYPES:
            row['Default answer'] = '\n'.join(str(v) for v in defaults)
        for option in c.get('options', []):
            append('Choices', {**owner, 'Label': option['displayValue'], 'Saved value': option['dataValue'],
                               'Default': 'Yes' if option['dataValue'] in defaults else 'No',
                               'Disabled': 'Yes' if option.get('disabled') else 'No'})
        if q['type'] in TABLE_TYPES:
            table = c['questionMultiColumn']
            row['Table columns'] = '\n'.join(col['displayName'] for col in table['metaData'])
            for data in table['data']:
                append('Table rows', {**owner, 'Saved row value': data['dataValue'],
                                     'Default': 'Yes' if data['dataValue'] in defaults else 'No',
                                     **{f'Value {index}': value for index, value in enumerate(data['displayValue'], 1)}})
            workbook['Questions'].row_dimensions[number].height = max(36, 16 * len(table['metaData']) + 8)
        write('Questions', number, row)
        condition = c.get('visibilityCondition')
        if condition:
            counter = [0]
            def condition_rows(expression, parent_key=''):
                counter[0] += 1
                rule_key = f'r{counter[0]:02}'
                values = {**owner, 'Rule key': rule_key, 'Parent rule key': parent_key,
                          'Group parentheses': 'Yes' if expression.get('withParentheses') else 'No'}
                if expression['operator'] in ('AND', 'OR'):
                    values['Match'] = 'All' if expression['operator'] == 'AND' else 'Any'
                    append('Conditions', values)
                    condition_rows(expression['left'], rule_key)
                    condition_rows(expression['right'], rule_key)
                else:
                    right = expression['right']
                    expected = right.get('values') or ([right['value']] if right.get('value') is not None else [])
                    values.update({'Leading question key': keys[expression['left']['valueReference']],
                                   'Comparison': comparisons[expression['operator']],
                                   'Expected answers': '\n'.join(str(v) for v in expected)})
                    append('Conditions', values)
            condition_rows(condition['expression'])
    guide = workbook['Guide']
    number = guide.max_row + 1
    guide.cell(number, 1, 'Filled sample')
    guide.cell(number, 2, 'The static reference cases are prefilled. The extra single-choice dropdown uses the reference checkbox values v1/v2. Import this workbook directly or edit its cells first. Original compound visibility rules are on Conditions; no connectors or dynamic lookups are used.')
    for cell in guide[number]:
        cell.font = Font(name='Arial', size=11)
        cell.alignment = Alignment(vertical='top', wrap_text=True)
    guide.row_dimensions[number].height = 70
