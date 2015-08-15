# Copyright (C) 2009-2011 Wander Lairson Costa
#
# The following terms apply to all files associated
# with the software unless explicitly disclaimed in individual files.
#
# The authors hereby grant permission to use, copy, modify, distribute,
# and license this software and its documentation for any purpose, provided
# that existing copyright notices are retained in all copies and that this
# notice is included verbatim in any distributions. No written agreement,
# license, or royalty fee is required for any of the authorized uses.
# Modifications to this software may be copyrighted by their authors
# and need not follow the licensing terms described here, provided that
# the new terms are clearly indicated on the first page of each file where
# they apply.
#
# IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
# FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
# ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
# DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
# IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
# NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
# MODIFICATIONS.

from ctypes import *
import ctypes.util
import usb.util
from usb._debug import methodtrace
import logging

__author__ = 'Wander Lairson Costa'

__all__ = ['get_backend']

_logger = logging.getLogger('usb.backend.openusb')

class _usb_endpoint_desc(Structure):
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('bEndpointAddress', c_uint8),
                ('bmAttributes', c_uint8),
                ('wMaxPacketSize', c_uint16),
                ('bInterval', c_uint8),
                ('bRefresh', c_uint8),
                ('bSynchAddress', c_uint8)]

class _usb_interface_desc(Structure):
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('bInterfaceNumber', c_uint8),
                ('bAlternateSetting', c_uint8),
                ('bNumEndpoints', c_uint8),
                ('bInterfaceClass', c_uint8),
                ('bInterfaceSubClass', c_uint8),
                ('bInterfaceProtocol', c_uint8),
                ('iInterface', c_uint8)]

class _usb_config_desc(Structure):
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('wTotalLength', c_uint16),
                ('bNumInterfaces', c_uint8),
                ('bConfigurationValue', c_uint8),
                ('iConfiguration', c_uint8),
                ('bmAttributes', c_uint8),
                ('bMaxPower', c_uint8)]

class _usb_device_desc(Structure):
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('bcdUSB', c_uint16),
                ('bDeviceClass', c_uint8),
                ('bDeviceSubClass', c_uint8),
                ('bDeviceProtocol', c_uint8),
                ('bMaxPacketSize0', c_uint8),
                ('idVendor', c_uint16),
                ('idProduct', c_uint16),
                ('bcdDevice', c_uint16),
                ('iManufacturer', c_uint8),
                ('iProduct', c_uint8),
                ('iSerialNumber', c_uint8),
                ('bNumConfigurations', c_uint8)]

class _openusb_request_result(Structure):
    _fields_ = [('status', c_int32),
                ('transfered_bytes', c_uint32)]

class _openusb_ctrl_request(Structure):

    class _openusb_ctrl_setup(Structure):
        _fields_ = [('bmRequestType', c_uint8),
                    ('bRequest', c_uint8),
                    ('wValue', c_uint16),
                    ('wIndex', c_uint16)]
    _fields_ = [('payload', POINTER(c_uint8)),
                ('length', c_uint32),
                ('timeout', c_uint32),
                ('flags', c_uint32),
                ('result', _openusb_request_result),
                ('next', c_void_p)]

class _openusb_intr_request(Structure):
    _fields_ = [('interval', c_uint16),
                ('payload', POINTER(c_uint8)),
                ('length', c_uint32),
                ('timeout', c_uint32),
                ('flags', c_uint32),
                ('result', _openusb_request_result),
                ('next', c_void_p)]

class _openusb_bulk_request(Structure):
    _fields_ = [('payload', POINTER(c_uint8)),
                ('length', c_uint32),
                ('timeout', c_uint32),
                ('flags', c_uint32),
                ('result', _openusb_request_result),
                ('next', c_void_p)]

class _openusb_isoc_pkts(Structure):

    class _openusb_isoc_packet(Structure):
        _fields_ = [('payload', POINTER(c_uint8)),
                    ('length', c_uint32)]
    _fields_ = [('num_packets', c_uint32),
                ('packets', POINTER(_openusb_isoc_packet))]

