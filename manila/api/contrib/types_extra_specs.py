# Copyright (c) 2011 Zadara Storage Inc.
# Copyright (c) 2011 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""The share types extra specs extension"""

import six
import webob

from manila.api import common
from manila.api import extensions
from manila.api.openstack import wsgi
from manila import db
from manila import exception
from manila.i18n import _
from manila import rpc
from manila.share import share_types

authorize = extensions.extension_authorizer('share', 'types_extra_specs')


class ShareTypeExtraSpecsController(wsgi.Controller):
    """The share type extra specs API controller for the OpenStack API."""

    def _get_extra_specs(self, context, type_id):
        extra_specs = db.share_type_extra_specs_get(context, type_id)
        specs_dict = {}
        for key, value in six.iteritems(extra_specs):
            specs_dict[key] = value
        return dict(extra_specs=specs_dict)

    def _check_type(self, context, type_id):
        try:
            share_types.get_share_type(context, type_id)
        except exception.NotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.msg)

    def _verify_extra_specs(self, extra_specs, verify_all_required=True):
        if verify_all_required:
            try:
                share_types.get_valid_required_extra_specs(extra_specs)
            except exception.InvalidExtraSpec as e:
                raise webob.exc.HTTPBadRequest(explanation=six.text_type(e))

        def is_valid_string(v):
            return isinstance(v, six.string_types) and len(v) in range(1, 256)

        def is_valid_extra_spec(k, v):
            valid_extra_spec_key = is_valid_string(k)
            valid_type = is_valid_string(v) or isinstance(v, bool)
            valid_required_extra_spec = (
                share_types.is_valid_required_extra_spec(k, v) in (None, True))
            return (valid_extra_spec_key
                    and valid_type
                    and valid_required_extra_spec)

        for k, v in six.iteritems(extra_specs):
            if is_valid_string(k) and isinstance(v, dict):
                self._verify_extra_specs(v)
            elif not is_valid_extra_spec(k, v):
                expl = _('Invalid extra_spec: %(key)s: %(value)s') % {
                    'key': k, 'value': v
                }
                raise webob.exc.HTTPBadRequest(explanation=expl)

    def index(self, req, type_id):
        """Returns the list of extra specs for a given share type."""
        context = req.environ['manila.context']
        authorize(context)
        self._check_type(context, type_id)
        return self._get_extra_specs(context, type_id)

    def create(self, req, type_id, body=None):
        context = req.environ['manila.context']
        authorize(context)

        if not self.is_valid_body(body, 'extra_specs'):
            raise webob.exc.HTTPBadRequest()

        self._check_type(context, type_id)
        specs = body['extra_specs']
        self._verify_extra_specs(specs, False)
        self._check_key_names(specs.keys())
        db.share_type_extra_specs_update_or_create(context, type_id, specs)
        notifier_info = dict(type_id=type_id, specs=specs)
        notifier = rpc.get_notifier('shareTypeExtraSpecs')
        notifier.info(context, 'share_type_extra_specs.create', notifier_info)
        return body

    def update(self, req, type_id, id, body=None):
        context = req.environ['manila.context']
        authorize(context)
        if not body:
            expl = _('Request body empty')
            raise webob.exc.HTTPBadRequest(explanation=expl)
        self._check_type(context, type_id)
        if id not in body:
            expl = _('Request body and URI mismatch')
            raise webob.exc.HTTPBadRequest(explanation=expl)
        if len(body) > 1:
            expl = _('Request body contains too many items')
            raise webob.exc.HTTPBadRequest(explanation=expl)
        self._verify_extra_specs(body, False)
        db.share_type_extra_specs_update_or_create(context, type_id, body)
        notifier_info = dict(type_id=type_id, id=id)
        notifier = rpc.get_notifier('shareTypeExtraSpecs')
        notifier.info(context, 'share_type_extra_specs.update', notifier_info)
        return body

    def show(self, req, type_id, id):
        """Return a single extra spec item."""
        context = req.environ['manila.context']
        authorize(context)
        self._check_type(context, type_id)
        specs = self._get_extra_specs(context, type_id)
        if id in specs['extra_specs']:
            return {id: specs['extra_specs'][id]}
        else:
            raise webob.exc.HTTPNotFound()

    def delete(self, req, type_id, id):
        """Deletes an existing extra spec."""
        context = req.environ['manila.context']
        self._check_type(context, type_id)
        authorize(context)

        if id in share_types.get_required_extra_specs():
            msg = _("Required extra specs can't be deleted.")
            raise webob.exc.HTTPForbidden(explanation=msg)

        try:
            db.share_type_extra_specs_delete(context, type_id, id)
        except exception.ShareTypeExtraSpecsNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        notifier_info = dict(type_id=type_id, id=id)
        notifier = rpc.get_notifier('shareTypeExtraSpecs')
        notifier.info(context, 'share_type_extra_specs.delete', notifier_info)
        return webob.Response(status_int=202)

    def _check_key_names(self, keys):
        if not common.validate_key_names(keys):
            expl = _('Key names can only contain alphanumeric characters, '
                     'underscores, periods, colons and hyphens.')

            raise webob.exc.HTTPBadRequest(explanation=expl)


class Types_extra_specs(extensions.ExtensionDescriptor):
    """Type extra specs support."""

    name = "TypesExtraSpecs"
    alias = "os-types-extra-specs"
    updated = "2011-08-24T00:00:00+00:00"

    def get_resources(self):
        resources = []
        res = extensions.ResourceExtension(
            'extra_specs',
            ShareTypeExtraSpecsController(),
            parent=dict(member_name='type',
                        collection_name='types')
        )
        resources.append(res)

        return resources
