import ctypes
import pathlib
import time
from typing import Optional
from helpers import DllBinder

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import os

from Instrument import Instrument

CWD = pathlib.Path(__file__).resolve().parent
os.add_dll_directory(CWD / "dll")
DLL_NAME = "xeneth64.dll"
CAL_PATH = (
    r"C:\Program Files\Xeneth\Calibrations\XC-(31-10-2017)-HG-ITR-500us_10331.xca"
)


class XenicsError(RuntimeError):
    """Exception raised for Xenics DLL errors."""

    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"[XENICSERROR {code}]: {message}")


class XenicsDLL:
    """Low-level ctypes wrapper for the Xenics camera DLL.

    This class is responsible for:
    - loading the DLL
    - defining function signatures
    - translating error codes into Python exceptions
    """

    def __init__(self, dll_name: str | pathlib.Path = DLL_NAME):
        self._dll_name = dll_name
        self._dll: Optional[ctypes.CDLL] = None
        self._load()

    # DLL loading and binding
    def _load(self) -> None:
        """Load the DLL and bind all functions."""
        print(self._dll_name)
        self._dll = ctypes.CDLL(self._dll_name, winmode=0)
        self._bind_functions()

    def _bind_functions(self) -> None:
        """Bind all required DLL functions."""

        binder = DllBinder(self._dll)

        # Camera lifecycle
        binder.bind(self, "XC_OpenCamera", ctypes.c_int32)
        binder.bind(self, "XC_CloseCamera", None, (ctypes.c_int32,))
        binder.bind(self, "XC_IsInitialised", ctypes.c_int32, (ctypes.c_int32,))

        # Error handling
        binder.bind(
            self,
            "XC_ErrorToString",
            ctypes.c_int32,
            (ctypes.c_int32, ctypes.c_char_p, ctypes.c_int32),
        )

        # Capture control
        binder.bind(self, "XC_StartCapture", ctypes.c_ulong, (ctypes.c_int32,))
        binder.bind(self, "XC_StopCapture", ctypes.c_ulong, (ctypes.c_int32,))
        binder.bind(self, "XC_IsCapturing", ctypes.c_bool, (ctypes.c_int32,))

        # Frame information
        binder.bind(self, "XC_GetFrameSize", ctypes.c_ulong, (ctypes.c_int32,))
        binder.bind(self, "XC_GetFrameType", ctypes.c_ulong, (ctypes.c_int32,))
        binder.bind(self, "XC_GetWidth", ctypes.c_ulong, (ctypes.c_int32,))
        binder.bind(self, "XC_GetHeight", ctypes.c_ulong, (ctypes.c_int32,))
        binder.bind(self, "XC_GetMaxValue", ctypes.c_ulong, (ctypes.c_int32,))

        # Frame capture
        binder.bind(
            self,
            "XC_GetFrame",
            ctypes.c_ulong,
            (
                ctypes.c_int32,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_void_p,
                ctypes.c_uint,
            ),
        )

        # Data and devices
        binder.bind(
            self,
            "XC_SaveData",
            ctypes.c_ulong,
            (ctypes.c_int32, ctypes.c_char_p, ctypes.c_ulong),
        )
        binder.bind(
            self,
            "XCD_EnumerateDevices",
            ctypes.c_ulong,
            (ctypes.c_int32, ctypes.c_uint, ctypes.c_ulong),
        )

        # Calibration and settings
        binder.bind(self, "XC_LoadCalibration", ctypes.c_ulong)
        binder.bind(self, "XC_LoadSettings", ctypes.c_ulong)
        binder.bind(self, "XC_LoadColourProfile", ctypes.c_ulong, (ctypes.c_char_p,))

        # Property access
        binder.bind(self, "XC_SetPropertyValue", ctypes.c_ulong)
        binder.bind(
            self,
            "XC_GetPropertyValueL",
            ctypes.c_ulong,
            (ctypes.c_int32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong)),
        )

    # Error handling utilities
    def _error_to_string(self, code: int) -> str:
        """Convert a DLL error code to a human-readable string."""
        buffer = ctypes.create_string_buffer(256)
        self._dll.XC_ErrorToString(code, buffer, len(buffer))
        return buffer.value.decode("utf-8", errors="replace")

    def _check_error(self, code: int) -> None:
        """Raise a XenicsError if error code is non-zero."""
        if code != 0:
            raise XenicsError(code, self._error_to_string(code))

    # Safe wrappers (public API of the DLL wrapper)
    def open_camera(self, url) -> int:
        handle = self._dll.XC_OpenCamera(url, 0, 0)
        if handle < 0:
            raise XenicsError(handle, "Failed to open camera")
        return handle

    def get_frame(
        self,
        handle: int,
        frame_number: int,
        buffer_size: int,
        buffer_ptr: ctypes.c_void_p,
        timeout_ms: int,
    ) -> None:
        self._check_error(
            self._dll.XC_GetFrame(
                handle,
                frame_number,
                buffer_size,
                buffer_ptr,
                timeout_ms,
            )
        )

    # def load_calibration(self) -> None:
    #     self._check_error(self._dll.XC_LoadCalibration())

    # def load_settings(self) -> None:
    #     self._check_error(self._dll.XC_LoadSettings())