class _openusb_isoc_request(Structure):
    _fields_ = [('start_frame', c_uint32),
                ('flags', c_uint32),
                ('pkts', _openusb_isoc_pkts),
                ('isoc_results', POINTER(_openusb_request_result)),
                ('isoc_status', c_int32),
                ('next', c_void_p)]

_openusb_devid = c_uint64
_openusb_busid = c_uint64
_openusb_handle = c_uint64
_openusb_dev_handle = c_uint64

_lib = None
_ctx = None

def _load_library():
    libname = ctypes.util.find_library('openusb')
    if libname is None:
        raise OSError('USB library could not be found')
    return CDLL(libname)

def _setup_prototypes(lib):
    # int32_t openusb_init(uint32_t flags , openusb_handle_t *handle);
    lib.openusb_init.argtypes = [c_uint32, POINTER(_openusb_handle)]
    lib.openusb_init.restype = c_int32

    # void openusb_fini(openusb_handle_t handle );
    lib.openusb_fini.argtypes = [_openusb_handle]

    # uint32_t openusb_get_busid_list(openusb_handle_t handle,
    #                                 openusb_busid_t **busids,
    #                                 uint32_t *num_busids);
    lib.openusb_get_busid_list.argtypes = [
            _openusb_handle,
            POINTER(POINTER(_openusb_busid)),
            POINTER(c_uint32)
        ]

    # void openusb_free_busid_list(openusb_busid_t * busids);
    lib.openusb_free_busid_list.argtypes = [POINTER(_openusb_busid)]

    # uint32_t openusb_get_devids_by_bus(openusb_handle_t handle,
    #                                    openusb_busid_t busid,
    #                                    openusb_devid_t **devids,
    #                                    uint32_t *num_devids);
    lib.openusb_get_devids_by_bus.argtypes = [
                _openusb_handle,
                _openusb_busid,
                POINTER(POINTER(_openusb_devid)),
                POINTER(c_uint32)
            ]

    lib.openusb_get_devids_by_bus.restype = c_int32

    # void openusb_free_devid_list(openusb_devid_t * devids);
    lib.openusb_free_devid_list.argtypes = [POINTER(_openusb_devid)]

    # int32_t openusb_open_device(openusb_handle_t handle,
    #                             openusb_devid_t devid ,
    #                             uint32_t flags,
    #                             openusb_dev_handle_t *dev);
    lib.openusb_open_device.argtypes = [
                _openusb_handle,
                _openusb_devid,
                c_uint32,
                POINTER(_openusb_dev_handle)
            ]

    lib.openusb_open_device.restype = c_int32

    # int32_t openusb_close_device(openusb_dev_handle_t dev);
    lib.openusb_close_device.argtypes = [_openusb_dev_handle]
    lib.openusb_close_device.restype = c_int32

    # int32_t openusb_set_configuration(openusb_dev_handle_t dev,
    #                                   uint8_t cfg);
    lib.openusb_set_configuration.argtypes = [_openusb_dev_handle, c_uint8]
    lib.openusb_set_configuration.restype = c_int32

    # int32_t openusb_get_configuration(openusb_dev_handle_t dev,
    #                                   uint8_t *cfg);
    lib.openusb_get_configuration.argtypes = [_openusb_dev_handle, POINTER(c_uint8)]
    lib.openusb_get_configuration.restype = c_int32

    # int32_t openusb_claim_interface(openusb_dev_handle_t dev,
    #                                 uint8_t ifc,
    #                                 openusb_init_flag_t flags);
    lib.openusb_claim_interface.argtypes = [
            _openusb_dev_handle,
            c_uint8,
            c_int
        ]

    lib.openusb_claim_interface.restype = c_int32

    # int32_t openusb_release_interface(openusb_dev_handle_t dev,
    #                                   uint8_t ifc);
    lib.openusb_release_interface.argtypes = [
            _openusb_dev_handle,
            c_uint8
        ]

    lib.openusb_release_interface.restype = c_int32

    # int32_topenusb_set_altsetting(openusb_dev_handle_t dev,
    #                               uint8_t ifc,
    #                               uint8_t alt);
    lib.openusb_set_altsetting.argtypes = [
            _openusb_dev_handle,
            c_uint8,
            c_uint8
        ]
    lib.openusb_set_altsetting.restype = c_int32

    # int32_t openusb_reset(openusb_dev_handle_t dev);
    lib.openusb_reset.argtypes = [_openusb_dev_handle]
    lib.openusb_reset.restype = c_int32

    # int32_t openusb_parse_device_desc(openusb_handle_t handle,
    #                                   openusb_devid_t devid,
    #                                   uint8_t *buffer,
    #                                   uint16_t buflen,
    #                                   usb_device_desc_t *devdesc);
    lib.openusb_parse_device_desc.argtypes = [
            _openusb_handle,
            _openusb_devid,
            POINTER(c_uint8),
            c_uint16,
            POINTER(_usb_device_desc)
        ]

    lib.openusb_parse_device_desc.restype = c_int32

    # int32_t openusb_parse_config_desc(openusb_handle_t handle,
    #                                   openusb_devid_t devid,
    #                                   uint8_t *buffer,
    #                                   uint16_t buflen,
    #                                   uint8_t cfgidx,
    #                                   usb_config_desc_t *cfgdesc);
    lib.openusb_parse_config_desc.argtypes = [
                _openusb_handle,
                _openusb_devid,
                POINTER(c_uint8),
                c_uint16,
                c_uint8,
                POINTER(_usb_config_desc)
            ]
    lib.openusb_parse_config_desc.restype = c_int32

    # int32_t openusb_parse_interface_desc(openusb_handle_t handle,
    #                                      openusb_devid_t devid,
    #                                      uint8_t *buffer,
    #                                      uint16_t buflen,
    #                                      uint8_t cfgidx,
    #                                      uint8_t ifcidx,
    #                                      uint8_t alt,
    #                                      usb_interface_desc_t *ifcdesc);
    lib.openusb_parse_interface_desc.argtypes = [
                    _openusb_handle,
                    _openusb_devid,
                    POINTER(c_uint8),
                    c_uint16,
                    c_uint8,
                    c_uint8,
                    c_uint8,
                    POINTER(_usb_interface_desc)
                ]

    lib.openusb_parse_interface_desc.restype = c_int32

    # int32_t openusb_parse_endpoint_desc(openusb_handle_t handle,
    #                                     openusb_devid_t devid,
    #                                     uint8_t *buffer,
    #                                     uint16_t buflen,
    #                                     uint8_t cfgidx,
    #                                     uint8_t ifcidx,
    #                                     uint8_t alt,
    #                                     uint8_t eptidx,
    #                                     usb_endpoint_desc_t *eptdesc);
    lib.openusb_parse_endpoint_desc.argtypes = [
                    _openusb_handle,
                    _openusb_devid,
                    POINTER(c_uint8),
                    c_uint16,
                    c_uint8,
                    c_uint8,
                    c_uint8,
                    c_uint8,
                    POINTER(_usb_endpoint_desc)
                ]

    lib.openusb_parse_interface_desc.restype = c_int32

    # const char *openusb_strerror(int32_t error );
    lib.openusb_strerror.argtypes = [c_int32]
    lib.openusb_strerror.restype = c_char_p

    # int32_t openusb_ctrl_xfer(openusb_dev_handle_t dev,
    #                           uint8_t ifc,
    #                           uint8_t ept,
    #                           openusb_ctrl_request_t *ctrl);
    lib.openusb_ctrl_xfer.argtypes = [
            _openusb_dev_handle,
            c_uint8,
            c_uint8,
            POINTER(_openusb_ctrl_request)
        ]

    lib.openusb_ctrl_xfer.restype = c_int32

    # int32_t openusb_intr_xfer(openusb_dev_handle_t dev,
    #                           uint8_t ifc,
    #                           uint8_t ept,
    #                           openusb_intr_request_t *intr);
    lib.openusb_intr_xfer.argtypes = [
                _openusb_dev_handle,
                c_uint8,
                c_uint8,
                POINTER(_openusb_intr_request)
            ]

    lib.openusb_bulk_xfer.restype = c_int32

    # int32_t openusb_bulk_xfer(openusb_dev_handle_t dev,
    #                           uint8_t ifc,
    #                           uint8_t ept,
    #                           openusb_bulk_request_t *bulk);
    lib.openusb_bulk_xfer.argtypes = [
            _openusb_dev_handle,
            c_uint8,
            c_uint8,
            POINTER(_openusb_bulk_request)
        ]

    lib.openusb_bulk_xfer.restype = c_int32

    # int32_t openusb_isoc_xfer(openusb_dev_handle_t dev,
    #                           uint8_t ifc,
    #                           uint8_t ept,
    #                           openusb_isoc_request_t *isoc);
    lib.openusb_isoc_xfer.argtypes = [
            _openusb_dev_handle,
            c_uint8,
            c_uint8,
            POINTER(_openusb_isoc_request)
        ]

    lib.openusb_isoc_xfer.restype = c_int32

