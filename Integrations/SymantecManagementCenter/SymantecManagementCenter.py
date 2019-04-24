import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *

''' IMPORTS '''

import json
import requests
from distutils.util import strtobool

# Disable insecure warnings
requests.packages.urllib3.disable_warnings()

''' GLOBALS/PARAMS '''

USERNAME = demisto.params().get('credentials').get('identifier')
PASSWORD = demisto.params().get('credentials').get('password')
SERVER = (demisto.params()['url'][:-1]
          if (demisto.params()['url'] and demisto.params()['url'].endswith('/')) else demisto.params()['url'])
BASE_URL = SERVER + '/api/'
USE_SSL = not demisto.params().get('insecure', False)
HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}
URL_LIST_TYPE = 'URL_LIST'
IP_LIST_TYPE = 'IP_LIST'
CATEGORY_LIST_TYPE = 'CATEGORY_LIST'

''' HELPER FUNCTIONS '''


def http_request(method, path, params=None, data=None):
    """
    Sends an HTTP request using the provided arguments
    :param method: HTTP method
    :param path: URL path
    :param params: URL query params
    :param data: Request body
    :return: JSON response (or the response itself if not serializable)
    """
    params = params if params is not None else {}
    data = data if data is not None else {}
    res = None

    try:
        res = requests.request(
            method,
            BASE_URL + path,
            auth=(USERNAME, PASSWORD),
            verify=USE_SSL,
            params=params,
            data=json.dumps(data),
            headers=HEADERS)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects, requests.exceptions.RequestException):
        # TODO: Wait for fiedler
        return_error('Connection error')

    if res.status_code < 200 or res.status_code > 300:
        status = res.status_code
        message = res.reason
        details = ''
        try:
            error_json = res.json()
            message = error_json.get('statusMessage')
            details = error_json.get('message')
        except Exception:
            pass
        return_error('Error in API call to Symantec MC, status code: {}, reason: {}, details: {}'.format(status, message, details))

    try:
        return res.json()
    except Exception:
        return res


''' FUNCTIONS '''


def test_module():
    """
    Performs basic get request to get system info
    """
    sys_info = http_request('GET', 'system/info')
    demisto.results('ok')


def list_devices_command():
    """
    List devices in Symantec MC using provided query filters
    """

    contents = []
    context = {}
    build = demisto.args().get('build')
    description = demisto.args().get('description')
    model = demisto.args().get('model')
    name = demisto.args().get('name')
    os_version = demisto.args().get('os_version')
    platform = demisto.args().get('platform')
    device_type = demisto.args().get('type')
    limit = int(demisto.args().get('limit', 10))

    devices = list_devices_request(build, description, model, name, os_version, platform, device_type)

    if devices:
        if limit:
            devices = devices[:limit]

        for device in devices:
            contents.append({
                'UUID': device.get('uuid'),
                'Name': device.get('name'),
                'LastChanged': device.get('lastChanged'),
                'Host': device.get('host'),
                'Type': device.get('type')
            })

        context['SymantecMC.Device(val.UUID && val.UUID === obj.UUID)'] = createContext(contents, removeNull=True)

    headers = ['UUID', 'Name', 'LastChanged', 'Host', 'Type']
    return_outputs(tableToMarkdown('Symantec Management Center Devices', contents,
                                   removeNull=True, headers=headers, headerTransform=pascalToSpace), context, devices)


def list_devices_request(build, description, model, name, os_version, platform, device_type):
    """
    Get devices from Symantec MC
    :param build: Device build number query
    :param description: Device description query
    :param model: Device model query
    :param name: Device name query
    :param os_version: Device OS version query
    :param platform: Device platform query
    :param device_type: Device type
    :return: List of Symantec MC devices
    """

    path = 'devices'
    params = {}

    if build:
        params['build'] = build
    if description:
        params['description'] = description
    if model:
        params['model'] = model
    if name:
        params['name'] = name
    if os_version:
        params['osVersion'] = os_version
    if platform:
        params['platform'] = platform
    if device_type:
        params['type'] = device_type

    response = http_request('GET', path, params)
    return response


