import json
from pathlib import Path
import unittest
import tempfile

from features.helix.helix_service import HelixService
from features.helix.questions import TYPES, WIDGETS, build_questionnaire
from features.helix.service_generator import create_package


class QuestionTests(unittest.TestCase):
    def test_load_sample_for_each_environment_and_export_all_cases(self):
        reference = json.loads((Path(__file__).parents[1] / 'reference/Service with questions.json').read_text())
        original = json.loads(reference['questionnaires'][0]['jsonRepresentation'])
        static_items = {q['id']: q for q in original['pages'][0]['pageItems']
                        if not (q.get('connectorId') or q.get('datasetId') or q.get('lookupByProcess'))}
        with tempfile.TemporaryDirectory() as directory:
            service = HelixService(Path(directory) / 'helix.sqlite3')
            for path in (Path(__file__).parents[1] / 'reference').glob('*.json'):
                with self.subTest(environment=path.name):
                    source = json.loads(path.read_text())
                    environment = service.save_environment(path.stem, source)
                    sample = service.sample_service(environment['id'])
                    self.assertEqual({q['id'] for q in sample['questions']}, set(static_items))
                    self.assertEqual(len(sample['questions']), 17)
                    saved = service.create_package(environment['id'], [sample])
                    package = service.get_package(environment['id'], saved['id'])
                    content = json.loads(package['questionnaires'][0]['jsonRepresentation'])
                    items = content['pages'][0]['pageItems']
                    self.assertTrue(any(q.get('hidden') for q in items))
                    self.assertTrue(any(q.get('readOnly') for q in items))
                    self.assertTrue(any(q.get('visibilityCondition') for q in items))
                    self.assertFalse(any(q.get('connectorId') or q.get('datasetId') for q in items))
                    self.assertEqual(content['actions'], [])
                    self.assertEqual(package['connectorIdToConnection'], {})
                    for question in items:
                        source = static_items[question['id']]
                        for key in ('options', 'staticDataValues', 'questionMultiColumn', 'defaultAnswer',
                                    'defaultAnswers', 'description', 'min', 'max'):
                            if key in source:
                                self.assertEqual(question[key], source[key], (question['label'], key))
                    group = next(q for q in items if q['type'] == 'RepeatableGroup')
                    self.assertEqual(len(group['pageItems']), 2)
                    workflow = package['processDefinitionGuidToProcessDefinition'][content['workflowId']]
                    params = {p['id']: p['name'] for p in workflow['inputParams']}
                    for question in items:
                        if question['type'] not in WIDGETS:
                            self.assertEqual(params[question['processInputId']], question['label'])

    def test_every_reference_type_and_input_label(self):
        questions = [{'type': kind, 'label': kind, 'required': True,
                      **({'pageItems': [{'type': 'TextField', 'label': 'Child'}]} if kind == 'RepeatableGroup' else {})}
                     for kind in TYPES]
        workflow = {'guid': 'workflow'}
        q = build_questionnaire(questions, workflow, 'Service', 123)
        representation = json.loads(q['jsonRepresentation'])
        params = {p['id']: p for p in workflow['inputParams']}
        for item in representation['pages'][0]['pageItems']:
            if item['type'] not in WIDGETS:
                self.assertEqual(params[item['processInputId']]['name'], item['label'])
        self.assertEqual(len(params), len(TYPES) - len(WIDGETS))

    def test_package_links_and_merges_questionnaires(self):
        data = json.loads((Path(__file__).parents[1] / 'reference/Service with questions.json').read_text())
        template = next(iter(data['serviceTypes']))
        fields = {f['id']: 'Profile' for f in data['serviceTypes'][template]['fields'] if f.get('required')}
        specs = [{'templateId': template, 'name': name, 'fieldValues': fields,
                  'questions': [{'type': 'TextField', 'label': 'Your name'}]} for name in ('One', 'Two')]
        package = create_package(data, specs)
        self.assertEqual(len(package['questionnaires']), 2)
        self.assertEqual(len(package['oldGroupIdToQuestionnaireTranslations']), 2)
        for service, questionnaire in zip(package['services'], package['questionnaires']):
            revision = service['versions'][0]['revisions'][0]
            self.assertEqual(revision['questionnaireGroupId'], questionnaire['questionnaireGroupId'])
            self.assertEqual(service['allRevisions'][0], revision)
            content = json.loads(questionnaire['jsonRepresentation'])
            self.assertEqual(content['workflowId'], revision['workflowId'])

    def test_invalid_labels_and_types(self):
        for questions in ([{'type': 'Bad', 'label': 'Q'}], [{'type': 'TextField', 'label': ' '}],
                          [{'type': 'TextField', 'label': 'Q'}, {'type': 'TextArea', 'label': 'q'}]):
            with self.assertRaises(ValueError):
                build_questionnaire(questions, {'guid': 'w'}, 'S', 0)
