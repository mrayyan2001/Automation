"""Plain-cell XLSX question definitions, choices, and static table rows."""
from datetime import date, datetime
from html import escape
from uuid import uuid4

from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

QUESTION_TYPES = {
    'Short text': 'TextField', 'Long text': 'TextArea', 'Number': 'IntegerField',
    'Date': 'DateField', 'Date and time': 'DateTimeField', 'Yes / No': 'YesNo',
    'Dropdown': 'Dropdown', 'Radio buttons': 'RadioButtons', 'Checkboxes': 'Checkbox',
    'Multiple choice dropdown': 'MultiSelectDropdown', 'Table': 'DataTable',
    'Multiple selection table': 'MultiSelectDataTable', 'Attachments': 'Attachment',
    'Repeatable group': 'RepeatableGroup', 'Description': 'DescriptionWidget',
    'Section heading': 'SectionWidget',
}
CHOICE_TYPES = {'YesNo', 'Dropdown', 'RadioButtons', 'Checkbox', 'MultiSelectDropdown'}
TABLE_TYPES = {'DataTable', 'MultiSelectDataTable'}
MULTI_TYPES = {'Checkbox', 'MultiSelectDropdown', 'MultiSelectDataTable', 'Attachment'}
QUESTION_HEADERS = [
    'Service name', 'Question key', 'Parent group key', 'Type', 'Label', 'Required',
    'Help text', 'Default answer', 'Hidden', 'Read-only', 'Maximum characters',
    'Minimum number', 'Maximum number', 'Number step', 'Text rows', 'Rich text',
    'Table columns', 'Group limit', 'Group output', 'Timezone', 'Earliest date',
    'Latest date', 'Validation pattern', 'Validation message', 'Show when question key',
    'Comparison', 'Expected answers',
]
CHOICE_HEADERS = ['Service name', 'Question key', 'Label', 'Saved value', 'Default', 'Disabled']
TABLE_HEADERS = ['Service name', 'Question key', 'Saved row value', 'Default'] + [f'Value {n}' for n in range(1, 21)]
CONDITION_HEADERS = ['Service name', 'Question key', 'Rule key', 'Parent rule key', 'Match',
                     'Leading question key', 'Comparison', 'Expected answers', 'Group parentheses']
SHEETS = {'Questions': QUESTION_HEADERS, 'Choices': CHOICE_HEADERS, 'Table rows': TABLE_HEADERS,
          'Conditions': CONDITION_HEADERS}


