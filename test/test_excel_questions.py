"""Exercise XLSX question input through import and generated Helix exports."""
import io
import json
from pathlib import Path
import unittest
from datetime import datetime

from openpyxl import load_workbook

from features.helix.helix_excel import build_excel_template, import_excel, excel_spec
from features.helix.excel_questions import QUESTION_HEADERS, CHOICE_HEADERS, TABLE_HEADERS
from features.helix.helix_service import HelixService
from features.helix.excel_questions import QUESTION_TYPES
import tempfile
from features.helix.service_generator import create_package


class ExcelQuestionsTest(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((Path(__file__).parents[1] / 'reference/Service with questions.json').read_text())
        self.workbook = load_workbook(io.BytesIO(build_excel_template(self.source)))
        spec = excel_spec(self.source)
        template = spec['templates'][0]
        self.service_row = {'Service name': 'Excel service', 'Service template': template['name']}
        for header, (template_id, field_id) in spec['columns'].items():
            if template_id == template['id']:
                field = next(f for f in template['fields'] if f['id'] == field_id)
                self.service_row[header] = field.get('params', {}).get('form_values', [{}])[0].get('name', 'Profile') if field['type'] == 'DROPDOWN' else 'Profile'
        self.write('Services', 2, self.service_row)

    def tearDown(self):
        self.workbook.close()

    def write(self, name, row, values):
        headers = [c.value for c in self.workbook[name][1]]
        for column, title in enumerate(headers, 1):
            if title in values:
                self.workbook[name].cell(row, column, values[title])

    def question(self, row, key, kind, **fields):
        self.write('Questions', row, {'Service name': 'Excel service', 'Question key': key, 'Type': kind, 'Label': key, **fields})

    def contents(self):
        output = io.BytesIO()
        self.workbook.save(output)
        return output.getvalue()

    def test_questions_choices_tables_groups_defaults_and_conditions_export(self):
        self.question(2, 'name', 'Short text', **{'Required': 'Yes', 'Default answer': 'Alice', 'Maximum characters': 100})
        self.question(3, 'department', 'Dropdown', **{'Show when question key': 'name', 'Expected answers': 'Alice'})
        self.question(4, 'employees', 'Multiple selection table', **{'Table columns': 'Name\nEmail'})
        self.question(5, 'items', 'Repeatable group', **{'Group limit': 4})
        self.question(6, 'item count', 'Number', **{'Parent group key': 'items', 'Default answer': 0, 'Minimum number': 0})
        for row, label, value, default in [(2, 'HR', 'hr', 'Yes'), (3, 'IT', 'it', 'No')]:
            self.write('Choices', row, {'Service name': 'Excel service', 'Question key': 'department', 'Label': label, 'Saved value': value, 'Default': default})
        self.write('Table rows', 2, {'Service name': 'Excel service', 'Question key': 'employees', 'Saved row value': '001', 'Default': 'Yes', 'Value 1': 'Alice', 'Value 2': 'alice@example.com'})
        result = import_excel(self.source, self.contents())
        self.assertEqual(result['errors'], [])
        service = result['services'][0]
        self.assertEqual(len(service['questions']), 4)
        department = service['questions'][1]
        self.assertEqual(department['config']['defaultAnswer'], 'hr')
        self.assertEqual(department['config']['visibilityCondition']['leadingQuestionId'], service['questions'][0]['id'])
        table = service['questions'][2]['config']
        self.assertEqual(table['questionMultiColumn']['data'][0]['displayValue'], ['Alice', 'alice@example.com'])
        self.assertEqual(table['defaultAnswers'], ['001'])
        self.assertEqual(service['questions'][3]['pageItems'][0]['config']['defaultAnswer'], 0)
        export = create_package(self.source, result['services'])
        representation = json.loads(export['questionnaires'][0]['jsonRepresentation'])
        params = {p['id']: p['name'] for p in export['processDefinitionGuidToProcessDefinition'][representation['workflowId']]['inputParams']}
        for q in representation['pages'][0]['pageItems']:
            self.assertEqual(params[q['processInputId']], q['label'])
        self.assertEqual(export['connectorIdToConnection'], {})

    def test_old_services_only_workbook_is_supported(self):
        for name in ('Questions', 'Choices', 'Table rows', 'Conditions', 'Guide'):
            del self.workbook[name]
        result = import_excel(self.source, self.contents())
        self.assertEqual(result['errors'], [])
        self.assertNotIn('questions', result['services'][0])

    def test_bad_question_or_orphaned_detail_prevents_whole_import(self):
        for sheet, values in [
            ('Questions', {'Service name': 'Unknown', 'Question key': 'q', 'Type': 'Short text', 'Label': 'Q'}),
            ('Choices', {'Service name': 'Excel service', 'Question key': 'missing', 'Label': 'A'}),
            ('Table rows', {'Service name': 'Excel service', 'Question key': 'missing', 'Saved row value': '1'}),
        ]:
            with self.subTest(sheet=sheet):
                self.write(sheet, 2, values)
                result = import_excel(self.source, self.contents())
                self.assertEqual(result['services'], [])
                self.assertTrue(any(e['sheet'] == sheet and e['row'] == 2 for e in result['errors']))
                for cell in self.workbook[sheet][2]:
                    cell.value = None

    def test_choices_and_table_cells_reject_duplicates_and_formulas(self):
        self.question(2, 'choice', 'Dropdown')
        for row in (2, 3):
            self.write('Choices', row, {'Service name': 'Excel service', 'Question key': 'choice', 'Label': 'Same', 'Saved value': 'same'})
        result = import_excel(self.source, self.contents())
        self.assertEqual(result['services'], [])
        self.assertTrue(any(e['sheet'] == 'Choices' and e['row'] == 3 for e in result['errors']))
        self.workbook['Choices']['C3'] = '=1+1'
        result = import_excel(self.source, self.contents())
        self.assertTrue(any(e['sheet'] == 'Choices' and 'formulas' in e['message'] for e in result['errors']))

    def test_group_cycles_and_missing_children_are_rejected(self):
        self.question(2, 'group', 'Repeatable group', **{'Parent group key': 'group'})
        result = import_excel(self.source, self.contents())
        self.assertEqual(result['services'], [])
        self.assertTrue(any('nested groups' in e['message'] for e in result['errors']))

    def test_same_key_can_be_used_in_separate_services(self):
        self.write('Services', 3, {**self.service_row, 'Service name': 'Second'})
        self.question(2, 'name', 'Short text')
        self.write('Questions', 3, {'Service name': 'Second', 'Question key': 'name', 'Type': 'TextField', 'Label': 'name'})
        result = import_excel(self.source, self.contents())
        self.assertEqual(result['errors'], [])
        self.assertEqual([len(s['questions']) for s in result['services']], [1, 1])
        self.assertNotEqual(result['services'][0]['questions'][0]['id'], result['services'][1]['questions'][0]['id'])

    def test_typed_excel_dates_and_relative_limits(self):
        self.question(2, 'start date', 'Date', **{'Default answer': datetime(2026, 10, 12),
                      'Earliest date': datetime(2026, 10, 9), 'Latest date': 'today+30'})
        result = import_excel(self.source, self.contents())
        self.assertEqual(result['errors'], [])
        config = result['services'][0]['questions'][0]['config']
        self.assertEqual(config['defaultAnswer'], '2026-10-12')
        self.assertEqual(config['min']['specificLimit'], '2026-10-09')
        self.assertEqual(config['max']['relativeLimit']['numberOfUnits'], 30)

    def test_filled_sample_round_trip_preserves_static_data_and_compound_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = HelixService(Path(directory) / 'helix.sqlite3')
            environment = storage.save_environment('Sample', self.source)
            sample = storage.sample_service(environment['id'])
            result = import_excel(self.source, build_excel_template(self.source, sample))
        self.assertEqual(result['errors'], [])
        questions = result['services'][0]['questions']
        self.assertEqual(len(questions), 18)
        self.assertEqual({q['type'] for q in questions}, set(QUESTION_TYPES.values()))
        lookup = {(q['type'], q['label']): q for q in questions}

        def expression_shape(expression):
            if expression['operator'] in ('AND', 'OR'):
                return (expression['operator'], expression['withParentheses'],
                        expression_shape(expression['left']), expression_shape(expression['right']))
            return (expression['operator'], expression['left']['label'], expression['right'])

        for original in sample['questions']:
            question = lookup[original['type'], original['label']]
            config = question['config']
            source_config = original['config']
            if source_config.get('options'):
                self.assertEqual(config['options'], source_config['options'])
            if source_config.get('questionMultiColumn'):
                original_table = source_config['questionMultiColumn']
                table = config['questionMultiColumn']
                self.assertEqual(table['data'], original_table['data'])
                self.assertEqual([c['displayName'] for c in table['metaData']],
                                 [c['displayName'] for c in original_table['metaData']])
            if source_config.get('visibilityCondition'):
                self.assertEqual(expression_shape(config['visibilityCondition']['expression']),
                                 expression_shape(source_config['visibilityCondition']['expression']))
            self.assertFalse(config.get('connectorId') or config.get('datasetId'))
        exported = create_package(self.source, result['services'])
        self.assertEqual(exported['connectorIdToConnection'], {})

    def test_invalid_condition_tree_prevents_import(self):
        self.question(2, 'leader', 'Short text')
        self.question(3, 'dependent', 'Short text')
        self.write('Conditions', 2, {'Service name': 'Excel service', 'Question key': 'dependent',
                   'Rule key': 'root', 'Match': 'All'})
        self.write('Conditions', 3, {'Service name': 'Excel service', 'Question key': 'dependent',
                   'Rule key': 'child', 'Parent rule key': 'root', 'Leading question key': 'leader',
                   'Comparison': 'Equals', 'Expected answers': 'test'})
        result = import_excel(self.source, self.contents())
        self.assertEqual(result['services'], [])
        self.assertTrue(any(e['sheet'] == 'Conditions' and e['row'] == 2 for e in result['errors']))