def _check(retval):
    if retval.value != 0:
        from usb.core import USBError
        raise USBError(_lib.openusb_strerror(retval).value)
    return retval

class _Context(object):

    def __init__(self):
        self.handle = _openusb_handle()
        _check(_lib.openusb_init(0, byref(self.handle)))
    def __del__(self):
        _lib.openusb_fini(self.handle)

class _BusIterator(object):

    def __init__(self):
        self.buslist = POINTER(openusb_busid)()
        num_busids = c_uint32()
        _check(_lib.openusb_get_busid_list(_ctx.handle,
                                           byref(self.buslist),
                                           byref(num_busids)))
        self.num_busids = num_busids.value
    def __iter__(self):
        for i in range(self.num_busids):
            yield self.buslist[i]
    def __del__(self):
        _lib.openusb_free_busid_list(self.buslist)

class _DevIterator(object):

    def __init__(self, busid):
        self.devlist = POINTER(_openusb_devid)()
        num_devids = c_uint32()
        _check(_lib.openusb_get_devids_by_bus(_ctx.handle,
                                              busid,
                                              byref(self.devlist),
                                              byref(num_devids)))
        self.num_devids = num_devids.value
    def __iter__(self):
        for i in range(self.num_devids):
            yield self.devlist[i]
    def __del__(self):
        _lib.openusb_free_devid_list(self.devlist)