def add_question_sheets(workbook):
    for name, headers in SHEETS.items():
        sheet = workbook.create_sheet(name)
        sheet.sheet_view.showGridLines = False
        sheet.append(headers)
        sheet.freeze_panes = 'C2'
        sheet.row_dimensions[1].height = 42
        sheet.sheet_format.defaultRowHeight = 36 if name == 'Questions' else 24
        for column, title in enumerate(headers, 1):
            sheet.column_dimensions[get_column_letter(column)].width = 28 if column <= 5 else 24
            for row in range(1, 102):
                cell = sheet.cell(row, column)
                cell.number_format = '@'
                cell.font = Font(name='Arial', size=11, bold=row == 1, color='000000')
                cell.alignment = Alignment(vertical='center', horizontal='center' if row == 1 else 'left', wrap_text=True)
        table = Table(displayName=name.replace(' ', '') + 'Table', ref=f'A1:{get_column_letter(len(headers))}101')
        table.tableStyleInfo = TableStyleInfo(name='TableStyleLight1', showRowStripes=False)
        sheet.add_table(table)
        sheet.row_dimensions[2].height = 36 if name == 'Questions' else 24

    def dropdown(sheet_name, column, values, source_name):
        sheet = workbook[sheet_name]
        # Sources are text, outside the editable table and importer range.
        source_column = 102
        while sheet.cell(1, source_column).value is not None:
            source_column += 1
        letter = get_column_letter(source_column)
        for row, value in enumerate(values, 1):
            cell = sheet.cell(row, source_column, value)
            cell.data_type = 's'
        sheet.column_dimensions[letter].hidden = True
        from openpyxl.workbook.defined_name import DefinedName
        workbook.defined_names.add(DefinedName(source_name, attr_text=f"'{sheet_name}'!${letter}$1:${letter}${len(values)}"))
        validation = DataValidation(type='list', formula1=source_name, allow_blank=True)
        validation.showDropDown = False
        validation.showErrorMessage = True
        validation.error = 'Choose a value from the dropdown.'
        sheet.add_data_validation(validation)
        validation.add(f'{column}2:{column}1001')

    dropdown('Questions', 'D', list(QUESTION_TYPES), 'QuestionTypeOptions')
    for index, column in enumerate(('F', 'I', 'J', 'P')):
        dropdown('Questions', column, ['Yes', 'No'], f'QuestionBooleanOptions{index}')
    dropdown('Questions', 'S', ['CSV', 'JSON'], 'QuestionGroupOutputOptions')
    dropdown('Questions', 'Z', ['Equals', 'Does not equal', 'Includes', 'Does not include', 'Starts with', 'Ends with'], 'QuestionComparisonOptions')
    for column in ('E', 'F'):
        dropdown('Choices', column, ['Yes', 'No'], f'ChoiceBooleanOptions{column}')
    dropdown('Table rows', 'D', ['Yes', 'No'], 'TableDefaultOptions')
    dropdown('Conditions', 'E', ['All', 'Any'], 'ConditionMatchOptions')
    dropdown('Conditions', 'G', ['Equals', 'Does not equal', 'Includes', 'Does not include', 'Starts with', 'Ends with'], 'ConditionComparisonOptions')
    dropdown('Conditions', 'I', ['Yes', 'No'], 'ConditionParenthesesOptions')
    guide = workbook.create_sheet('Guide')
    guide.sheet_view.showGridLines = False
    rows = [
        ['Sheet / field', 'How to fill it'],
        ['Services', 'One service per row. Use the environment template and category dropdowns.'],
        ['Questions', 'One question per row. Service name must match Services. Question keys are unique within each service, for example name, department, items. Row order is question order.'],
        ['Type and label', 'Choose a type. The label also becomes the workflow input name. Labels must be unique within each service, including group questions.'],
        ['Choices', 'One choice per row. Use the same service name and question key. Label is displayed; Saved value is passed to the workflow (blank uses Label). Default and Disabled use Yes/No.'],
        ['Table columns', 'Enter column titles on separate lines in Questions (Alt+Enter). Up to 20 columns.'],
        ['Table rows', 'One data row per row. Saved row value must be unique for that question. Value 1 matches the first table column, Value 2 the second, and so on. Default uses Yes/No.'],
        ['Repeatable groups', 'Create a Repeatable group question. For child questions, enter its Question key in Parent group key. Children support their own choices and tables. Nested groups are not supported.'],
        ['Default answer', 'For multiple selections, use one saved value per line. Choices/Table rows can mark defaults instead; use one method. Numbers must be whole numbers.'],
        ['Earliest / Latest date', 'Leave blank for no limit; use YYYY-MM-DD or today+N / today-N for a relative limit. Date defaults use YYYY-MM-DD; date-time defaults use YYYY-MM-DDTHH:MM.'],
        ['Visibility', 'For a single rule, use Show when question key, Comparison, and Expected answers on Questions. Use Conditions instead for compound rules; do not use both methods on the same question.'],
        ['Conditions', 'One rule per row. Rule keys are unique per question. A group uses Match All/Any; its child rows use its Rule key as Parent rule key. Leave Parent rule key blank on the single root rule. Leaf rules use Leading question key, Comparison, and Expected answers (one value per line).'],
        ['Optional settings', 'Leave unused fields blank. Required, Hidden, Read-only, Rich text, Default, and Disabled accept Yes/No.'],
        ['Import', 'Upload the workbook, review and edit the imported services in the package draft, then save. Any invalid row prevents the entire import; errors identify the sheet and row.'],
        ['Limits', 'Up to 50 services, 100 questions per service/group, and 1,000 input rows per sheet. Static data only. Keep column headers; old Services-only templates still work.'],
    ]
    for row in rows:
        guide.append(row)
    guide.column_dimensions['A'].width = 28
    guide.column_dimensions['B'].width = 100
    for row in guide:
        for cell in row:
            cell.font = Font(name='Arial', size=11, bold=cell.row == 1)
            cell.alignment = Alignment(vertical='top', wrap_text=True)
        guide.row_dimensions[row[0].row].height = 55 if row[0].row > 1 else 28