def get_device_command():
    """
    Command to get information for a specified device
    :return: An entry with the device data
    """
    uuid = demisto.args()['uuid']
    content = {}
    context = {}

    device = get_device_request(uuid)
    if device:
        content = {
            'UUID': device.get('uuid'),
            'Name': device.get('name'),
            'LastChanged': device.get('lastChanged'),
            'LastChangedBy': device.get('lastChangedBy'),
            'Description': device.get('description'),
            'Model': device.get('model'),
            'Platform': device.get('platform'),
            'Type': device.get('type'),
            'OSVersion': device.get('osVersion'),
            'Build': device.get('build'),
            'SerialNumber': device.get('serialNumber'),
            'Host': device.get('host'),
            'ManagementStatus': device.get('managementStatus'),
            'DeploymentStatus': device.get('deploymentStatus')
        }

        context['SymantecMC.Device(val.UUID && val.UUID === obj.UUID)'] = createContext(content, removeNull=True)

    headers = ['UUID', 'Name', 'LastChanged', 'LastChangedBy', 'Description',
               'Model', 'Platform', 'Host', 'Type', 'OSVersion', 'Build', 'SerialNumber',
               'ManagementStatus', 'DeploymentStatus']

    return_outputs(tableToMarkdown('Symantec Management Center Device', content,
                                   removeNull=True, headers=headers, headerTransform=pascalToSpace), context, device)


def get_device_request(uuid):
    """
    Return data for a specified device
    :param uuid: The device UUID
    :return: The device data
    """
    path = 'devices/' + uuid

    response = http_request('GET', path)

    return response


def get_device_health_command():
    """
        Command to get health information for a specified device
        :return: An entry with the device data and health
        """
    uuid = demisto.args()['uuid']
    health_content = []
    human_readable = ''
    context = {}

    device_health = get_device_health_request(uuid)
    if device_health and device_health.get('health'):

        if not isinstance(device_health['health'], list):
            device_health['health'] = [device_health['health']]

        device_content = {
            'UUID': device_health.get('uuid'),
            'Name': device_health.get('name')
        }

        for health in device_health['health']:
            health_content.append({
                'Category': health.get('category'),
                'Name': health.get('name'),
                'State': health.get('state'),
                'Message': health.get('message'),
                'Status': health.get('status')
            })

        device_headers = ['UUID', 'Name']
        content = device_content
        human_readable = tableToMarkdown('Symantec Management Center Device', device_content,
                                         removeNull=True, headers=device_headers, headerTransform=pascalToSpace)
        if health_content:
            health_headers = ['Category', 'Name', 'State', 'Message', 'Status']
            human_readable += tableToMarkdown('Device Health', health_content,
                                              removeNull=True, headers=health_headers, headerTransform=pascalToSpace)
            content['Health'] = health_content

        context['SymantecMC.Device(val.UUID && val.UUID === obj.UUID)'] = createContext(content, removeNull=True)

    return_outputs(human_readable, context, device_health)


def get_device_health_request(uuid):
    """
    Return health for a specified device
    :param uuid: The device UUID
    :return: The device health data
    """
    path = 'devices/' + uuid + '/health'

    response = http_request('GET', path)

    return response


def get_device_license_command():
    """
    Command to get license information for a specified device
    :return: An entry with the device data and license information
    """
    uuid = demisto.args()['uuid']
    license_content = []
    human_readable = ''
    context = {}

    device_license = get_device_license_request(uuid)
    if device_license:

        if not isinstance(device_license['components'], list):
            device_license['components'] = [device_license['components']]

        device_content = {
            'UUID': device_license.get('uuid'),
            'Name': device_license.get('name'),
            'Type': device_license.get('deviceType'),
            'LicenseStatus': device_license.get('licenseStatus')
        }

        for component in device_license['components']:
            license_content.append({
                'Name': component.get('componentName'),
                'ActivationDate': component.get('activationDate'),
                'ExpirationDate': component.get('expirationDate'),
                'Validity': component.get('validity')
            })

        device_headers = ['UUID', 'Name', 'Type', 'LicenseStatus']
        content = device_content
        human_readable = tableToMarkdown('Symantec Management Center Device', device_content,
                                         removeNull=True, headers=device_headers, headerTransform=pascalToSpace)
        if license_content:
            license_headers = ['Name', 'ActivationDate', 'ExpirationDate', 'Validity']
            human_readable += tableToMarkdown('License Components', license_content,
                                              removeNull=True, headers=license_headers, headerTransform=pascalToSpace)
            content['LicenseComponent'] = license_content

        context['SymantecMC.Device(val.UUID && val.UUID === obj.UUID)'] = createContext(content, removeNull=True)

    return_outputs(human_readable, context, device_license)


