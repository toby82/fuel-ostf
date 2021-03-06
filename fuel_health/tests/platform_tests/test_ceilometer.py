# Copyright 2013 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from fuel_health import ceilometermanager
from fuel_health.common.utils.data_utils import rand_name


class CeilometerApiPlatformTests(ceilometermanager.CeilometerBaseTest):
    """TestClass contains tests that check basic Ceilometer functionality."""

    def test_check_alarm_state(self):
        """Ceilometer test to check alarm status and get Nova metrics.
        Target component: Ceilometer

        Scenario:
            1. Create a new instance.
            2. Instance become active.
            3. Wait for Nova notifications.
            4. Wait for Nova pollsters.
            5. Wait for Nova statistic.
            6. Create a new alarm.
            7. Verify that become status 'alarm' or 'ok'.
        Duration: 60 s.

        Deployment tags: Ceilometer
        """

        self.check_image_exists()

        name = rand_name('ost1-test-ceilo-instance-')

        fail_msg = "Creation instance is failed."
        msg = "Instance was created."

        vcenter = self.config.compute.use_vcenter
        image_name = 'TestVM-VMDK' if vcenter else None

        instance = self.verify(600, self._create_server, 1, fail_msg, msg,
                               self.compute_client, name, img_name=image_name)

        fail_msg = "Instance is not available."
        msg = "instance becoming available."

        self.verify(200, self.wait_for_instance_status, 2,
                    fail_msg, msg,
                    instance, 'ACTIVE')

        fail_msg = "Nova notifications is not received."
        msg = "Nova notifications is received."
        query = [{'field': 'resource', 'op': 'eq', 'value': instance.id}]

        notifications = self.nova_notifications if not vcenter else []

        self.verify(600, self.wait_metrics, 3,
                    fail_msg, msg, notifications, query)

        pollsters = (self.nova_pollsters if not vcenter
                     else self.nova_vsphere_pollsters)

        pollsters.append("".join(["instance:",
                                  self.compute_client.flavors.get(
                                      instance.flavor['id']).name]))

        fail_msg = "Nova pollsters is not received."
        msg = "Nova pollsters is received."
        self.verify(600, self.wait_metrics, 4,
                    fail_msg, msg, pollsters, query)

        fail_msg = "Statistic for Nova notification:cpu_util is not received."
        msg = "Statistic for Nova notification:cpu_util is received."

        cpu_util_stat = self.verify(60, self.wait_for_statistic_of_metric, 5,
                                    fail_msg, msg,
                                    "cpu_util",
                                    query)

        fail_msg = "Creation alarm for sum cpu_util is failed."
        msg = "Creation alarm for sum cpu_util is successful."
        threshold = cpu_util_stat[0].sum - 1

        alarm = self.verify(60, self.create_alarm, 6,
                            fail_msg, msg,
                            meter_name="cpu_util",
                            threshold=threshold,
                            name=rand_name('ceilometer-alarm'),
                            period=600,
                            statistic='sum',
                            comparison_operator='lt')

        fail_msg = "Alarm verify state is failed."
        msg = "Alarm status becoming."

        self.verify(1000, self.wait_for_alarm_status, 7,
                    fail_msg, msg,
                    alarm.alarm_id)

    def test_create_sample(self):
        """Ceilometer create, check, list samples
        Target component: Ceilometer

        Scenario:
        1. Request samples list for image resource.
        2. Create new sample for image resource.
        3. Check that created sample has the expected resource.
        4. Get samples and compare sample lists before and after create sample.
        5. Get resource of sample.
        Duration: 5 s.
        Deployment tags: Ceilometer
        """

        self.check_image_exists()
        image_id = self.get_image_from_name()
        query = [{'field': 'resource', 'op': 'eq', 'value': image_id}]

        fail_msg = 'Get samples for update image is failed.'
        msg = 'Get samples for update image is successful.'

        list_before_create_sample = self.verify(
            60, self.ceilometer_client.samples.list, 1,
            fail_msg, msg,
            self.glance_notifications[0], q=query)

        fail_msg = 'Creation sample for update image is failed.'
        msg = 'Creation sample for update image is successful.'

        sample = self.verify(60, self.ceilometer_client.samples.create, 2,
                             fail_msg, msg,
                             resource_id=image_id,
                             counter_name=self.glance_notifications[0],
                             counter_type='delta',
                             counter_unit='image',
                             counter_volume=1,
                             resource_metadata={"user": "example_metadata"})

        fail_msg = 'Resource of sample is absent or not equal with expected.'

        self.verify_response_body_value(
            body_structure=sample[0].resource_id,
            value=image_id,
            msg=fail_msg,
            failed_step=3)

        fail_msg = """List of samples after creating test sample isn't
        greater than initial list of samples"""
        msg = 'New test sample was added to the list of samples'

        self.verify(
            20, self.wait_samples_count, 4,
            fail_msg, msg,
            self.glance_notifications[0], query,
            len(list_before_create_sample))

        fail_msg = 'Getting resource of sample is failed.'
        msg = 'Getting resource of sample is successful.'

        self.verify(20, self.ceilometer_client.resources.get, 5,
                    fail_msg, msg, sample[0].resource_id)

    def test_check_volume_notifications(self):
        """Ceilometer test to check get Cinder notifications.
        Target component: Ceilometer

        Scenario:
        1. Create volume.
        2. Check volume notifications.
        3. Create volume snapshot.
        4. Check volume snapshot notifications.
        Duration: 10 s.
        Deployment tags: Ceilometer
        """

        if (not self.config.volume.cinder_node_exist
                and not self.config.volume.ceph_exist):
            self.skipTest("There are no cinder nodes or "
                          "ceph storage for volume")

        fail_msg = "Creation volume failed"
        msg = "Volume was created"

        volume = self.verify(60, self._create_volume, 1,
                             fail_msg, msg,
                             self.volume_client,
                             'available')

        query = [{'field': 'resource', 'op': 'eq', 'value': volume.id}]
        fail_msg = "Volume notifications are not received."
        msg = "Volume notifications are received."

        self.verify(600, self.wait_metrics, 2,
                    fail_msg, msg,
                    self.volume_notifications, query)

        fail_msg = "Creation volume snapshot failed"
        msg = "Volume snapshot was created"

        snapshot = self.verify(60, self._create_snapshot, 3,
                               fail_msg, msg,
                               self.volume_client,
                               volume.id, 'available')

        query = [{'field': 'resource', 'op': 'eq', 'value': snapshot.id}]
        fail_msg = "Volume snapshot notifications are not received."
        msg = "Volume snapshot notifications are received."

        self.verify(600, self.wait_metrics, 4,
                    fail_msg, msg,
                    self.snapshot_notifications, query)

    def test_check_glance_notifications(self):
        """Ceilometer test to check get Glance notifications.
        Target component: Ceilometer

        Scenario:
        1. Check glance notifications.
        Duration: 5 s.
        Deployment tags: Ceilometer
        """
        image = self.glance_helper()
        query = [{'field': 'resource', 'op': 'eq', 'value': image.id}]

        fail_msg = "Glance notifications are not received."
        msg = "Glance notifications are received."

        self.verify(600, self.wait_metrics, 1,
                    fail_msg, msg,
                    self.glance_notifications, query)

    def test_check_keystone_notifications(self):
        """Ceilometer test to check get Keystone notifications.
        Target component: Ceilometer

        Scenario:
        1. Check keystone project notifications.
        2. Check keystone user notifications.
        3. Check keystone role notifications.
        4. Check keystone group notifications.
        Duration: 5 s.
        Available since release: 2014.2-6.0
        Deployment tags: Ceilometer
        """

        tenant, user, role, group, trust = self.identity_helper()

        fail_msg = "Keystone project notifications are not received."
        msg = "Keystone project notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': tenant.id}]
        self.verify(600, self.wait_metrics, 1,
                    fail_msg, msg,
                    self.keystone_project_notifications, query)

        fail_msg = "Keystone user notifications are not received."
        msg = "Keystone user notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': user.id}]
        self.verify(600, self.wait_metrics, 2,
                    fail_msg, msg,
                    self.keystone_user_notifications, query)

        fail_msg = "Keystone role notifications are not received."
        msg = "Keystone role notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': role.id}]
        self.verify(600, self.wait_metrics, 3,
                    fail_msg, msg,
                    self.keystone_role_notifications, query)

        fail_msg = "Keystone group notifications are not received."
        msg = "Keystone group notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': group.id}]
        self.verify(600, self.wait_metrics, 4,
                    fail_msg, msg,
                    self.keystone_group_notifications, query)

        fail_msg = "Keystone trust notifications are not received."
        msg = "Keystone trust notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': trust.id}]
        self.verify(600, self.wait_metrics, 5,
                    fail_msg, msg,
                    self.keystone_trust_notifications, query)

    def test_check_neutron_notifications(self):
        """Ceilometer test to check get Neutron notifications.
        Target component: Ceilometer

        Scenario:
        1. Check neutron network notifications.
        2. Check neutron subnet notifications.
        3. Check neutron port notifications.
        4. Check neutron router notifications.
        5. Check neutron floating ip notifications.
        Duration: 40 s.
        Deployment tags: Ceilometer, neutron
        """

        net, subnet, port, router, flip = self.neutron_helper()

        fail_msg = "Neutron network notifications are not received."
        msg = "Neutron network notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': net["id"]}]
        self.verify(60, self.wait_metrics, 1,
                    fail_msg, msg,
                    self.neutron_network_notifications, query)

        fail_msg = "Neutron subnet notifications are not received."
        msg = "Neutron subnet notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': subnet["id"]}]
        self.verify(60, self.wait_metrics, 2,
                    fail_msg, msg,
                    self.neutron_subnet_notifications, query)

        fail_msg = "Neutron port notifications are not received."
        msg = "Neutron port notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': port["id"]}]
        self.verify(60, self.wait_metrics, 3,
                    fail_msg, msg,
                    self.neutron_port_notifications, query)

        fail_msg = "Neutron router notifications are not received."
        msg = "Neutron router notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': router["id"]}]
        self.verify(60, self.wait_metrics, 4,
                    fail_msg, msg,
                    self.neutron_router_notifications, query)

        fail_msg = "Neutron floating ip notifications are not received."
        msg = "Neutron floating ip notifications are received."
        query = [{'field': 'resource', 'op': 'eq', 'value': flip["id"]}]
        self.verify(60, self.wait_metrics, 5,
                    fail_msg, msg,
                    self.neutron_floatingip_notifications, query)

    def test_check_sahara_notifications(self):
        """Ceilometer test to check get Sahara notifications.
        Target component: Ceilometer

        Scenario:
        1. Find and check Sahara image
        2. Create Sahara cluster
        3. Check Sahara cluster notification
        Duration: 40 s.
        Deployment tags: Ceilometer, Sahara
        """

        plugin_name = 'vanilla'
        hadoop_version = '2.4.1'

        fail_msg = ("Sahara image is not correctly registered or it is not "
                    "registered at all. Correct image for Sahara not found.")
        msg = "Image was found and registered for Sahara."

        image_id = self.verify(60, self.find_and_check_image, 1,
                               fail_msg, msg, plugin_name, hadoop_version)

        if image_id is None:
            self.skipTest('Image for creating Sahara cluster not found')

        fail_msg = "Creation of Sahara cluster failed."
        msg = "Sahara cluster was created"

        cluster = self.verify(300, self.sahara_helper, 2,
                              fail_msg, msg,
                              image_id, plugin_name, hadoop_version)

        fail_msg = "Sahara cluster notifications were not received."
        msg = "Sahara cluster notifications were received."
        query = [{'field': 'resource', 'op': 'eq', 'value': cluster.id}]
        self.verify(60, self.wait_metrics, 3,
                    fail_msg, msg,
                    self.sahara_cluster_notifications, query)
