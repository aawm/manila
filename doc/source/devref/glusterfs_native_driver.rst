..
      Copyright 2015 Red Hat, Inc.
      All Rights Reserved.

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

GlusterFS Native driver
=======================

GlusterFS Native driver uses GlusterFS, an open source distributed file system,
as the storage backend for serving file shares to Manila clients.

A Manila share is a GlusterFS volume. This driver uses flat-network
(share-server-less) model. Instances directly talk with the GlusterFS backend
storage pool. The instances use 'glusterfs' protocol to mount the GlusterFS
shares. Access to each share is allowed via TLS Certificates. Only the instance
which has the TLS trust established with the GlusterFS backend can mount and
hence use the share. Currently only 'rw' access is supported.

Network Approach
----------------

L3 connectivity between the storage backend and the host running the Manila
share service should exist.

Supported shared filesystems
----------------------------

- GlusterFS (access by TLS Certificates (``cert`` access type))

Multi-tenancy model
-------------------

The driver does not support network segmented multi-tenancy model. Instead
multi-tenancy is supported using tenant specific TLS certificates.

Supported Operations
--------------------

- Create GlusterFS Share
- Delete GlusterFS Share
- Allow GlusterFS Share access (rw)
- Deny GlusterFS Share access
- Create GlusterFS Snapshot
- Delete GlusterFS Snapshot

Requirements
------------

- Install glusterfs-server package, version >= 3.6.x, on the storage backend.
- Install glusterfs and glusterfs-fuse package, version >=3.6.x, on the Manila
  host.
- Establish network connection between the Manila host and the storage backend.


Manila driver configuration setting
-----------------------------------

The following parameters in Manila's configuration file need to be set:

- `share_driver` =
    manila.share.drivers.glusterfs_native.GlusterfsNativeShareDriver
- `glusterfs_servers` = List of GlusterFS servers which provide volumes
    that can be used to create shares. The servers are expected to be of
    distinct Gluster clusters (ie. should not be gluster peers). Each server
    should be of the form ``[<remoteuser>@]<glustervolserver>``.

    The optional ``<remoteuser>@`` part of the server URI indicates SSH
    access for cluster management (see related optional parameters below).
    If it is not given, direct command line management is performed (ie.
    Manila host is assumed to be part of the GlusterFS cluster the server
    belongs to).
- `glusterfs_volume_pattern` = Regular expression template
    used to filter GlusterFS volumes for share creation. The regex template can
    contain the #{size} parameter which matches a number (sequence of digits)
    and the value shall be intepreted as size of the volume in GB. Examples:
    ``manila-share-volume-\d+$``, ``manila-share-volume-#{size}G-\d+$``; with
    matching volume names, respectively: *manila-share-volume-12*,
    *manila-share-volume-3G-13*". In latter example, the number that matches
    ``#{size}``, that is, 3, is an indication that the size of volume is 3G.

The following configuration parameters are optional:

- `glusterfs_mount_point_base` =  <base path of GlusterFS volume mounted on
     Manila host>
- `glusterfs_path_to_private_key` = <path to Manila host's private key file>
- `glusterfs_server_password` = <password of remote GlusterFS server machine>


Known Restrictions
------------------

- GlusterFS volumes are not created on demand. A pre-existing set of
  GlusterFS volumes should be supplied by the GlusterFS cluster(s), conforming
  to the naming convention encoded by ``glusterfs_volume_pattern``. However,
  the GlusterFS endpoint is allowed to extend this set any time (so Manila
  and GlusterFS endpoints are expected to communicate volume supply/demand
  out-of-band). ``glusterfs_volume_pattern`` can include a size hint (with
  ``#{size}`` syntax), which, if present, requires the GlusterFS end to
  indicate the size of the shares in GB in the name. (On share creation,
  Manila picks volumes *at least* as big as the requested one.)
- Certificate setup (aka trust setup) between instance and storage backend is
  out of band of Manila.
- Support for 'create_share_from_snapshot' is planned for Liberty release.

The :mod:`manila.share.drivers.glusterfs_native.GlusterfsNativeShareDriver` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: manila.share.drivers.glusterfs_native
    :noindex:
    :members:
    :undoc-members:
    :show-inheritance:
