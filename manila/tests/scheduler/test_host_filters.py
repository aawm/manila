# Copyright 2011 OpenStack LLC.  # All Rights Reserved.
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
"""
Tests For Scheduler Host Filters.
"""

from oslo_serialization import jsonutils

from manila import context
from manila.openstack.common.scheduler import filters
from manila import test
from manila.tests.scheduler import fakes
from manila import utils


class HostFiltersTestCase(test.TestCase):
    """Test case for host filters."""

    def setUp(self):
        super(HostFiltersTestCase, self).setUp()
        self.context = context.RequestContext('fake', 'fake')
        self.json_query = jsonutils.dumps(
            ['and', ['>=', '$free_capacity_gb', 1024],
             ['>=', '$total_capacity_gb', 10 * 1024]])
        # This has a side effect of testing 'get_filter_classes'
        # when specifying a method (in this case, our standard filters)
        filter_handler = filters.HostFilterHandler('manila.scheduler.filters')
        classes = filter_handler.get_all_classes()
        self.class_map = {}
        for cls in classes:
            self.class_map[cls.__name__] = cls

    def _stub_service_is_up(self, ret_value):
        def fake_service_is_up(service):
            return ret_value
        self.mock_object(utils, 'service_is_up', fake_service_is_up)

    def test_capacity_filter_passes(self):
        self._stub_service_is_up(True)
        filt_cls = self.class_map['CapacityFilter']()
        filter_properties = {'size': 100}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_capacity_gb': 200,
                                    'updated_at': None,
                                    'service': service})
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_capacity_filter_current_host_passes(self):
        self._stub_service_is_up(True)
        filt_cls = self.class_map['CapacityFilter']()
        filter_properties = {'size': 100, 'share_exists_on': 'host1#pool1'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1#pools1',
                                   {'free_capacity_gb': 200,
                                    'updated_at': None,
                                    'service': service})
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_capacity_filter_fails(self):
        self._stub_service_is_up(True)
        filt_cls = self.class_map['CapacityFilter']()
        filter_properties = {'size': 100}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_capacity_gb': 120,
                                    'reserved_percentage': 20,
                                    'updated_at': None,
                                    'service': service})
        self.assertFalse(filt_cls.host_passes(host, filter_properties))

    def test_capacity_filter_passes_infinite(self):
        self._stub_service_is_up(True)
        filt_cls = self.class_map['CapacityFilter']()
        filter_properties = {'size': 100}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_capacity_gb': 'infinite',
                                    'updated_at': None,
                                    'service': service})
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_capacity_filter_passes_unknown(self):
        self._stub_service_is_up(True)
        filt_cls = self.class_map['CapacityFilter']()
        filter_properties = {'size': 100}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_capacity_gb': 'unknown',
                                    'updated_at': None,
                                    'service': service})
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_retry_filter_disabled(self):
        # Test case where retry/re-scheduling is disabled.
        filt_cls = self.class_map['RetryFilter']()
        host = fakes.FakeHostState('host1', {})
        filter_properties = {}
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_retry_filter_pass(self):
        # Node not previously tried.
        filt_cls = self.class_map['RetryFilter']()
        host = fakes.FakeHostState('host1', {})
        retry = dict(num_attempts=2, hosts=['host2'])
        filter_properties = dict(retry=retry)
        self.assertTrue(filt_cls.host_passes(host, filter_properties))

    def test_retry_filter_fail(self):
        # Node was already tried.
        filt_cls = self.class_map['RetryFilter']()
        host = fakes.FakeHostState('host1', {})
        retry = dict(num_attempts=1, hosts=['host1'])
        filter_properties = dict(retry=retry)
        self.assertFalse(filt_cls.host_passes(host, filter_properties))