def get_device_license_request(uuid):
    """
    Return the license for a specified device
    :param uuid: The device UUID
    :return: The device license data
    """
    path = 'devices/' + uuid + '/license'

    response = http_request('GET', path)

    return response


def get_device_status_command():
    """
    Command to get the status for a specified device
    :return: An entry with the device status data
    """
    uuid = demisto.args()['uuid']
    content = {}
    context = {}

    device = get_device_status_request(uuid)
    if device:
        content = {
            'UUID': device.get('uuid'),
            'Name': device.get('name'),
            'CheckDate': device.get('checkDate'),
            'StartDate': device.get('startDate'),
            'MonitorState': device.get('monitorState'),
            'Warnings': len(device.get('warnings', [])),
            'Errors': len(device.get('errors', []))
        }

        context['SymantecMC.Device(val.UUID && val.UUID === obj.UUID)'] = createContext(content, removeNull=True)

    headers = ['UUID', 'Name', 'CheckDate', 'StartDate', 'MonitorState', 'Warnings', 'Errors']

    return_outputs(tableToMarkdown('Symantec Management Center Device Status', content,
                                   removeNull=True, headers=headers, headerTransform=pascalToSpace), context, device)


def get_device_status_request(uuid):
    """
    Return data for a specified device status
    :param uuid: The device UUID
    :return: The device status data
    """
    path = 'devices/' + uuid + '/status'

    response = http_request('GET', path)

    return response


def list_policies_command():
    """
    List policies in Symantec MC using provided query filters
    """

    contents = []
    context = {}
    content_type = demisto.args().get('content_type')
    description = demisto.args().get('description')
    name = demisto.args().get('name')
    reference_id = demisto.args().get('reference_id')
    shared = demisto.args().get('shared')
    tenant = demisto.args().get('tenant')
    limit = int(demisto.args().get('limit', 10))

    policies = list_policies_request(content_type, description, name, reference_id, shared, tenant)

    if policies:
        if limit:
            policies = policies[:limit]

        for policy in policies:
            contents.append({
                'UUID': policy.get('uuid'),
                'Name': policy.get('name'),
                'ContentType': policy.get('contentType'),
                'Author': policy.get('author'),
                'Shared': policy.get('shared'),
                'ReferenceID': policy.get('referenceId'),
                'Tenant': policy.get('tenant'),
                'ReplaceVariables': policy.get('replaceVariables')
            })

        context['SymantecMC.Policy(val.UUID && val.UUID === obj.UUID)'] = createContext(contents, removeNull=True)

    headers = ['UUID', 'Name', 'ContentType', 'Author', 'Shared', 'ReferenceID', 'Tenant', 'ReplaceVariables']
    return_outputs(tableToMarkdown('Symantec Management Center Policies', contents,
                                   removeNull=True, headers=headers, headerTransform=pascalToSpace), context, policies)


def list_policies_request(content_type, description, name, reference_id, shared, tenant):
    """
    Get policies in Symantec MC
    :param content_type: Policy content type query
    :param description: Policy description query
    :param name: Policy name query
    :param reference_id: Policy reference ID query
    :param shared: Policy shared query
    :param tenant: Policy tenant query
    :return: List of policies in Symantec MC
    """
    path = 'policies'
    params = {}

    if content_type:
        params['contentType'] = content_type
    if description:
        params['description'] = description
    if name:
        params['name'] = name
    if reference_id:
        params['referenceId'] = reference_id
    if shared:
        params['shared'] = shared
    if tenant:
        params['tenant'] = tenant

    response = http_request('GET', path, params)
    return response


