# -*- coding: utf-8 -*-

import io
import time
import pygame
try:
    import gphoto2 as gp
except ImportError:
    gp = None  # gphoto2 is optional
from PIL import Image, ImageFilter
from pibooth.pictures import sizing
from pibooth.utils import LOGGER, PoolingTimer, pkill
from pibooth.language import get_translated_text
from pibooth.camera.base import BaseCamera

# import subprocess as sp
# import serial


def get_gp_camera_proxy(port=None):
    """Return camera proxy if a gPhoto2 compatible camera is found
    else return None.

    .. note:: try to kill any process using gPhoto2 as it may block camera access.

    :param port: look on given port number
    :type port: str
    """
    if not gp:
        return None  # gPhoto2 is not installed

    pkill('*gphoto2*')
    if hasattr(gp, 'gp_camera_autodetect'):
        # gPhoto2 version 2.5+
        cameras = gp.check_result(gp.gp_camera_autodetect())
    else:
        port_info_list = gp.PortInfoList()
        port_info_list.load()
        abilities_list = gp.CameraAbilitiesList()
        abilities_list.load()
        cameras = abilities_list.detect(port_info_list)
    if cameras:
        LOGGER.debug("Found gPhoto2 cameras on ports: '%s'", "' / '".join([p for _, p in cameras]))
        # Initialize first camera proxy and return it
        camera = gp.Camera()
        if port is not None:
            port_info_list = gp.PortInfoList()
            port_info_list.load()
            idx = port_info_list.lookup_path(port)
            camera.set_port_info(port_info_list[idx])

        try:
            camera.init()
            return camera
        except gp.GPhoto2Error as ex:
            LOGGER.warning("Could not connect gPhoto2 camera: %s", ex)

    return None


def gp_log_callback(level, domain, string, data=None):
    """Logging callback for gphoto2.
    """
    LOGGER.getChild('gphoto2').debug(domain.decode("utf-8") + u': ' + string.decode("utf-8"))


