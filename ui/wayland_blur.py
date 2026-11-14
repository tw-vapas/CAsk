"""Optional KDE Wayland blur protocol transport using Qt's existing connection.

Protocols: ext-background-effect-v1 (preferred), KDE blur.xml v1 (fallback).
Only the native-resource lookup touches Qt private ABI. Resolve symbols from the
running PyQt Qt library directory; never load a second system Qt/KF library.
Missing symbols, libraries, platform, or protocol leave ordinary translucency.
All calls and callbacks execute on the GUI thread. Qt owns display I/O; this
transport dispatches only its own registry queue and never reads/disconnects it.
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QByteArray, QLibraryInfo, QTimer
from PyQt6.QtGui import QGuiApplication


class Interface(C.Structure):
    pass


class Message(C.Structure):
    _fields_ = [('name', C.c_char_p), ('signature', C.c_char_p),
                ('types', C.POINTER(C.POINTER(Interface)))]


Interface._fields_ = [('name', C.c_char_p), ('version', C.c_int),
                     ('method_count', C.c_int), ('methods', C.POINTER(Message)),
                     ('event_count', C.c_int), ('events', C.POINTER(Message))]


class Argument(C.Union):
    _fields_ = [('i', C.c_int32), ('u', C.c_uint32), ('s', C.c_char_p), ('o', C.c_void_p)]


GLOBAL = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint32, C.c_char_p, C.c_uint32)
CAPABILITIES = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint32)
REMOVE = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint32)


class WaylandBlur:
    """Own blur/registry proxies, never the Qt display or Qt wl_surface."""

    def __init__(self, parent):
        self.status = 'Unavailable'
        self._repaint = parent.update
        self._standard = False
        self._supports_blur = True
        self.display = self.queue = self.registry = self.manager = self.compositor = self.blur = None
        self.surface = None
        self._globals = {}
        self._desired = ()
        self._applied = None
        self._closed = False
        self.timer = QTimer(parent)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._poll)
        try:
            if QGuiApplication.platformName() != 'wayland':
                self.status = 'Unsupported platform'
                return
            self._load_native()
            self._load_protocol()
            self.display = self._resource(b'display')
            if not self.display:
                self.status = 'Qt Wayland display unavailable'
                return
            self.queue = self.wl.wl_display_create_queue(self.display)
            if not self.queue:
                raise RuntimeError('Wayland queue allocation failed')
            # A wrapper assigns only our new registry to this queue, leaving Qt alone.
            wrapper = self.wl.wl_proxy_create_wrapper(self.display)
            if not wrapper:
                raise RuntimeError('Wayland proxy wrapper allocation failed')
            self.wl.wl_proxy_set_queue(wrapper, self.queue)
            self.registry = self._request(wrapper, 1, self.registry_interface, [Argument(o=None)])
            self.wl.wl_proxy_wrapper_destroy(wrapper)
            self._global_callback = GLOBAL(self._global)
            self._remove_callback = REMOVE(self._remove)
            self._listener = (C.c_void_p * 2)(C.cast(self._global_callback, C.c_void_p), C.cast(self._remove_callback, C.c_void_p))
            if self.wl.wl_proxy_add_listener(self.registry, self._listener, None) != 0:
                raise RuntimeError('Wayland registry listener failed')
            self.status = 'Waiting for KDE blur protocol'
            self.timer.start()
            self.wl.wl_display_flush(self.display)
        except (OSError, AttributeError, RuntimeError) as exc:
            self.status = f'Unavailable: {exc}'
            self.close()

    def _function(self, library, name, result, arguments):
        function = getattr(library, name)
        function.restype = result
        function.argtypes = arguments
        return function

    def _load_native(self):
        directory = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibrariesPath))
        self.gui = C.CDLL(str(directory / 'libQt6Gui.so.6'))
        self.qt_wayland = C.CDLL(str(directory / 'libQt6WaylandClient.so.6'))
        native = self._function(self.gui, '_ZN15QGuiApplication23platformNativeInterfaceEv', C.c_void_p, [])
        self.native = native()
        if not self.native:
            raise RuntimeError('Qt native interface unavailable')
        self.integration_resource = self._function(
            self.qt_wayland, '_ZN15QtWaylandClient23QWaylandNativeInterface28nativeResourceForIntegrationERK10QByteArray',
            C.c_void_p, [C.c_void_p, C.c_void_p])
        self.window_resource = self._function(
            self.qt_wayland, '_ZN15QtWaylandClient23QWaylandNativeInterface23nativeResourceForWindowERK10QByteArrayP7QWindow',
            C.c_void_p, [C.c_void_p, C.c_void_p, C.c_void_p])

    def _resource(self, name, window=None):
        key = QByteArray(name)
        pointer = int(sip.unwrapinstance(key))
        if window is None:
            return self.integration_resource(self.native, pointer)
        return self.window_resource(self.native, pointer, int(sip.unwrapinstance(window)))

    def _load_protocol(self):
        self.wl = C.CDLL(ctypes.util.find_library('wayland-client') or 'libwayland-client.so.0')
        ptr = C.c_void_p
        for name, result, arguments in (
            ('wl_proxy_marshal_array_flags', ptr, [ptr, C.c_uint32, C.POINTER(Interface), C.c_uint32, C.c_uint32, C.POINTER(Argument)]),
            ('wl_proxy_create_wrapper', ptr, [ptr]),
            ('wl_proxy_wrapper_destroy', None, [ptr]),
            ('wl_proxy_set_queue', None, [ptr, ptr]),
            ('wl_proxy_add_listener', C.c_int, [ptr, C.POINTER(ptr), ptr]),
            ('wl_display_create_queue', ptr, [ptr]),
            ('wl_display_dispatch_queue_pending', C.c_int, [ptr, ptr]),
            ('wl_display_flush', C.c_int, [ptr]),
            ('wl_proxy_destroy', None, [ptr]),
            ('wl_event_queue_destroy', None, [ptr]),
        ):
            self._function(self.wl, name, result, arguments)
        self.registry_interface = Interface.in_dll(self.wl, 'wl_registry_interface')
        self.compositor_interface = Interface.in_dll(self.wl, 'wl_compositor_interface')
        self.region_interface = Interface.in_dll(self.wl, 'wl_region_interface')
        self.surface_interface = Interface.in_dll(self.wl, 'wl_surface_interface')
        self.blur_interface = Interface(b'org_kde_kwin_blur', 1, 0, None, 0, None)
        self.manager_interface = Interface(b'org_kde_kwin_blur_manager', 1, 0, None, 0, None)
        # Keep message/type storage alive as long as any proxy can reference it.
        self._create_types = (C.POINTER(Interface) * 2)(C.pointer(self.blur_interface), C.pointer(self.surface_interface))
        self._surface_types = (C.POINTER(Interface) * 1)(C.pointer(self.surface_interface))
        self._region_types = (C.POINTER(Interface) * 1)(C.pointer(self.region_interface))
        self._manager_methods = (Message * 2)(Message(b'create', b'no', self._create_types), Message(b'unset', b'o', self._surface_types))
        self._blur_methods = (Message * 3)(Message(b'commit', b'', None), Message(b'set_region', b'?o', self._region_types), Message(b'release', b'', None))
        self.manager_interface.method_count = 2
        self.manager_interface.methods = self._manager_methods
        self.blur_interface.method_count = 3
        self.blur_interface.methods = self._blur_methods
        self.effect_interface = Interface(b'ext_background_effect_surface_v1', 1, 0, None, 0, None)
        self.effect_manager_interface = Interface(b'ext_background_effect_manager_v1', 1, 0, None, 0, None)
        self._effect_types = (C.POINTER(Interface) * 2)(C.pointer(self.effect_interface), C.pointer(self.surface_interface))
        self._effect_manager_methods = (Message * 2)(Message(b'destroy', b'', None), Message(b'get_background_effect', b'no', self._effect_types))
        self._effect_methods = (Message * 2)(Message(b'destroy', b'', None), Message(b'set_blur_region', b'?o', self._region_types))
        self._effect_events = (Message * 1)(Message(b'capabilities', b'u', None))
        self.effect_manager_interface.method_count = 2
        self.effect_manager_interface.methods = self._effect_manager_methods
        self.effect_manager_interface.event_count = 1
        self.effect_manager_interface.events = self._effect_events
        self.effect_interface.method_count = 2
        self.effect_interface.methods = self._effect_methods
        self._capabilities_callback = CAPABILITIES(self._capabilities)
        self._effect_listener = (C.c_void_p * 1)(C.cast(self._capabilities_callback, C.c_void_p))

    def _request(self, proxy, opcode, interface=None, arguments=(), destroy=False):
        args = (Argument * len(arguments))(*arguments) if arguments else None
        return self.wl.wl_proxy_marshal_array_flags(proxy, opcode, C.byref(interface) if interface else None, 1, int(destroy), args)

    def _global(self, data, registry, name, interface, version):
        if interface == b'ext_background_effect_manager_v1' and not self._standard:
            if self.manager:
                self._release_blur()
                self.wl.wl_proxy_destroy(self.manager)
                self._globals = {key: value for key, value in self._globals.items() if value != 'manager'}
            self._standard = True
            self._supports_blur = False
            self.manager = self._bind(name, self.effect_manager_interface)
            self.wl.wl_proxy_add_listener(self.manager, self._effect_listener, None)
            self._globals[name] = 'manager'
            self._applied = None
        elif interface == b'org_kde_kwin_blur_manager' and not self.manager:
            self.manager = self._bind(name, self.manager_interface)
            self._globals[name] = 'manager'
            self._applied = None
        elif interface == b'wl_compositor' and not self.compositor:
            self.compositor = self._bind(name, self.compositor_interface)
            self._globals[name] = 'compositor'
        if self.manager and self.compositor and self._supports_blur:
            self.status = 'Native Wayland blur ready'

    def _capabilities(self, data, manager, flags):
        self._supports_blur = bool(flags & 1)
        self._applied = None
        self.status = 'Native Wayland blur ready' if self._supports_blur else 'Compositor blur disabled'
        if not self._supports_blur:
            self._release_blur()
            self._repaint()

    def _bind(self, name, interface):
        return self._request(self.registry, 0, interface,
                             [Argument(u=name), Argument(s=interface.name), Argument(u=1), Argument(o=None)])

    def _remove(self, data, registry, name):
        target = self._globals.pop(name, None)
        if target:
            self._release_blur()
            self.wl.wl_proxy_destroy(getattr(self, target))
            setattr(self, target, None)
            if target == 'manager':
                self._standard = False
            self._applied = None
            self.status = 'KDE Wayland blur unavailable'

    def _poll(self):
        if self._closed:
            return
        if self.wl.wl_display_dispatch_queue_pending(self.display, self.queue) < 0:
            self.status = 'Wayland connection unavailable'
            self.close()
            return
        self._apply()

    def update(self, window, rectangles):
        if self._closed or not self.display:
            return
        surface = self._resource(b'surface', window) if window else None
        if surface != self.surface:
            self._release_blur()
            self.surface = surface
            self._applied = None
        self._desired = tuple(rectangles)
        self._apply()

    def _apply(self):
        if not self.manager or not self.compositor or not self.surface or not self._supports_blur:
            return
        if self._applied == self._desired:
            return
        if not self._desired:
            # An empty blur region means the WHOLE surface in KDE. Always unset.
            self._release_blur()
            if not self._standard:
                self._request(self.manager, 1, arguments=[Argument(o=self.surface)])
        else:
            region = self._request(self.compositor, 1, self.region_interface, [Argument(o=None)])
            for x, y, width, height in self._desired:
                self._request(region, 1, arguments=[Argument(i=n) for n in (x, y, width, height)])
            if not self.blur:
                self.blur = self._request(self.manager, 1 if self._standard else 0, self.effect_interface if self._standard else self.blur_interface, [Argument(o=None), Argument(o=self.surface)])
            self._request(self.blur, 1, arguments=[Argument(o=region)])
            if not self._standard:
                self._request(self.blur, 0)
            self._request(region, 0, destroy=True)
        self._applied = self._desired
        self.wl.wl_display_flush(self.display)
        self._repaint()

    def _release_blur(self):
        if self.blur:
            self._request(self.blur, 0 if self._standard else 2, destroy=True)
            self.blur = None

    def detach(self):
        """Called before Qt destroys its surface, while the pointer is still valid."""
        self.update(None, ())

    def close(self):
        if self._closed:
            return
        self.timer.stop()
        self._release_blur()
        if self.display:
            for name in ('manager', 'compositor', 'registry'):
                proxy = getattr(self, name)
                if proxy:
                    if name == 'manager' and self._standard:
                        self._request(proxy, 0, destroy=True)
                    else:
                        self.wl.wl_proxy_destroy(proxy)
                    setattr(self, name, None)
            self.wl.wl_display_flush(self.display)
        if self.queue:
            self.wl.wl_event_queue_destroy(self.queue)
            self.queue = None
        self._closed = True