def get_policy_command():
    """
    Command to get information for a specified policy including it's contents
    :return: An entry with the policy data
    """
    uuid = demisto.args()['uuid']
    policy_content_data = {}
    revision_content = {}
    policy_content_content = []
    content_title = ''
    human_readable = ''
    content_headers = []
    content_key = ''
    context = {}

    policy = get_policy_request(uuid)
    if policy:
        policy_content = {
            'UUID': policy.get('uuid'),
            'Name': policy.get('name'),
            'Description': policy.get('description'),
            'ContentType': policy.get('contentType')
        }
        policy_content_data = get_policy_content_request(uuid)

        if 'revisionInfo' in policy_content_data:
            policy_content['SchemaVersion'] = policy_content_data.get('schemaVersion')
            revision_content = {
                'Number': policy_content_data['revisionInfo'].get('revisionNumber'),
                'Description': policy_content_data['revisionInfo'].get('revisionDescription'),
                'Author': policy_content_data['revisionInfo'].get('author'),
                'Date': policy_content_data['revisionInfo'].get('revisionDate')
            }

        if policy.get('contentType') == URL_LIST_TYPE:
            content_title = 'URLs'
            content_headers = ['Address', 'Description', 'Enabled']
            content_key = 'URL'
            urls = policy_content_data.get('content', {}).get('urls', [])
            for url in urls:
                policy_content_content.append({
                    'Address': url.get('url'),
                    'Description': url.get('description'),
                    'Enabled': url.get('enabled')
                })
        elif policy.get('contentType') == IP_LIST_TYPE:
            content_title = 'IPs'
            content_headers = ['Address', 'Description', 'Enabled']
            content_key = 'IP'
            ips = policy_content_data.get('content', {}).get('ipAddresses', [])
            for ip in ips:
                policy_content_content.append({
                    'Address': ip.get('ipAddress'),
                    'Description': ip.get('description'),
                    'Enabled': ip.get('enabled')
                })
        elif policy.get('contentType') == CATEGORY_LIST_TYPE:
            content_title = 'Categories'
            content_headers = ['Name']
            content_key = 'Category'
            categories = policy_content_data.get('content', {}).get('categories', [])
            for category in categories:
                policy_content_content.append({
                    'Name': category.get('categoryName')
                })

        policy_headers = ['UUID', 'Name', 'SchemaVersion', 'Description', 'ContentType']
        human_readable = tableToMarkdown('Symantec Management Center Policy', policy_content,
                                         removeNull=True, headers=policy_headers, headerTransform=pascalToSpace)
        content = policy_content
        if revision_content:
            revision_headers = ['Number', 'Description', 'Author', 'Date']
            content['RevisionInfo'] = revision_content
            human_readable += tableToMarkdown('Revision Information', revision_content,
                                              removeNull=True, headers=revision_headers, headerTransform=pascalToSpace)

        if policy_content_content:
            content[content_key] = policy_content_content
            human_readable += tableToMarkdown(content_title, policy_content_content,
                                              removeNull=True, headers=content_headers, headerTransform=pascalToSpace)

        context['SymantecMC.Policy(val.UUID && val.UUID === obj.UUID)'] = createContext(content, removeNull=True)

    return_outputs(human_readable, context, policy.update(policy_content_data))


def get_policy_request(uuid):
    """
    Return data for a specified policy
    :param uuid: The policy UUID
    :return: The policy data
    """
    path = 'policies/' + uuid

    response = http_request('GET', path)

    return response


def get_policy_content_request(uuid):
    """
    Return content data for a specified policy
    :param uuid: The policy UUID
    :return: The policy content data
    """
    path = 'policies/' + uuid + '/content'

    response = http_request('GET', path)

    return response