class GpCamera(BaseCamera):

    """gPhoto2 camera management.
    """

    IMAGE_EFFECTS = [u'none',
                     u'blur',
                     u'contour',
                     u'detail',
                     u'edge_enhance',
                     u'edge_enhance_more',
                     u'emboss',
                     u'find_edges',
                     u'smooth',
                     u'smooth_more',
                     u'sharpen']

    def __init__(self, camera_proxy):
        super(GpCamera, self).__init__(camera_proxy)
        self._gp_logcb = None
        self._preview_compatible = True
        self._preview_viewfinder = False

        # req = sp.run("ls /dev | grep USB", shell=True, capture_output=True)
        #
        # if req.returncode == 0:
        #     port = req.stdout.decode().strip()
        #     port = "/dev/" + port
        #     self.com = serial.Serial(port, timeout=1)
        #
        #     LOGGER.info(f"Communication Port for Serial is: {port}")


    def _specific_initialization(self):
        """Camera initialization.
        """
        self._gp_logcb = gp.check_result(gp.gp_log_add_func(gp.GP_LOG_VERBOSE, gp_log_callback))
        abilities = self._cam.get_abilities()
        self._preview_compatible = gp.GP_OPERATION_CAPTURE_PREVIEW ==\
            abilities.operations & gp.GP_OPERATION_CAPTURE_PREVIEW
        if not self._preview_compatible:
            LOGGER.warning("The connected DSLR camera is not compatible with preview")
        else:
            try:
                self.get_config_value('actions', 'viewfinder')
                self._preview_viewfinder = True
            except ValueError:
                self._preview_viewfinder = False

        self.set_config_value('imgsettings', 'iso', self.preview_iso)
        self.set_config_value('settings', 'capturetarget', 'Memory card')
        self.set_config_value('imgsettings', 'imageformat', self.imageformat)
        self.set_config_value('imgsettings', 'imageformatsd', self.imageformat)

    def _show_overlay(self, text, alpha):
        """Add an image as an overlay.
        """
        if self._window:  # No window means no preview displayed
            # modification TK to add countdown over image not as overlay
            # rect = self.get_countdown_rect()
            # rect = self.get_rect()
            # self._overlay = self.build_countdown_top((rect.width, rect.height), str(text), alpha)
            # self._overlay = self.build_overlay((rect.width, rect.height), str(text), alpha)

            ct_rect = self.get_countdown_rect()
            ct_pil_image = self.build_countdown_top((ct_rect.width, ct_rect.height), str(text))
            LOGGER.debug("created countdown image to display")
            #ct_pil_image.save("countdown_img"+text+".png")
            updated = self._window.show_image(ct_pil_image, pos='top')

            pygame.event.pump()
            if updated:
                pygame.display.update(updated)

    def _rotate_image(self, image, rotation):
        """Rotate a PIL image, same direction than RpiCamera.
        """
        if rotation == 90:
            return image.transpose(Image.ROTATE_90)
        elif rotation == 180:
            return image.transpose(Image.ROTATE_180)
        elif rotation == 270:
            return image.transpose(Image.ROTATE_270)
        return image

    def _get_preview_image(self):
        """Capture a new preview image.
        """
        rect = self.get_rect()
        if self._preview_compatible:
            cam_file = self._cam.capture_preview()
            image = Image.open(io.BytesIO(cam_file.get_data_and_size()))
            image = self._rotate_image(image, self.preview_rotation)
            # Crop to keep aspect ratio of the resolution
            image = image.crop(sizing.new_size_by_croping_ratio(image.size, self.resolution))
            # Resize to fit the available space in the window
            image = image.resize(sizing.new_size_keep_aspect_ratio(image.size, (rect.width, rect.height), 'outer'))

            if self.preview_flip:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            image = Image.new('RGB', (rect.width, rect.height), color=(0, 0, 0))

        if self._overlay:
            image.paste(self._overlay, (0, 0), self._overlay)
        return image

    def _post_process_capture(self, capture_data):
        """Rework capture data.

        :param capture_data: couple (GPhotoPath, effect)
        :type capture_data: tuple
        """
        gp_path, effect = capture_data
        camera_file = self._cam.file_get(gp_path.folder, gp_path.name, gp.GP_FILE_TYPE_NORMAL)
        if self.delete_internal_memory:
            LOGGER.debug("Delete capture '%s' from internal memory", gp_path.name)
            self._cam.file_delete(gp_path.folder, gp_path.name)
        image = Image.open(io.BytesIO(camera_file.get_data_and_size()))
        image = self._rotate_image(image, self.capture_rotation)

        # Crop to keep aspect ratio of the resolution
        image = image.crop(sizing.new_size_by_croping_ratio(image.size, self.resolution))
        # Resize to fit the resolution
        image = image.resize(sizing.new_size_keep_aspect_ratio(image.size, self.resolution, 'outer'))

        if self.capture_flip:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)

        if effect != 'none':
            image = image.filter(getattr(ImageFilter, effect.upper()))

        return image

    def set_config_value(self, section, option, value):
        """Set camera configuration.
        """
        try:
            LOGGER.debug('Setting option %s/%s=%s', section, option, value)
            config = self._cam.get_config()
            child = config.get_child_by_name(section).get_child_by_name(option)
            if child.get_type() == gp.GP_WIDGET_RADIO:
                choices = [c for c in child.get_choices()]
            else:
                choices = None
            data_type = type(child.get_value())
            value = data_type(value)  # Cast value
            if choices and value not in choices:
                if value == 'Memory card' and 'card' in choices:
                    value = 'card'  # Fix for Sony ZV-1
                elif value == 'Memory card' and 'card+sdram' in choices:
                    value = 'card+sdram'  # Fix for Sony ILCE-6400
                else:
                    LOGGER.warning("Invalid value '%s' for option %s (possible choices: %s), trying to set it anyway",
                                   value, option, choices)
            child.set_value(value)
            self._cam.set_config(config)
        except gp.GPhoto2Error as ex:
            LOGGER.error('Unsupported option %s/%s=%s (%s), configure your DSLR manually', section, option, value, ex)

    def get_config_value(self, section, option):
        """Get camera configuration option.
        """
        try:
            config = self._cam.get_config()
            child = config.get_child_by_name(section).get_child_by_name(option)
            value = child.get_value()
            LOGGER.debug('Getting option %s/%s=%s', section, option, value)
            return value
        except gp.GPhoto2Error:
            raise ValueError('Unknown option {}/{}'.format(section, option))

    def preview(self, window, flip=True):
        """Setup the preview.
        """
        self._window = window
        self.preview_flip = flip

        if self._preview_compatible:
            if self._preview_viewfinder:
                self.set_config_value('actions', 'viewfinder', 1)
            self._window.show_image(self._get_preview_image())

    def preview_countdown(self, timeout, alpha=80):
        """Show a countdown of `timeout` seconds on the preview.
        Returns when the countdown is finished.
        """
        timeout = int(timeout)
        if timeout < 1:
            raise ValueError("Start time shall be greater than 0")

        # this action is performed on canon dslr to focus during the countdown
        # self.set_config_value('actions', 'autofocusdrive', '1')


        # self.set_config_value('capturesettings', 'focusmode', '1') # set focusmode to AI Focus / AIServo = 2
        # self.set_config_value('actions', 'manualfocusdrive', '6') # set focus to far 3

        # Manual Focus Drive Options
        # Choice: 0 Nah 1
        # Choice: 1 Nah 2
        # Choice: 2 Nah 3
        # Choice: 3 Keine
        # Choice: 4 Weit 1
        # Choice: 5 Weit 2
        # Choice: 6 Weit 3

        # this would be the point to make the focus by hardware

        # Halfpress Camera Button by Hardware
        # self.com.write(b'CAMFOC\n')
        # LOGGER.info("Focus Camera")

        shown = False
        first_loop = True
        timer = PoolingTimer(timeout)
        while not timer.is_timeout():
            remaining = int(timer.remaining() + 1)
            if not self._overlay or remaining != timeout:
                # Rebluid overlay only if remaining number has changed
                self._show_overlay(str(remaining), alpha)
                timeout = remaining
                shown = False

            updated_rect = None
            if self._preview_compatible:
                updated_rect = self._window.show_image(self._get_preview_image())
            elif not shown:
                updated_rect = self._window.show_image(self._get_preview_image())
                shown = True  # Do not update dummy preview until next overlay update

            if first_loop:
                timer.start()  # Because first preview capture is longer than others
                first_loop = False

            pygame.event.pump()
            if updated_rect:
                pygame.display.update(updated_rect)

        # self.set_config_value('actions', 'cancelautofocus', '1')

        self._show_overlay(get_translated_text('smile'), alpha)
        self._window.show_image(self._get_preview_image())

    def preview_wait(self, timeout, alpha=80):
        """Wait the given time.
        """
        timeout = int(timeout)
        if timeout < 1:
            raise ValueError("Start time shall be greater than 0")

        timer = PoolingTimer(timeout)
        if self._preview_compatible:
            while not timer.is_timeout():
                updated_rect = self._window.show_image(self._get_preview_image())
                pygame.event.pump()
                if updated_rect:
                    pygame.display.update(updated_rect)
        else:
            time.sleep(timer.remaining())

        self._show_overlay(get_translated_text('smile'), alpha)
        self._window.show_image(self._get_preview_image())

    def stop_preview(self):
        """Stop the preview.
        """
        self._hide_overlay()
        self._window = None

    def capture(self, effect=None):
        """Capture a new picture.
        """
        if self._preview_viewfinder:
            self.set_config_value('actions', 'viewfinder', 0)

        effect = str(effect).lower()
        if effect not in self.IMAGE_EFFECTS:
            raise ValueError("Invalid capture effect '{}' (choose among {})".format(effect, self.IMAGE_EFFECTS))

        if self.capture_iso != self.preview_iso:
            self.set_config_value('imgsettings', 'iso', self.capture_iso)

        # Fullpress Camera Button by Hardware
        # self.com.write(b'CAMSHO\n')
        # LOGGER.info("Take Picture")

        # one option here for a better timing would be to
        # use /main/actions/eosremoterelease
        # Label: Canon EOS Remote Release
        # Readonly: 0
        # Type: RADIO
        # Current: None
        # Choice: 0 None
        # Choice: 1 Press Half
        # Choice: 2 Press Full
        # Choice: 3 Release Half
        # Choice: 4 Release Full
        # Choice: 5 Immediate
        # Choice: 6 Press 1
        # Choice: 7 Press 2
        # Choice: 8 Press 3
        # Choice: 9 Release 1
        # Choice: 10 Release 2
        # Choice: 11 Release 3
        # END
        # problem is, that when focus is not correct and we use for example 5
        # the picture might be taken but unsharp
        # with gp.GP_CAPTURE_IMAGE the Camera first focuses and then shoots
        # but this leads to delays in some places

        self._captures.append((self._cam.capture(gp.GP_CAPTURE_IMAGE), effect))
        # self._captures.append((self._cam.file_get))
        time.sleep(0.3)  # Necessary to let the time for the camera to save the image

        if self.capture_iso != self.preview_iso:
            self.set_config_value('imgsettings', 'iso', self.preview_iso)

        self._hide_overlay()  # If stop_preview() has not been called

    def quit(self):
        """Close the camera driver, it's definitive.
        """
        if self._cam:
            del self._gp_logcb  # Uninstall log callback
            self._cam.exit()
