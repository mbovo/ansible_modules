# Copyright: (c) 2019, Manuel Bovo <manuel.bovo@gmail.com>
# MIT License (see LICENSE.md )

from __future__ import absolute_import, division, print_function

from ansible.module_utils.api import basic_auth_argument_spec
from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible.module_utils._text import to_text, to_native
from urllib.parse import urlparse
import json
import traceback

GITLAB_IMP_ERR = None
try:
    from grafana_api.grafana_face import GrafanaFace
    HAS_GRAFANA_PACKAGE = True
except Exception:
    GRAFANA_IMP_ERR = traceback.format_exc()
    HAS_GRAFANA_PACKAGE = False

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: grafana_team
author:
  - Manuel Bovo (@mbovo)
version_added: 2.9
short_description: Manage Grafana Teams
description:
    - "Create, update, delete Grafana Teams"
options:
    
'''

EXAMPLES = '''
- hosts: localhost
  connection: local
  tasks:
    - name: Create Team
      grafana_team:
        state: present
        grafana_url: "https://grafana.com"
        grafana_user: "admin"
        grafana_password: "admin"
        validate_certs: false
        name: "teamName"
        email: "team@email.com"
'''

RETURN = '''
members:
    description: The list of tuples (id, login, email)
    type: list
    returned: onSuccess
teamId:
    description: the team ID
    type: str
    returned: onSuccess
'''

__metaclass__ = type

def grafana_dashboard_id_from_name(graf: GrafanaFace, name):
  ret = graf.search.search_dashboards(name)
  if len(ret) == 0:
    raise Exception("No dashboard found named %s" % name)
  if len(ret) > 1 :
    raise Exception("Multiple dashboard found with name %s" % name)
  if ret[0]['type'] != 'dash-db':
    raise Exception("No dashboard found named %s" % name)
  d_id = ret[0]['id']
  d_uid = ret[0]['uid']

  return (d_id,d_uid)

def grafana_get_permission(graf: GrafanaFace, name):
  did, duid = grafana_dashboard_id_from_name(graf, name)
  perms = graf.dashboard.get_dashboard_permissions(did)
  return perms, did, duid

def grafana_search_permission(perms, ptype, target_name) -> bool:
  for perm in perms:
    if ptype == 'team':
      if perm['team'] == target_name:
        return True
    elif ptype == 'user':
      if perm['userLogin'] == target_name or perm['userEmail'] == target_name:
        return True
    elif ptype == 'role':
      if 'role' in perm and  str(perm['role']).lower() == str(target_name).lower():
        return True
    
  return False


def grafana_team_id_by_name(graf: GrafanaFace, name:str) -> str:
  team = graf.teams.get_team_by_name(name)
  return team[0]['id']


def grafana_user_id_by_name(graf: GrafanaFace, name:str) -> str:
  user = graf.users.find_user(name)
  return user[0]['id']

def grafana_add_permission(graf: GrafanaFace, module: AnsibleModule, data):
  perms, did, _ = grafana_get_permission(graf, data['dashboard'])
  found = grafana_search_permission(perms, data['type'], data['target_name'])
  
  mapPermNameToID = {'view': '1', 'edit': '2', 'admin': '4'}

  if not found:
    newPerm = {'permission': mapPermNameToID[data['role']]}
    if data['type'] == 'team':
      newPerm['teamId'] = grafana_team_id_by_name(graf, data['target_name'])
    elif data['type'] == 'user':
      newPerm['userId'] = grafana_user_id_by_name(graf, data['target_name'])
    elif data['type'] == 'role':
      newPerm['role'] = str(data['target_name']).capitalize()
    
    perms.append(newPerm)

    return graf.dashboard.update_dashboard_permissions(did, perms)

  return {'changed':False}

def grafana_delete_permission(graf: GrafanaFace, module: AnsibleModule, data):
  pass

def main():
  argument_spec = basic_auth_argument_spec()
  argument_spec.update(
      state=dict(choices=['present', 'absent'], default='present'),
      api_url=dict(aliases=['url', 'grafana_url'], type='str', required=True),
      api_username=dict(aliases=['grafana_user'], type='str', default='admin'),
      api_password=dict(aliases=['grafana_password'],type='str', default='admin', no_log=True),
      grafana_api_key=dict(aliases=['api_key'], type='str', no_log=True),
      # validate_certs inherited from basic_auth_argument_spec
      dashboard=dict(type='str', required=True, aliases=['dashboard_name']),
      type=dict(choices=['role','team','user'], default='role'),
      target_name=dict(type='str', default='Viewer', aliases=['target']),
      role=dict(choices=['view','edit','admin'], default='view')
  )

  module = AnsibleModule(
      argument_spec=argument_spec,
      supports_check_mode=False,
      required_together=[['api_username', 'api_password']],
      mutually_exclusive=[['grafana_api_key', 'api_username'], [
          'grafana_api_key', 'api_password']],
      required_one_of=[['grafana_api_key', 'api_username']]
  )

  if not HAS_GRAFANA_PACKAGE:
        module.fail_json(msg=missing_required_lib(
            "grafana-api"), exception=GRAFANA_IMP_ERR)

  try:

    if module.params['grafana_api_key'] is not None:
      auth = module.params['grafana_api_key']
    else:
      auth = (module.params['api_username'], module.params['api_password'])

    uri = urlparse(module.params['api_url'])

    graf = GrafanaFace(auth,
                       host=uri.hostname,
                       port=uri.port,
                       protocol=uri.scheme,
                       verify=module.params['validate_certs']
                       )


    if module.params['state'] == 'present':
      result = grafana_add_permission(graf, module, module.params)
    else:
      result = grafana_delete_permission(graf, module, module.param)
  except Exception as e:
    module.fail_json(
        failed=True,
        msg="error: %s" % to_native(e)
    )

    return

  module.exit_json(
      failed=False,
      **result
  )
  return


if __name__ == '__main__':
    main()