def create_policy_command():
    """
        Command to create a new policy in Symantec MC
        :return: An entry with the new policy data
    """
    name = demisto.args()['name']
    content_type = demisto.args()['content_type']
    description = demisto.args().get('description')
    reference_id = demisto.args().get('reference_id')
    tenant = demisto.args().get('tenant')
    shared = demisto.args().get('shared')
    replace_variables = demisto.args().get('replace_variables')

    content = {}
    context = {}

    policy = create_policy_request(name, content_type, description, reference_id, tenant, shared, replace_variables)
    if policy:
        content = {
            'UUID': policy.get('uuid'),
            'Name': policy.get('name'),
            'ContentType': policy.get('contentType'),
            'Author': policy.get('author')
        }

        context['SymantecMC.Policy(val.UUID && val.UUID === obj.UUID)'] = createContext(content, removeNull=True)

    headers = ['UUID', 'Name', 'ContentType', 'Author']

    return_outputs(tableToMarkdown('Policy created successfully', content,
                                   removeNull=True, headers=headers, headerTransform=pascalToSpace), context, policy)


def create_policy_request(name, content_type, description, reference_id, tenant, shared, replace_variables):
    """
    Creates a policy in Symantec MC using the provided arguments
    :param name: Policy name
    :param content_type: Policy content type
    :param description: Policy description
    :param reference_id: Policy reference ID
    :param tenant: Policy tenant
    :param shared: Policy shared
    :param replace_variables: Policy replace variables
    :return: The created policy data
    """
    path = 'policies'

    body = {
        'name': name,
        'contentType': content_type
    }

    if description:
        body['description'] = description
    if reference_id:
        body['referenceId'] = reference_id
    if tenant:
        body['tenant'] = tenant
    if shared:
        body['shared'] = shared
    if replace_variables:
        body['replaceVariables'] = replace_variables

    response = http_request('POST', path, data=body)
    return response


def update_policy_command():
    """
        Command to update an existing policy in Symantec MC
        :return: An entry with the policy data
    """
    uuid = demisto.args()['uuid']
    name = demisto.args().get('name')
    description = demisto.args().get('description')
    reference_id = demisto.args().get('reference_id')
    replace_variables = demisto.args().get('replace_variables')

    content = {}
    context = {}

    policy = update_policy_request(uuid, name, description, reference_id, replace_variables)
    if policy:
        content = {
            'UUID': policy.get('uuid'),
            'Name': policy.get('name'),
            'ContentType': policy.get('contentType'),
            'Author': policy.get('author')
        }

        context['SymantecMC.Policy(val.UUID && val.UUID === obj.UUID)'] = createContext(content, removeNull=True)

    headers = ['UUID', 'Name', 'ContentType', 'Author']

    return_outputs(tableToMarkdown('Policy updated successfully', content,
                                   removeNull=True, headers=headers, headerTransform=pascalToSpace), context, policy)


def update_policy_request(uuid, name, description, reference_id, replace_variables):
    """
    Updates a policy in Symantec MC using the provided arguments
    :param uuid: Policy UUID
    :param name: New policy name
    :param description: New policy description
    :param reference_id: New policy reference ID
    :param replace_variables: New policy replace variables
    :return: The updated policy data
    """
    path = 'policies/' + uuid

    body = {}

    if name:
        body['name'] = name
    if description:
        body['description'] = description
    if reference_id:
        body['referenceId'] = reference_id
    if replace_variables:
        body['replaceVariables'] = replace_variables

    response = http_request('PUT', path, data=body)
    return response


def delete_policy_command():
    """
        Command to delete an existing policy in Symantec MC
        :return: An entry indicating whether the deletion was successful
    """
    uuid = demisto.args()['uuid']
    force = demisto.args().get('force')

    delete_policy_request(uuid, force)
    return_outputs('Policy deleted successfully', {}, {})


def delete_policy_request(uuid, force):
    """
    Deletes a policy in Symantec MC using the provided arguments
    :param uuid: Policy UUID
    :param force: Force policy delete
    :return: The deletion response
    """
    path = 'policies/' + uuid

    response = http_request('DELETE', path, data=force)
    return response


