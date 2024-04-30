# -*- coding: utf-8 -*-

import pygame
from PIL import Image, ImageDraw

from pibooth import fonts
from pibooth.pictures import sizing
from pibooth.utils import LOGGER, PoolingTimer, pkill


class BaseCamera(object):

    def __init__(self, camera_proxy):
        self._cam = camera_proxy
        self._border = 50
        self._window = None
        self._overlay = None
        self._captures = []

        self.resolution = None
        self.delete_internal_memory = False
        self.preview_rotation, self.capture_rotation = (0, 0)
        self.preview_iso, self.capture_iso = (100, 800)
        self.imageformat = 'Large Normal JPEG'
        self.preview_flip, self.capture_flip = (False, False)

    def initialize(self, iso, resolution, rotation=0, flip=False, delete_internal_memory=False, imageformat=None):
        """Initialize the camera.
        """
        if not isinstance(rotation, (tuple, list)):
            rotation = (rotation, rotation)
        self.preview_rotation, self.capture_rotation = rotation
        for name in ('preview', 'capture'):
            rotation = getattr(self, '{}_rotation'.format(name))
            if rotation not in (0, 90, 180, 270):
                raise ValueError(
                    "Invalid {} camera rotation value '{}' (should be 0, 90, 180 or 270)".format(name, rotation))
        self.resolution = resolution
        self.capture_flip = flip
        if not isinstance(iso, (tuple, list)):
            iso = (iso, iso)
        self.preview_iso, self.capture_iso = iso
        if imageformat:
            self.imageformat = imageformat
        self.delete_internal_memory = delete_internal_memory
        self._specific_initialization()

    def _specific_initialization(self):
        """Specific camera initialization.
        """
        pass

    def _show_overlay(self, text, alpha):
        """Add an image as an overlay.
        """
        self._overlay = text

    def _hide_overlay(self):
        """Remove any existing overlay.
        """
        if self._overlay is not None:
            self._overlay = None

    def collect_captures(self):
        # collect filenames from cam

        raise NotImplementedError

    def _post_process_capture(self, capture_data):
        """Rework and return a PIL Image object from capture data.
        """
        raise NotImplementedError

    def get_rect(self, max_size=None):
        """Return a Rect object (as defined in pygame) for resizing preview and images
        in order to fit to the defined window.
        """
        rect = self._window.get_rect(absolute=True)

        size = (rect.width - 2 * self._border, rect.height - 2 * self._border)
        if max_size:
            size = (min(size[0], max_size[0]), min(size[1], max_size[1]))
        res = sizing.new_size_keep_aspect_ratio(self.resolution, size)
        return pygame.Rect(rect.centerx - res[0] // 2, rect.centery - res[1] // 2, res[0], res[1])

    def get_countdown_rect(self):
        """Return a Rect object (as defined in pygame) for positioning the countdawn text
         to fit the defined window
        """
        rect = self._window.get_rect(absolute=True)

        size = (rect.width - 2 * self._border, rect.height // 4)
        # here for portrait mode
        return pygame.Rect(rect.centerx - size[0] // 2, (rect.centery - size[1] // 2) , size[0], size[1])

    def build_countdown_top(self, size, text):
        """Return a PIL image with the given text that can be used
        as an countdown above image
        """
        image = Image.new('RGB', size, (255,255,255))
        draw = ImageDraw.Draw(image)

        font = fonts.get_pil_font(text, fonts.CURRENT, 0.9 * size[0], 0.9 * size[1])
        txt_width, txt_height = draw.textsize(text, font=font)

        position = ((size[0] - txt_width) // 2, (size[1] - txt_height) // 2)
        # position = ((size[0] - txt_width) // 2,  -(size[1] - txt_height) * 3)
        draw.text(position, text, (0, 0, 0), font=font)
        return image


    def build_overlay(self, size, text, alpha):
        """Return a PIL image with the given text that can be used
        as an overlay for the camera.
        """
        image = Image.new('RGBA', size)
        draw = ImageDraw.Draw(image)

        font = fonts.get_pil_font(text, fonts.CURRENT, 0.9 * size[0], 0.9 * size[1])
        txt_width, txt_height = draw.textsize(text, font=font)

        position = ((size[0] - txt_width) // 2, (size[1] - txt_height) // 2 - size[1] // 10)
        draw.text(position, text, (255, 0, 0, alpha), font=font)
        return image

    def preview(self, window, flip=True):
        """Setup the preview.
        """
        raise NotImplementedError

    def preview_countdown(self, timeout, alpha=60):
        """Show a countdown of `timeout` seconds on the preview.
        Returns when the countdown is finished.
        """
        raise NotImplementedError

    def preview_wait(self, timeout, alpha=60):
        """Wait the given time and let doing the job.
        Returns when the timeout is reached.
        """
        raise NotImplementedError

    def stop_preview(self):
        """Stop the preview.
        """
        raise NotImplementedError

    def capture(self, effect=None):
        """Capture a new picture.
        """
        raise NotImplementedError

    def get_captures(self):
        """Return all buffered captures as PIL images (buffer dropped after call).
        """
        self.collect_captures()

        images = []
        for data in self._captures:
            LOGGER.debug("In base get_captures")
            LOGGER.debug(data[0].name)

            images.append(self._post_process_capture(data))
        self.drop_captures()
        return images

    def drop_captures(self):
        """Delete all buffered captures.
        """
        self._captures.clear()

    def quit(self):
        """Close the camera driver, it's definitive.
        """
        raise NotImplementedError
