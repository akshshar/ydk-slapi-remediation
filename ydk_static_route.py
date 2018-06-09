#!/usr/bin/env python
#
# Copyright 2016 Cisco Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Create configuration for model Cisco-IOS-XR-ip-static-cfg.

optional arguments:
  -h, --help     show this help message and exit
  -v, --verbose  print debugging messages
"""

from argparse import ArgumentParser
from urlparse import urlparse

from ydk.services import CRUDService
from ydk.providers import NetconfServiceProvider
from ydk.models.cisco_ios_xr import Cisco_IOS_XR_ip_static_cfg \
    as xr_ip_static_cfg
import logging
import pdb, os
import sys,time
from interface import SLInterface
import signal
from functools import partial
import threading

from genpy import sl_common_types_pb2

logger = logging.getLogger("ydk")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(("%(asctime)s - %(name)s - "
                              "%(levelname)s - %(message)s"))
handler.setFormatter(formatter)
logger.addHandler(handler)

ACTIVE_PREFIX_DICT = { "prefix" : "15.1.1.0",
                       "prefixlen" : 24,
                       "next_hop_address" : "11.1.1.20",
                       "outgoing_interface" : "GigabitEthernet0/0/0/0",
                       "admin_distance" : 30}


BACKUP_PREFIX_DICT = { "prefix" : "15.1.1.0",
                       "prefixlen" : 24,
                       "next_hop_address" : "12.1.1.20",
                       "outgoing_interface" : "GigabitEthernet0/0/0/1",
                       "admin_distance" : 30}

class YDKStaticRoute(object):

    def __init__(self, device):

        self.address = device.hostname
        self.port = device.port
        self.username = device.username
        self.password = device.password
        self.protocol = device.scheme
        self.exit = False
        self.event_loop_done = False

        self.provider = NetconfServiceProvider(address=self.address,
                                      port=self.port,
                                      username=self.username,
                                      password=self.password,
                                      protocol=self.protocol,
                                      timeout=10000000)

        self.sl_interface = SLInterface()

        #self.event_thread = threading.Thread(target = self.wait_for_event)
        #self.event_thread.daemon = True
        #self.event_thread.start()

        self.slapi_intf_thread = threading.Thread(target = self.sl_interface.intf_listen_notifications)
        self.slapi_intf_thread.daemon = True
        self.slapi_intf_thread.start()
      
        print self.slapi_intf_thread

    def config_router_static(self,
                             router_static,
                             prefix_dict):
         
        """Add config data to router_static object."""
        vrf_unicast = router_static.default_vrf.address_family.vrfipv4.vrf_unicast
        vrf_prefix = vrf_unicast.vrf_prefixes.VrfPrefix()
        vrf_prefix.prefix = prefix_dict["prefix"]
        vrf_prefix.prefix_length = prefix_dict["prefixlen"]
        vrf_next_hop_interface_name_next_hop_address = vrf_prefix.vrf_route.vrf_next_hop_table. \
            VrfNextHopInterfaceNameNextHopAddress()
        vrf_next_hop_interface_name_next_hop_address.next_hop_address = prefix_dict["next_hop_address"] 
        vrf_next_hop_interface_name_next_hop_address.metric = prefix_dict["admin_distance"]
        vrf_next_hop_interface_name_next_hop_address.interface_name = prefix_dict["outgoing_interface"]
        vrf_prefix.vrf_route.vrf_next_hop_table.vrf_next_hop_interface_name_next_hop_address. \
            append(vrf_next_hop_interface_name_next_hop_address)
        vrf_unicast.vrf_prefixes.vrf_prefix.append(vrf_prefix)


    def takeaction(self, path):

        new_line="\n"

        crud = CRUDService() 
        if path == "active":
            router_static = xr_ip_static_cfg.RouterStatic()
            self.config_router_static(router_static, ACTIVE_PREFIX_DICT)
            crud.create(self.provider, router_static)
            print(10*new_line)
        else:
            router_static = xr_ip_static_cfg.RouterStatic()
            self.config_router_static(router_static, BACKUP_PREFIX_DICT)
            crud.create(self.provider, router_static)
            print(10*new_line)

    def wait_for_event(self):
       while True:
           if self.exit:
               self.event_loop_done = True
               break
           if self.sl_interface.path_event["status"]:
               time.sleep(1)
               self.takeaction(self.sl_interface.path_event["path"])
               self.sl_interface.path_event["status"] = False
               
           time.sleep(2)


EXIT_FLAG = False
# POSIX signal handler to ensure we shutdown cleanly
def handler(ydk_static_route, signum, frame):
    global EXIT_FLAG

    if not EXIT_FLAG:
        EXIT_FLAG = True
        ydk_static_route.exit = True
        while not ydk_static_route.event_loop_done:
            break

        print "Unregistering from the SLInterface vertical..."
        ydk_static_route.sl_interface.intf_register(sl_common_types_pb2.SL_REGOP_UNREGISTER)
        os._exit(0)


if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument("device",
                        help="NETCONF device (ssh://user:password@host:port)")
    args = parser.parse_args()
    device = urlparse(args.device)

    ydk_static_route = YDKStaticRoute(device)


    # Register our handler for keyboard interrupt and termination signals
    signal.signal(signal.SIGINT, partial(handler, ydk_static_route))
    signal.signal(signal.SIGTERM, partial(handler, ydk_static_route))

    # The process main thread does nothing but wait for signals
    #signal.pause()

    ydk_static_route.wait_for_event()