def add_policy_content_command():
    """
        Command to add content to an existing policy in Symantec MC
        :return: An entry indicating whether the addition was successful
    """
    uuid = demisto.args()['uuid']
    content_type = demisto.args()['content_type']
    change_description = demisto.args()['change_description']
    schema_version = demisto.args().get('schema_version')
    ips = argToList(demisto.args().get('ip', []))
    urls = argToList(demisto.args().get('url', []))
    categories = argToList(demisto.args().get('category', []))
    enabled = demisto.args().get('enabled')
    description = demisto.args().get('description')

    if ((content_type == IP_LIST_TYPE and not ips) or
            (content_type == URL_LIST_TYPE and not urls) or
            (content_type == CATEGORY_LIST_TYPE and not categories)):
        return_error('Incorrect content provided for the type {}'.format(content_type))

    if ((content_type == IP_LIST_TYPE and (urls or categories)) or
            (content_type == URL_LIST_TYPE and (ips or categories)) or
            (content_type == CATEGORY_LIST_TYPE and (ips or urls))):
        return_error('More than one content type was provided for the type {}'.format(content_type))

    if content_type == IP_LIST_TYPE:
        add_policy_content_request(uuid, content_type, change_description, schema_version,
                                   ips=ips, enabled=enabled, description=description)
    elif content_type == URL_LIST_TYPE:
        add_policy_content_request(uuid, content_type, change_description, schema_version,
                                   urls=urls, enabled=enabled, description=description)
    elif content_type == CATEGORY_LIST_TYPE:
        add_policy_content_request(uuid, content_type, change_description, schema_version,
                                   categories=categories)

    return_outputs('Successfully added content to the policy', {}, {})


def add_policy_content_request(uuid, content_type, change_description, schema_version,
                               ips=None, urls=None, categories=None, enabled=None, description=''):
    """
    Add content to a specified policy using the provided arguments
    :param uuid: Policy UUID
    :param content_type: Policy content type
    :param change_description: Policy update change description
    :param schema_version: Policy schema version
    :param ips: IPs to add to the content
    :param urls: URLs to add to the content
    :param categories: Category names to add to the content
    :param enabled:  Policy content enabled
    :param description: Policy content description
    :return: Content update response
    """
    path = 'policies/' + uuid + '/content'

    body = {
        'contentType': content_type,
        'changeDescription': change_description
    }

    if schema_version:
        body['schemaVersion'] = schema_version

    content = get_policy_content_request(uuid)
    if not content or 'content' not in content:
        return_error('Could not update policy content - failed retrieving the current content')

    if ips:
        if 'ipAddresses' not in content['content']:
            content['content']['ipAddresses'] = []
        content['content']['ipAddresses'] += [{
            'ipAddress': ip,
            'description': description,
            'enabled': bool(strtobool(enabled))
        } for ip in ips]
    elif urls:
        if 'urls' not in content['content']:
            content['content']['urls'] = []
        content['content']['urls'] += [{
            'url': url,
            'description': description,
            'enabled': bool(strtobool(enabled))
        } for url in urls]
    elif categories:
        if 'categories' not in content['content']:
            content['content']['categories'] = []
        content['content']['categories'] += [{
            'categoryName': category,
        } for category in categories]

    # temporary workaround
    # ==================================================================
    if 'items' in content['content']:
        content['content'].pop('items')
    # ==================================================================
    body['content'] = content['content']
    response = http_request('POST', path, data=body)

    return response


def delete_policy_content_command():
    """
        Command to delete content from an existing policy in Symantec MC
        :return: An entry indicating whether the deletion was successful
    """
    uuid = demisto.args()['uuid']
    content_type = demisto.args()['content_type']
    change_description = demisto.args()['change_description']
    schema_version = demisto.args().get('schema_version')
    ips = argToList(demisto.args().get('ip', []))
    urls = argToList(demisto.args().get('url', []))
    categories = argToList(demisto.args().get('category', []))

    if ((content_type == IP_LIST_TYPE and not ips) or
            (content_type == URL_LIST_TYPE and not urls) or
            (content_type == CATEGORY_LIST_TYPE and not categories)):
        return_error('Incorrect content provided for the type {}'.format(content_type))

    if ((content_type == IP_LIST_TYPE and (urls or categories)) or
            (content_type == URL_LIST_TYPE and (ips or categories)) or
            (content_type == CATEGORY_LIST_TYPE and (ips or urls))):
        return_error('More than one content type was provided for the type {}'.format(content_type))

    if content_type == IP_LIST_TYPE:
        delete_policy_content_request(uuid, content_type, change_description, schema_version, ips=ips)
    elif content_type == URL_LIST_TYPE:
        delete_policy_content_request(uuid, content_type, change_description, schema_version, urls=urls)
    elif content_type == CATEGORY_LIST_TYPE:
        delete_policy_content_request(uuid, content_type, change_description, schema_version, categories=categories)

    return_outputs('Successfully deleted content from the policy', {}, {})


