"""Reference-backed work-order and group-approval mappings."""
from copy import deepcopy
import json
from pathlib import Path
import re

REFERENCE = json.loads(Path(__file__).with_name('fulfillment_reference.json').read_text())
WORK_ORDER = 'Create work order'


def remedy_connections(environment):
    connections = environment.get('connectorIdToConnection', {})
    return {identifier: connections[str(key)] for identifier, key in environment.get('rxConnectionIdToConnectionId', {}).items()
            if str(key) in connections and connections[str(key)].get('rxBundleId') == 'com.bmc.myservice.connect.remedy'}


def resolve_connection(row, environment):
    available = remedy_connections(environment)
    selected = row.get('Connection ID', '')
    if not selected and available:
        preferred = next((identifier for identifier, connection in available.items()
                          if (connection.get('connectionName') or '').casefold() == 'remedy'), None)
        return preferred or next(iter(available))
    if selected not in available:
        raise ValueError('The environment export must contain a valid Remedy connection. Upload an export containing its connection metadata.')
    return selected


def other_fields(row):
    result = []
    if row.get('Priority'):
        result.append(('Priority', row['Priority']))
    for line in row.get('Other fields', '').splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition('=')
        if not separator or not key.strip() or not value.strip():
            raise ValueError('Other fields use one field = value assignment per line.')
        if key.strip().casefold() == 'description':
            raise ValueError('Description is always taken from QAnswer OutputText.')
        result.append((key.strip(), value.strip()))
    if len(result) > 3:
        raise ValueError('Use at most three extra work-order fields, including Priority, per step.')
    if len({key.casefold() for key, _ in result}) != len(result):
        raise ValueError('Work-order extra field names must be unique; do not repeat Priority in Other fields.')
    return result


def validate_work_order(row):
    support = [row.get(key, '') for key in ('Support company', 'Support organization', 'Support group')]
    if any(support) and not all(support):
        raise ValueError('Fill Support company, Support organization, and Support group together.')
    if not row.get('Template') and not all(support):
        raise ValueError('A work order needs a Template or all three support assignment fields.')
    if row.get('Approvers'):
        raise ValueError('Work orders do not use Approvers.')
    other_fields(row)


def value_expression(value, question_names):
    if value.casefold().startswith('question:'):
        label = value.partition(':')[2].strip().casefold()
        if label not in question_names:
            raise ValueError('Question-based workflow values must reference an answerable question label in this service.')
        return '${processContext.' + question_names[label] + '}'
    if value.startswith('${'):
        return value
    return json.dumps(value)


def work_order_rows(row, name, question_names, environment, builder_name=None):
    """Return the optional input builder and creation step, in execution order."""
    validate_work_order(row)
    mappings = [
        {'assignTarget': 'connectionId', 'expression': json.dumps(resolve_connection(row, environment))},
        {'assignTarget': 'customerLoginId', 'expression': '${processContext.Context.requestedFor.loginName}'},
        {'assignTarget': 'contactLoginId', 'expression': '${processContext.Context.requestedBy.loginName}'},
        {'assignTarget': 'summary', 'expression': value_expression(row['Summary'], question_names) if row.get('Summary') else '${processContext.Context.service.name}'},
        {'assignTarget': 'description', 'expression': '${activityResults.QAnswer.OutputText}'},
        {'assignTarget': 'correlationId', 'expression': '$\\PROCESSCORRELATIONID$'},
    ]
    for column, target in [('Template', 'templateName'), ('Support company', 'requestAssigneeSupportGroupCompany'),
                           ('Support organization', 'requestAssigneeSupportOrganization'), ('Support group', 'requestAssigneeSupportGroupName')]:
        if row.get(column):
            mappings.append({'assignTarget': target, 'expression': value_expression(row[column], question_names)})
    steps = []
    fields = other_fields(row)
    if fields:
        builder = builder_name or name + 'Inputs'
        assignments = []
        for index, (key, value) in enumerate(fields, 1):
            assignments.extend([f'key{index} = ' + json.dumps(key),
                                f'value{index} = ' + value_expression(value, question_names)])
        steps.append({'Row type': 'Step', 'Name': builder, 'Type': 'Service task',
                      'Target': REFERENCE['buildInputSet']['actionTypeName'], 'Input mapping': '\n'.join(assignments)})
        steps.append({'Row type': 'Flow', 'From': builder, 'To': name})
        mappings.append({'assignTarget': 'otherFields', 'expression': '${activityResults.' + builder + '.output.inputs}'})
    steps.append({'Row type': 'Step', 'Name': name, 'Type': 'Service task',
                  'Target': REFERENCE['workOrder']['actionTypeName'],
                  'Input mapping': '\n'.join(m['assignTarget'] + ' = ' + m['expression'] for m in mappings)})
    return steps, builder if fields else name


def creates_work_item(rows):
    return any(re.search(r'create.*(?:work.?order|incident|change|wo(?:$|[^A-Za-z]))', row.get('Target', ''), re.I)
               for row in rows if row.get('Row type') == 'Step')


def add_connection_metadata(output, environment):
    used = set()
    def inspect(elements):
        for element in elements:
            for mapping in element.get('inputMap', []):
                if mapping['assignTarget'] == 'connectionId':
                    try:
                        identifier = json.loads(mapping['expression'])
                        if isinstance(identifier, str):
                            used.add(identifier)
                    except (ValueError, TypeError):
                        pass
            inspect(element.get('flowElements', []))
    for process in output['processDefinitionGuidToProcessDefinition'].values():
        inspect(process['flowElements'])
    for identifier in used:
        key = environment.get('rxConnectionIdToConnectionId', {}).get(identifier)
        if key is not None and str(key) in environment.get('connectorIdToConnection', {}):
            output['rxConnectionIdToConnectionId'][identifier] = key
            output['connectorIdToConnection'][str(key)] = deepcopy(environment['connectorIdToConnection'][str(key)])
    for identifier, key in environment.get('rcfConnectionIdToConnectionId', {}).items():
        if key in output['rxConnectionIdToConnectionId'].values():
            output['rcfConnectionIdToConnectionId'][identifier] = key