def _rows(workbook, name, errors):
    if name not in workbook.sheetnames:
        return []
    expected = SHEETS[name]
    rows = workbook[name].iter_rows(max_row=1002, max_col=101)
    headers = [str(c.value).strip() if c.value is not None else '' for c in next(rows)]
    while headers and not headers[-1]:
        headers.pop()
    if headers != expected:
        raise ValueError(f'{name}: headers do not match. Download a new template and keep its headers.')
    result = []
    for number, cells in enumerate(rows, 2):
        if all(c.value is None or str(c.value).strip() == '' for c in cells):
            continue
        try:
            if number > 1001:
                raise ValueError('Use at most 1,000 input rows per sheet.')
            if any(c.value is not None for c in cells[len(expected):]):
                raise ValueError('A filled cell has no matching column header.')
            if any(c.data_type in ('f', 'e') for c in cells):
                raise ValueError('Use plain values, not formulas or Excel errors.')
            def text(value):
                if isinstance(value, (date, datetime)):
                    return value.isoformat()
                return str(value).strip() if value is not None else ''
            result.append((number, dict(zip(expected, (text(c.value) for c in cells)))))
        except ValueError as exc:
            errors.append({'sheet': name, 'row': number, 'message': str(exc)})
    return result


def _boolean(value):
    if value.casefold() in ('', 'no', 'false', '0'):
        return False
    if value.casefold() in ('yes', 'true', '1'):
        return True
    raise ValueError('Use Yes or No for boolean fields.')


def _integer(value, title, minimum=None):
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f'{title} must be a whole number.') from exc
    if minimum is not None and number < minimum:
        raise ValueError(f'{title} must be at least {minimum}.')
    return number


def _lines(value):
    return [v.strip() for v in value.splitlines() if v.strip()]


def _limit(value):
    if value.lower().startswith('today'):
        days = _integer(value[5:] or '0', 'Relative days')
        return {'limitType': 'RELATIVE', 'relativeLimit': {'questionId': None, 'dateUnit': 'DAYS_FROM_NOW', 'numberOfUnits': days, 'repeatableGroupInstanceId': None}}
    parsed = datetime.fromisoformat(value).date() if 'T' in value else date.fromisoformat(value)
    return {'limitType': 'SPECIFIC', 'specificLimit': parsed.isoformat()}


