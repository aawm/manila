# Copyright 2013 Openstack Foundation
# Copyright 2015 Mirantis, Inc.
# All Rights Reserved.
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

from oslo_config import cfg
from oslo_log import log

from manila.common import constants
from manila import exception
from manila import network
from manila.network.neutron import api as neutron_api
from manila.network.neutron import constants as neutron_constants

neutron_single_network_plugin_opts = [
    cfg.StrOpt(
        'neutron_net_id',
        help="Default Neutron network that will be used for share server "
             "creation. This opt is used only with "
             "class 'NeutronSingleNetworkPlugin'.",
        deprecated_group='DEFAULT',
        default=None),
    cfg.StrOpt(
        'neutron_subnet_id',
        help="Default Neutron subnet that will be used for share server "
             "creation. Should be assigned to network defined in opt "
             "'neutron_net_id'. This opt is used only with "
             "class 'NeutronSingleNetworkPlugin'.",
        deprecated_group='DEFAULT',
        default=None),
]

CONF = cfg.CONF
LOG = log.getLogger(__name__)


class NeutronNetworkPlugin(network.NetworkBaseAPI):

    def __init__(self, *args, **kwargs):
        db_driver = kwargs.pop('db_driver', None)
        super(NeutronNetworkPlugin, self).__init__(db_driver=db_driver)
        self.neutron_api = neutron_api.API(*args, **kwargs)

    def allocate_network(self, context, share_server, share_network, **kwargs):
        """Allocate network resources using given network information.

        Create neutron ports for a given neutron network and subnet,
        create manila db records for allocated neutron ports.

        :param context: RequestContext object
        :param share_network: share network data
        :param kwargs: allocations parameters given by the back-end
                       driver. Supported params:
                       'count' - how many allocations should be created
                       'device_owner' - set owner for network allocations
        :rtype: list of :class: 'dict'
        """
        if not self._has_provider_network_extension():
            msg = "%s extension required" % neutron_constants.PROVIDER_NW_EXT
            raise exception.NetworkBadConfigurationException(reason=msg)

        self._save_neutron_network_data(context, share_network)
        self._save_neutron_subnet_data(context, share_network)

        allocation_count = kwargs.get('count', 1)
        device_owner = kwargs.get('device_owner', 'share')

        ports = []
        for __ in range(0, allocation_count):
            ports.append(self._create_port(context, share_server,
                                           share_network, device_owner))

        return ports

    def deallocate_network(self, context, share_server_id):
        """Deallocate neutron network resources for the given share server.

        Delete previously allocated neutron ports, delete manila db
        records for deleted ports.

        :param context: RequestContext object
        :param share_server_id: id of share server
        :rtype: None
        """
        ports = self.db.network_allocations_get_for_share_server(
            context, share_server_id)

        for port in ports:
            self._delete_port(context, port)

    def _create_port(self, context, share_server, share_network, device_owner):
        port = self.neutron_api.create_port(
            share_network['project_id'],
            network_id=share_network['neutron_net_id'],
            subnet_id=share_network['neutron_subnet_id'],
            device_owner='manila:' + device_owner)
        port_dict = {
            'id': port['id'],
            'share_server_id': share_server['id'],
            'ip_address': port['fixed_ips'][0]['ip_address'],
            'mac_address': port['mac_address'],
            'status': constants.STATUS_ACTIVE,
        }
        return self.db.network_allocation_create(context, port_dict)

    def _delete_port(self, context, port):
        try:
            self.neutron_api.delete_port(port['id'])
        except exception.NetworkException:
            self.db.network_allocation_update(
                context, port['id'], {'status': constants.STATUS_ERROR})
            raise
        else:
            self.db.network_allocation_delete(context, port['id'])

    def _has_provider_network_extension(self):
        extentions = self.neutron_api.list_extensions()
        return neutron_constants.PROVIDER_NW_EXT in extentions

    def _save_neutron_network_data(self, context, share_network):
        net_info = self.neutron_api.get_network(
            share_network['neutron_net_id'])

        provider_nw_dict = {
            'network_type': net_info['provider:network_type'],
            'segmentation_id': net_info['provider:segmentation_id']
        }

        self.db.share_network_update(context,
                                     share_network['id'],
                                     provider_nw_dict)

    def _save_neutron_subnet_data(self, context, share_network):
        subnet_info = self.neutron_api.get_subnet(
            share_network['neutron_subnet_id'])

        subnet_values = {
            'cidr': subnet_info['cidr'],
            'ip_version': subnet_info['ip_version']
        }

        self.db.share_network_update(context,
                                     share_network['id'],
                                     subnet_values)


class NeutronSingleNetworkPlugin(NeutronNetworkPlugin):

    def __init__(self, *args, **kwargs):
        super(NeutronSingleNetworkPlugin, self).__init__(*args, **kwargs)
        CONF.register_opts(
            neutron_single_network_plugin_opts,
            group=self.neutron_api.config_group_name)
        self.net = self.neutron_api.configuration.neutron_net_id
        self.subnet = self.neutron_api.configuration.neutron_subnet_id
        self._verify_net_and_subnet()

    def allocate_network(self, context, share_server, share_network, **kwargs):
        share_network = self._update_share_network_net_data(
            context, share_network)
        super(NeutronSingleNetworkPlugin, self).allocate_network(
            context, share_server, share_network, **kwargs)

    def _verify_net_and_subnet(self):
        data = dict(net=self.net, subnet=self.subnet)
        if self.net and self.subnet:
            net = self.neutron_api.get_network(self.net)
            if not (net.get('subnets') and data['subnet'] in net['subnets']):
                raise exception.NetworkBadConfigurationException(
                    "Subnet '%(subnet)s' does not belong to "
                    "network '%(net)s'." % data)
        else:
            raise exception.NetworkBadConfigurationException(
                "Neutron net and subnet are expected to be both set. "
                "Got: net=%(net)s and subnet=%(subnet)s." % data)

    def _update_share_network_net_data(self, context, share_network):
        upd = dict()
        if not share_network.get('neutron_net_id') == self.net:
            upd['neutron_net_id'] = self.net
        if not share_network.get('neutron_subnet_id') == self.subnet:
            upd['neutron_subnet_id'] = self.subnet
        if upd:
            share_network = self.db.share_network_update(
                context, share_network['id'], upd)
        return share_network