class Xenics(Instrument):

    def __init__(
        self,
        url: str = "cam://0",
        dll: XenicsDLL = XenicsDLL(),
        calibration_file: str | None = None,
        settings_file: str | None = None,
    ):
        super().__init__()

        self._cam: int | None = None
        self._url: str = url

        # Status
        self._is_open = False
        self._is_capturing = False

        # Load the SDK
        self._dll: XenicsDLL = dll
        self._calibration_file: str | None = calibration_file
        self._settings_file: str | None = settings_file

    @property
    def url(self) -> str:
        """Camera URL.

        Returns
        -------
        str
            Camera URL path.
        """
        return self._url

    @property
    def cam(self) -> int:
        """Xenics Cam.

        Returns
        -------
        int
            Xenics device key-identifier for the connected cam.
        """
        return self._cam

    @property
    def calibration_file(self) -> str:
        """Calibration file path.

        Returns
        -------
        str
            Path to the calibration file.
        """
        return self._calibration_file

    @calibration_file.setter
    def calibration_file(self, filepath: str | None) -> None:
        """Set calibration file path.

        Parameters
        ----------
        filepath : str
            Path to the calibration file.
        """
        if filepath is None:
            return
        self._calibration_file = filepath
        self.load_calibration(filepath)

    @property
    def settings_file(self) -> str:
        """Settings file path.

        Returns
        -------
        str
            Path to the settings file.
        """
        return self._settings_file

    @settings_file.setter
    def settings_file(self, filepath: str | None) -> None:
        """Set settings file path.

        Parameters
        ----------
        filepath : str
            Path to the settings file.
        """
        if filepath is None:
            return
        self._settings_file = filepath
        self.load_settings(filepath)

    @property
    def frame_size(self) -> int:
        """Return the frame size in bytes.

        Returns
        -------
        int
            Frame size in bytes.
        """
        self._require_open()
        return int(self._dll.XC_GetFrameSize(self._cam))

    @property
    def frame_dims(self) -> tuple[int, int]:
        """Return frame dimensions.

        Returns
        -------
        tuple of int
            Frame dimensions as (height, width).
        """
        self._require_open()

        width = int(self._dll.XC_GetWidth(self._cam))
        height = int(self._dll.XC_GetHeight(self._cam))

        return height, width

    @property
    def width(self) -> int:
        """Return frame width.

        Returns
        -------
        int
            Frame width.
        """
        self._require_open()
        return int(self._dll.XC_GetWidth(self._cam))

    @property
    def height(self) -> int:
        """Return frame height.

        Returns
        -------
        int
            Frame height.
        """
        self._require_open()
        return int(self._dll.XC_GetHeight(self._cam))

    @property
    def frame_type(self) -> int:
        """Return the camera frame type enumeration.

        Returns
        -------
        int
            Frame type enumeration.
        """
        self._require_open()
        return int(self._dll.XC_GetFrameType(self._cam))

    @property
    def pixel_size(self) -> int:
        """Return the pixel size in bytes.

        Returns
        -------
        int
            Number of bytes per pixel.

        Raises
        ------
        XenicsError
            If the frame type is unsupported.
        """
        frame_type = self.frame_type

        pixel_sizes = {
            -1: 0,  # UNKNOWN
            0: 0,  # NATIVE
            1: 1,  # 8 BPP GRAY
            2: 2,  # 16 BPP GRAY
            3: 4,  # 32 BPP GRAY
            4: 4,  # RGBA
            5: 4,  # RGB
            6: 4,  # BGRA
            7: 4,  # BGR
        }

        try:
            return pixel_sizes[frame_type]
        except KeyError:
            raise XenicsError(
                code=frame_type,
                message=f"Unsupported frame type {frame_type}",
            )

    def _require_open(self) -> None:
        """Check that camera is open."""
        if not self._is_open or self._cam is None:
            raise RuntimeError("Camera is not open.")

    def _require_capturing(self) -> None:
        """Check that camera is capturing."""
        if not self._is_capturing or self._cam is None:
            raise RuntimeError("Camera is not capturing.")

    def connect(self) -> None:
        """
        Initializes the instrument
        :return:
        """
        self.open()
        self.load_calibration()
        self.load_settings()
        self.start_capture()

    def open(self) -> None:
        """Open the camera connection."""
        if self._is_open:
            return

        handle = self._dll.XC_OpenCamera(self._url.encode("utf-8"), 0, 0)
        if handle == 0:
            raise Exception("Xenics handle is NULL.")

        if not self._dll.XC_IsInitialised(handle):
            raise XenicsError(
                code=-1, message="Camera initialization failed after opening."
            )

        self._cam = handle
        self._is_open = True

    def close(self) -> None:
        """Stop capture (if running) and close the camera."""
        if not self._is_open:
            return

        try:
            if self._is_capturing:
                self.stop_capture()
                self._is_capturing = False

        except BaseException:
            print("Something went wrong closing the camera.")
            raise

        finally:
            self._dll.XC_CloseCamera(self._cam)
            self._cam = None
            self._is_open = False

    def start_capture(self) -> None:
        """Start frame acquisition."""
        self._require_open()

        if self._is_capturing:
            return

        self._dll._check_error(self._dll.XC_StartCapture(self._cam))
        self._is_capturing = True

    def stop_capture(self) -> None:
        """Stop frame acquisition."""
        self._require_open()

        if not self._is_capturing:
            return

        self._dll._check_error(self._dll.XC_StopCapture(self._cam))
        self._is_capturing = False

    def load_calibration(self, filename: str | None = None) -> None:
        fname = filename if filename is not None else self._calibration_file
        if fname is None:
            # LOG no calibration loaded.
            return
        else:
            flag = 1  # Use software correction
            self._dll._check_error(
                self._dll.XC_LoadCalibration(self._cam, str(fname).encode(), flag)
            )

    def load_settings(self, filename: str | None = None) -> None:
        fname = filename if filename is not None else self.settings_file
        if fname is None:
            # LOG no setting loaded.
            return
        else:
            self._dll._check_error(
                self._dll.XC_LoadSettings(self._cam, fname.encode())
            )

    def grab_frame(self, filename: str):
        """Acquire a single frame and save it to disk.

        Parameters
        ----------
        filename : str
            Output image filename.

        Returns
        -------
        numpy.ndarray
            Acquired frame as a NumPy array.

        Raises
        ------
        XenicsError
            If acquisition fails.
        """

        self._require_capturing()

        frame_size = self.frame_size
        frame_t = self.frame_type
        height, width = self.frame_dims
        pixel_dtype = self.get_pixel_dtype()
        pixel_size = self.pixel_size

        buffer = bytes(frame_size)

        self._dll.get_frame(self._cam, frame_t, 1, buffer, frame_size)

        frame = np.frombuffer(
            buffer,
            dtype=pixel_dtype,
            count=frame_size // pixel_size,
        ).reshape((height, width))

        Image.fromarray(frame).save(filename)
        return frame

    def get_pixel_dtype(self):
        bytes_in_pixel = self.pixel_size
        conversions = (None, np.uint8, np.uint16, None, np.uint32)
        try:
            pixel_dtype = conversions[bytes_in_pixel]
        except BaseException:
            raise Exception("Unsupported pixel size %s" % str(bytes_in_pixel))
        if conversions is None:
            raise Exception("Unsupported pixel size %s" % str(bytes_in_pixel))
        return pixel_dtype


if __name__ == "__main__":

    camera = Xenics(url="gev://192.168.1.11", calibration_file=CAL_PATH)
    # TODO: metti profilo NATIVE in BW
    # TODO: fix dll path and cal files

    print(camera.url)
    camera.connect()
    time.sleep(1)
    im = camera.grab_frame("trial_w_settings.tiff")
    plt.imshow(im)
    plt.show()
    camera.close()