class _OpenUSB(usb.backend.IBackend):

    @methodtrace(_logger)
    def enumerate_devices(self):
        for bus in _BusIterator():
            for devid in _DevIterator(bus):
                yield devid

    @methodtrace(_logger)
    def get_device_descriptor(self, dev):
        desc = _usb_device_desc()
        _check(_lib.openusb_parse_device_desc(_ctx.handle,
                                              dev,
                                              None,
                                              0,
                                              byref(desc)))
        return desc

    @methodtrace(_logger)
    def get_configuration_descriptor(self, dev, config):
        desc = _usb_config_desc()
        _check(_lib.openusb_parse_config_desc(_ctx.handle,
                                              dev,
                                              None,
                                              0,
                                              config,
                                              byref(desc)))
        return desc

    @methodtrace(_logger)
    def get_interface_descriptor(self, dev, intf, alt, config):
        desc = _usb_interface_desc()
        _check(_lib.openusb_parse_interface_desc(_ctx.handle,
                                                 dev,
                                                 None,
                                                 0,
                                                 config,
                                                 intf,
                                                 alt,
                                                 byref(desc)))
        return desc

    @methodtrace(_logger)
    def get_endpoint_descriptor(self, dev, ep, intf, alt, config):
        desc = _usb_endpoint_desc()
        _check(_lib.openusb_parse_endpoint_desc(_ctx.handle,
                                                dev,
                                                None,
                                                0,
                                                config,
                                                intf,
                                                alt,
                                                ep,
                                                byref(desc)))
        return desc

    @methodtrace(_logger)
    def open_device(self, dev):
        handle = _openusb_dev_handle()
        _check(_lib.openusb_open_device(_ctx.handle, dev, 0, byref(handle)))
        return handle

    @methodtrace(_logger)
    def close_device(self, dev_handle):
        _lib.openusb_close_device(dev_handle)

    @methodtrace(_logger)
    def set_configuration(self, dev_handle, config_value):
        _check(_lib.openusb_set_configuration(dev_handle, config_value))

    @methodtrace(_logger)
    def get_configuration(self, dev_handle):
        config = c_uint8()
        _check(_lib.openusb_get_configuration(dev_handle, byref(config)))
        return config.value

    @methodtrace(_logger)
    def set_interface_altsetting(self, dev_handle, intf, altsetting):
        _check(_lib.set_altsetting(dev_handle, intf, altsetting))

    @methodtrace(_logger)
    def claim_interface(self, dev_handle, intf):
        _check(_lib.openusb_claim_interface(dev_handle, intf, 0))

    @methodtrace(_logger)
    def release_interface(self, dev_handle, intf):
        _lib.openusb_release_interface(dev_handle, intf)

    @methodtrace(_logger)
    def bulk_write(self, dev_handle, ep, intf, data, timeout):
        request = _openusb_bulk_request()
        memset(byref(request), 0, sizeof(request))
        request.payload, request.length = data.buffer_info()
        request.timeout = timeout
        _check(_lib.openusb_bulk_xfer(dev_handle, intf, ep, byref(request)))
        return request.transfered_bytes.value

    @methodtrace(_logger)
    def bulk_read(self, dev_handle, ep, intf, size, timeout):
        request = _openusb_bulk_request()
        buffer = array.array('B', '\x00' * size)
        memset(byref(request), 0, sizeof(request))
        request.payload, request.length = buffer.buffer_info()
        request.timeout = timeout
        _check(_lib.openusb_bulk_xfer(dev_handle, intf, ep, byref(request)))
        return buffer[:request.transfered_bytes.value]

    @methodtrace(_logger)
    def intr_write(self, dev_handle, ep, intf, data, timeout):
        request = _openusb_intr_request()
        memset(byref(request), 0, sizeof(request))
        payload, request.length = data.buffer_info()
        request.payload = cast(payload, POINTER(c_uint8))
        request.timeout = timeout
        _check(_lib.openusb_intr_xfer(dev_handle, intf, ep, byref(request)))
        return request.transfered_bytes.value

    @methodtrace(_logger)
    def intr_read(self, dev_handle, ep, intf, size, timeout):
        request = _openusb_intr_request()
        buffer = array.array('B', '\x00' * size)
        memset(byref(request), 0, sizeof(request))
        payload, request.length = buffer.buffer_info()
        request.payload = cast(payload, POINTER(c_uint8))
        request.timeout = timeout
        _check(_lib.openusb_intr_xfer(dev_handle, intf, ep, byref(request)))
        return buffer[:request.transfered_bytes.value]