def import_question_sheets(workbook, services, errors):
    """Attach validated question trees, resolving workbook keys to fresh IDs."""
    service_map = {s['name'].casefold(): s for s in services}
    questions, locations, parents, visibility = {}, {}, {}, {}
    labels = set()

    def owner(row):
        service_name = row['Service name'].casefold()
        if service_name not in service_map:
            raise ValueError('Service name must match a valid row on Services.')
        if not row['Question key']:
            raise ValueError('Enter a Question key.')
        return service_name, row['Question key']

    for number, row in _rows(workbook, 'Questions', errors):
        try:
            key = owner(row)
            if key in questions:
                raise ValueError('Question key must be unique within the service.')
            kind = QUESTION_TYPES.get(row['Type'], row['Type'])
            if kind not in QUESTION_TYPES.values():
                raise ValueError('Choose a supported static question type.')
            if not row['Label'] or len(row['Label']) > 200:
                raise ValueError('Enter a question label (1–200 characters).')
            label_key = (key[0], row['Label'].casefold())
            if kind not in ('DescriptionWidget', 'SectionWidget') and label_key in labels:
                raise ValueError('Question labels must be unique within the service, including group questions.')
            config = {}
            for column, setting in [('Hidden', 'hidden'), ('Read-only', 'readOnly'), ('Rich text', 'isRTF')]:
                if row[column]:
                    config[setting] = _boolean(row[column])
            if row['Help text']:
                config['description'] = '<p>' + escape(row['Help text']).replace('\n', '<br>') + '</p>'
            for column, setting, minimum in [('Maximum characters', 'maxLength', 1), ('Minimum number', 'minValue', None), ('Maximum number', 'maxValue', None), ('Number step', 'step', 1), ('Text rows', 'numberOfRows', 1), ('Group limit', 'instanceLimit', 1)]:
                if row[column]:
                    config[setting] = _integer(row[column], column, minimum)
            if config.get('minValue') is not None and config.get('maxValue') is not None and config['minValue'] > config['maxValue']:
                raise ValueError('Minimum number must not exceed Maximum number.')
            for column, setting in [('Timezone', 'timezoneId'), ('Validation pattern', 'regex'), ('Validation message', 'regexCustomErrorMessage')]:
                if row[column]:
                    config[setting] = row[column]
            if row['Validation message']:
                config['regexErrorMessageType'] = 'CustomMessage'
            if row['Default answer']:
                if kind == 'IntegerField':
                    config['defaultAnswer'] = _integer(row['Default answer'], 'Default answer')
                elif kind == 'DateField':
                    value = row['Default answer']
                    config['defaultAnswer'] = (datetime.fromisoformat(value).date() if 'T' in value else date.fromisoformat(value)).isoformat()
                elif kind == 'DateTimeField':
                    config['defaultAnswer'] = datetime.fromisoformat(row['Default answer']).isoformat(timespec='minutes')
                elif kind in MULTI_TYPES:
                    config['defaultAnswers'] = _lines(row['Default answer'])
                else:
                    config['defaultAnswer'] = row['Default answer']
            for column, setting in [('Earliest date', 'min'), ('Latest date', 'max')]:
                if row[column]:
                    config[setting] = _limit(row[column])
            if kind == 'RepeatableGroup':
                config['outputFormat'] = row['Group output'] or 'CSV'
                if config['outputFormat'] not in ('CSV', 'JSON'):
                    raise ValueError('Group output must be CSV or JSON.')
            if kind in TABLE_TYPES:
                columns = _lines(row['Table columns'])
                if not 1 <= len(columns) <= 20:
                    raise ValueError('Tables need 1–20 column titles, one per line in Table columns.')
                config['questionMultiColumn'] = {'metaData': [{'displayId': str(uuid4()), 'displayName': title, 'datasetFieldType': None, 'selectionItems': None, 'dataValueField': False} for title in columns], 'data': []}
            q = {'id': str(uuid4()), 'type': kind, 'label': row['Label'], 'required': _boolean(row['Required']), 'config': config}
            if kind == 'RepeatableGroup':
                q['pageItems'] = []
            questions[key] = q
            if kind not in ('DescriptionWidget', 'SectionWidget'):
                labels.add(label_key)
            locations[key] = number
            parents[key] = row['Parent group key']
            if row['Show when question key']:
                visibility[key] = (row['Show when question key'], row['Comparison'] or 'Equals', _lines(row['Expected answers']))
        except ValueError as exc:
            errors.append({'sheet': 'Questions', 'row': number, 'message': str(exc)})

    for sheet in ('Choices', 'Table rows'):
        for number, row in _rows(workbook, sheet, errors):
            try:
                key = owner(row)
                q = questions.get(key)
                if q is None:
                    raise ValueError('Question key must match a valid row on Questions.')
                c = q['config']
                if sheet == 'Choices':
                    if q['type'] not in CHOICE_TYPES:
                        raise ValueError('Choices must reference a choice question.')
                    if not row['Label']:
                        raise ValueError('Enter a choice label.')
                    value = row['Saved value'] or row['Label']
                    options = c.setdefault('options', [])
                    if any(o['dataValue'] == value for o in options):
                        raise ValueError('Saved choice values must be unique within the question.')
                    option = {'dataValue': value, 'displayValue': row['Label'], 'disabled': _boolean(row['Disabled'])}
                    options.append(option)
                    c['staticDataValues'] = [o['dataValue'] for o in options]
                else:
                    if q['type'] not in TABLE_TYPES:
                        raise ValueError('Table rows must reference a table question.')
                    table = c['questionMultiColumn']
                    value = row['Saved row value']
                    if not value or any(r['dataValue'] == value for r in table['data']):
                        raise ValueError('Each table row needs a unique Saved row value.')
                    count = len(table['metaData'])
                    if any(row[f'Value {n}'] for n in range(count + 1, 21)):
                        raise ValueError('A table cell has no matching column title on Questions.')
                    table['data'].append({'dataValue': value, 'displayValue': [row[f'Value {n}'] for n in range(1, count + 1)]})
                    c['staticDataValues'] = [r['dataValue'] for r in table['data']]
                if _boolean(row['Default']):
                    if q['type'] in MULTI_TYPES:
                        defaults = c.setdefault('defaultAnswers', [])
                        if value not in defaults:
                            defaults.append(value)
                    else:
                        if c.get('defaultAnswer') is not None and c['defaultAnswer'] != value:
                            raise ValueError('Single-selection questions can have only one default.')
                        c['defaultAnswer'] = value
            except ValueError as exc:
                errors.append({'sheet': sheet, 'row': number, 'message': str(exc)})

    comparisons = {'Equals': 'EQUALS', 'Does not equal': 'NOT_EQUALS', 'Includes': 'INCLUDES', 'Does not include': 'NOT_INCLUDES', 'Starts with': 'STARTS_WITH', 'Ends with': 'ENDS_WITH'}
    for key, q in questions.items():
        try:
            parent = questions.get((key[0], parents[key])) if parents[key] else None
            if parents[key] and (parent is None or parent['type'] != 'RepeatableGroup' or q['type'] == 'RepeatableGroup'):
                raise ValueError('Parent group key must reference a Repeatable group; nested groups are not supported.')
            if q['type'] in CHOICE_TYPES and q['type'] != 'YesNo' and not q['config'].get('options'):
                raise ValueError('Add at least one choice on Choices.')
            if q['type'] in TABLE_TYPES and not q['config']['questionMultiColumn']['data']:
                raise ValueError('Add at least one row on Table rows.')
            values = set(q['config'].get('staticDataValues', []))
            if q['type'] == 'YesNo' and not values:
                values = {'true', 'false'}
            defaults = q['config'].get('defaultAnswers', []) if q['type'] in MULTI_TYPES else [q['config']['defaultAnswer']] if q['config'].get('defaultAnswer') is not None else []
            if q['type'] in CHOICE_TYPES | TABLE_TYPES and any(v not in values for v in defaults):
                raise ValueError('Default answers must match saved choice/table values.')
            if key in visibility:
                leader_key, comparison, expected = visibility[key]
                leader = questions.get((key[0], leader_key))
                if leader is None or leader is q:
                    raise ValueError('Show when question key must reference another question in this service.')
                if comparison not in comparisons:
                    raise ValueError('Choose a supported Comparison.')
                operator = comparisons[comparison]
                q['config']['visibilityCondition'] = {'leadingQuestionId': leader['id'], 'leadingQuestionExpectedAnswers': expected, 'expression': {'operator': operator, 'withParentheses': False, 'left': {'values': [], 'type': 'QUESTION_ANSWER', 'label': leader['label'], 'valueReference': leader['id'], 'fieldType': None, 'value': None}, 'right': {'values': expected, 'type': 'QUESTION_OPTION' if leader['type'] in CHOICE_TYPES else 'STRING', 'label': expected[0] if expected else None, 'valueReference': None, 'fieldType': None, 'value': expected[0] if expected else None}}}
            if parent:
                parent['pageItems'].append(q)
            else:
                service_map[key[0]].setdefault('questions', []).append(q)
        except ValueError as exc:
            errors.append({'sheet': 'Questions', 'row': locations[key], 'message': str(exc)})
    for key, q in questions.items():
        if q['type'] == 'RepeatableGroup' and not q['pageItems']:
            errors.append({'sheet': 'Questions', 'row': locations[key], 'message': 'Add child questions using Parent group key.'})
    import_conditions(workbook, questions, visibility, errors)
    return {name: min(number for key, number in locations.items() if key[0] == name)
            for name in {key[0] for key in locations}}


