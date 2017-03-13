import json

from ckan.lib import base
from ckan import logic, model
from ckan.plugins import toolkit
from ckan.common import c, _
from ckan import authz
import ckan.lib.helpers as h

from ckanext.requestdata.emailer import send_email

get_action = logic.get_action
NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError

abort = base.abort
BaseController = base.BaseController


def _get_context():
    return {
        'model': model,
        'session': model.Session,
        'user': c.user or c.author,
        'auth_user_obj': c.userobj
    }


def _get_action(action, data_dict):
    return toolkit.get_action(action)(_get_context(), data_dict)


class UserController(BaseController):

    def my_requested_data(self, id):
        '''Handles creating template for 'My Requested Data' page in the
        user's dashboard.

        :param id: The user's id.
        :type id: string

        :returns: template

        '''

        try:
            requests = _get_action('requestdata_request_list', {})
        except NotAuthorized:
            abort(403, _('Not authorized to see this page.'))

        c.is_myself = id == c.user

        if not c.is_myself:
            abort(403, _('Not authorized to see this page.'))

        requests_new = []
        requests_open = []
        requests_archive = []

        for item in requests:
            if item['state'] == 'new':
                requests_new.append(item)
            elif item['state'] == 'open':
                requests_open.append(item)
            elif item['state'] == 'archive':
                requests_archive.append(item)

        extra_vars = {
            'requests_new': requests_new,
            'requests_open': requests_open,
            'requests_archive': requests_archive
        }

        data_dict = {
            'id': id,
            'include_num_followers': True
        }

        self._setup_template_variables(_get_context(), data_dict)

        return toolkit.render('requestdata/my_requested_data.html', extra_vars)

    def _setup_template_variables(self, context, data_dict):
        c.is_sysadmin = authz.is_sysadmin(c.user)
        try:
            user_dict = get_action('user_show')(context, data_dict)
        except NotFound:
            abort(404, _('User not found'))
        except NotAuthorized:
            abort(403, _('Not authorized to see this page'))

        c.user_dict = user_dict
        c.about_formatted = h.render_markdown(user_dict['about'])

    def reply_request(self, username):
        '''Handles sending email to the person who created the request, as well
        as updating the state of the request to 'open'.

        :param username: The user's name.
        :type username: string

        :rtype: json

        '''

        data = dict(toolkit.request.POST)

        message_content = data.get('message_content')

        if message_content is None or message_content == '':
            payload = {
                'success': False,
                'error': {
                    'message_content': 'Missing value'
                }
            }

            return json.dumps(payload)

        to = data['send_to']
        from_ = c.userobj.email

        data.pop('send_to')

        try:
            _get_action('requestdata_request_patch', data)
        except NotAuthorized:
            abort(403, _('Not authorized to use this action.'))
        except ValidationError:
            error = {
                'success': False,
                'error': {
                    'message': 'An error occurred while sending the reply.'
                }
            }

            return json.dumps(error)

        response = send_email(message_content, to, from_)

        if response['success'] is False:
            error = {
                'success': False,
                'error': {
                    'message': response['message']
                }
            }

            return json.dumps(error)

        success = {
            'success': True
        }

        return json.dumps(success)