def delete_policy_content_request(uuid, content_type, change_description, schema_version,
                                  ips=None, urls=None, categories=None):
    """
    Add content to a specified policy using the provided arguments
    :param uuid: Policy UUID
    :param content_type: Policy content type
    :param change_description: Policy update change description
    :param schema_version: Policy schema version
    :param ips: IPs to delete from the content
    :param urls: URLs to delete from the content
    :param categories: Category names to delete from the content
    :return: Content update response
    """
    path = 'policies/' + uuid + '/content'

    body = {
        'contentType': content_type,
        'changeDescription': change_description
    }

    if schema_version:
        body['schemaVersion'] = schema_version

    content = get_policy_content_request(uuid)
    if not content or 'content' not in content:
        return_error('Could not update policy content - failed retrieving the current content')

    if ips:
        if 'ipAddresses' in content['content']:
            ips_to_keep = [ip for ip in content['content']['ipAddresses'] if ip['ipAddress'] not in ips]
            content['content']['ipAddresses'] = ips_to_keep
    elif urls:
        if 'urls' in content['content']:
            urls_to_keep = [url for url in content['content']['urls'] if url['url'] not in urls]
            content['content']['urls'] = urls_to_keep
    elif categories:
        if 'categories' in content['content']:
            categories_to_keep = [category for category in content['content']['categories']
                                  if category['categoryName'] not in categories]
            content['content']['categories'] = categories_to_keep

    body['content'] = content['content']
    response = http_request('POST', path, data=body)

    return response


def list_tenants_command():
    """
    List tenants in Symantec MC
    """

    contents = []
    context = {}
    limit = int(demisto.args().get('limit', 10))

    tenants = list_tenants_request()

    if tenants:
        if limit:
            tenants = tenants[:limit]

        for tenant in tenants:
            contents.append({
                'UUID': tenant.get('uuid'),
                'Name': tenant.get('name'),
                'ExternalID': tenant.get('externalId'),
                'Description': tenant.get('description'),
                'System': tenant.get('system')
            })

        context['SymantecMC.Tenant(val.UUID && val.UUID === obj.UUID)'] = createContext(contents, removeNull=True)

    headers = ['UUID', 'Name', 'ExternalID', 'Description', 'System']
    return_outputs(tableToMarkdown('Symantec Management Center Tenants', contents,
                                   removeNull=True, headers=headers, headerTransform=pascalToSpace), context, tenants)


def list_tenants_request():
    """
    Get devices from Symantec MC
    :return: List of Symantec MC tenants
    """

    path = 'tenants'
    params = {}

    response = http_request('GET', path, params)
    return response


''' COMMANDS '''
LOG('Command being called is ' + demisto.command())
handle_proxy()

COMMAND_DICTIONARY = {
    'test-module': test_module,
    'symantec-mc-list-devices': list_devices_command,
    'symantec-mc-get-device': get_device_command,
    'symantec-mc-get-device-health': get_device_health_command,
    'symantec-mc-get-device-license': get_device_license_command,
    'symantec-mc-get-device-status': get_device_status_command,
    'symantec-mc-list-policies': list_policies_command,
    'symantec-mc-get-policy': get_policy_command,
    'symantec-mc-create-policy': create_policy_command,
    'symantec-mc-update-policy': update_policy_command,
    'symantec-mc-delete-policy': delete_policy_command,
    'symantec-mc-add-policy-content': add_policy_content_command,
    'symantec-mc-delete-policy-content': delete_policy_content_command,
    'symantec-mc-list-tenants': list_tenants_command
}

try:
    command_func = COMMAND_DICTIONARY[demisto.command()]
    command_func()
except Exception as e:
    LOG(str(e))
    LOG.print_log()
    return_error(str(e))