# TODO: implement isochronous
#    @methodtrace(_logger)
#    def iso_write(self, dev_handle, ep, intf, data, timeout):
#       pass

#    @methodtrace(_logger)
#    def iso_read(self, dev_handle, ep, intf, size, timeout):
#        pass

    @methodtrace(_logger)
    def ctrl_transfer(self,
                      dev_handle,
                      bmRequestType,
                      bRequest,
                      wValue,
                      wIndex,
                      data_or_wLength,
                      timeout):
        request = _openusb_ctrl_request()
        request.setup.bmRequestType = bmRequestType
        request.setup.bRequest = bRequest
        request.setup.wValue
        request.setup.wIndex
        request.timeout = timeout

        direction = usb.util.ctrl_direction(bmRequestType)

        if direction == ENDPOINT_OUT:
            buffer = data_or_wLength
        else:
            buffer = array.array('B', '\x00' * data_or_wLength)

        payload, request.length = buffer.buffer_info()
        request.payload = cast(payload, POINTER(c_uint8))

        ret = _check(_lib.openusb_ctrl_xfer(dev_handle, 0, 0, byref(request)))

        if direction == ENDPOINT_OUT:
            ret
        else:
            buffer[:ret]

    @methodtrace(_logger)
    def reset_device(self, dev_handle):
        _check(_lib.openusb_reset(dev_handle))

def get_backend():
    try:
        global _lib, _ctx
        if _lib is None:
            _lib = _load_library()
            _setup_prototypes(_lib)
            _ctx = _Context()
        return _OpenUSB()
    except Exception:
        _logger.error('Error loading OpenUSB backend', exc_info=True)
        return None