def import_conditions(workbook, questions, simple_visibility, errors):
    """Resolve a visible rule tree without storing JSON in spreadsheet cells."""
    rules = {}
    comparisons = {'Equals': 'EQUALS', 'Does not equal': 'NOT_EQUALS', 'Includes': 'INCLUDES',
                   'Does not include': 'NOT_INCLUDES', 'Starts with': 'STARTS_WITH', 'Ends with': 'ENDS_WITH'}
    for number, row in _rows(workbook, 'Conditions', errors):
        try:
            key = (row['Service name'].casefold(), row['Question key'])
            if key not in questions:
                raise ValueError('Service name and Question key must match a valid question.')
            if key in simple_visibility:
                raise ValueError('Use Conditions or the visibility columns on Questions, not both.')
            if not row['Rule key'] or row['Rule key'] in rules.get(key, {}):
                raise ValueError('Rule key must be nonempty and unique within the question.')
            parent = row['Parent rule key']
            if row['Match']:
                if row['Match'] not in ('All', 'Any') or row['Leading question key'] or row['Comparison'] or row['Expected answers']:
                    raise ValueError('Groups use Match All/Any; leave leading question, comparison, and answers blank.')
                expression = {'operator': 'AND' if row['Match'] == 'All' else 'OR',
                              'withParentheses': _boolean(row['Group parentheses'])}
            else:
                leader = questions.get((key[0], row['Leading question key']))
                if leader is None or leader is questions[key]:
                    raise ValueError('Leading question key must reference another question in this service.')
                operator = comparisons.get(row['Comparison'])
                if operator is None:
                    raise ValueError('Choose a supported Comparison.')
                values = _lines(row['Expected answers'])
                choice_label = next((option['displayValue'] for option in leader['config'].get('options', [])
                                     if values and option['dataValue'] == values[0]), values[0] if values else None)
                expression = {'operator': operator, 'withParentheses': _boolean(row['Group parentheses']),
                              'left': {'values': [], 'type': 'QUESTION_ANSWER', 'label': leader['label'],
                                       'valueReference': leader['id'], 'fieldType': None, 'value': None},
                              'right': {'values': values, 'type': 'QUESTION_OPTION' if leader['type'] in CHOICE_TYPES else 'STRING',
                                        'label': choice_label if leader['type'] in CHOICE_TYPES else None,
                                        'valueReference': None, 'fieldType': None, 'value': values[0] if values else None}}
            rules.setdefault(key, {})[row['Rule key']] = (parent, expression, number)
        except ValueError as exc:
            errors.append({'sheet': 'Conditions', 'row': number, 'message': str(exc)})
    for key, nodes in rules.items():
        number = min(v[2] for v in nodes.values())
        try:
            roots = [name for name, (parent, _, _) in nodes.items() if not parent]
            if len(roots) != 1:
                raise ValueError('Each question needs exactly one root rule (blank Parent rule key).')
            visited = set()

            def build(name, depth=0):
                if depth > 20 or name in visited:
                    raise ValueError('Condition groups contain a cycle or are too deeply nested.')
                visited.add(name)
                _, expression, _ = nodes[name]
                children = [child for child, (parent, _, _) in nodes.items() if parent == name]
                if expression['operator'] in ('AND', 'OR'):
                    if len(children) < 2:
                        raise ValueError('All/Any groups need at least two child rules.')
                    expressions = [build(child, depth + 1) for child in children]
                    result = expressions[0]
                    for child in expressions[1:]:
                        result = {**expression, 'left': result, 'right': child}
                    return result
                if children:
                    raise ValueError('Only All/Any groups can contain child rules.')
                return expression

            expression = build(roots[0])
            if len(visited) != len(nodes):
                raise ValueError('Some rules refer to a missing parent group or form a cycle.')
            questions[key]['config']['visibilityCondition'] = {'leadingQuestionExpectedAnswers': [], 'expression': expression}
        except ValueError as exc:
            errors.append({'sheet': 'Conditions', 'row': number, 'message': str(exc)})
