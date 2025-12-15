"""
Basic example
"""

# import all from high level API
import sys

from xenics.xeneth import *
from xenics.xeneth.errors import XenethAPIException


def save_as_bin(data, file_path):
    """
    Save data as binary file
    """
    with open(file_path, "wb") as f:
        f.write(data)

    # Result can viewed with ImageJ: File > Import > Raw > 16-bit unsigned, Little-endian byte order


def main(url):
    """
    Main program function
    """
    cam = XCamera()

    # open camera and start capturing
    try:
        cam.open(url)
        buffer = cam.create_buffer()
        print(f"{cam.name=}")
        print(f"{cam.handle=}")
        print(f"{cam.width=}")
        print(f"{cam.height=}")
        print(f"{cam.max_width=}")
        print(f"{cam.max_height=}")
        print(f"{cam.name=}")
        if cam.is_initialized:
            print("Start capturing")
            cam.start_capture()

            if cam.get_frame(buffer, flags=XGetFrameFlags.XGF_Blocking):
                print("Image Captured.")
                # Save the frame as binary
                save_as_bin(buffer.image_data, "image_with_overlay.bin")

        else:
            print("Initialization failed")

    except XenethAPIException as e:
        print(e.message)
    finally:
        # Cleanup
        if cam.is_capturing:
            try:
                print("Stop capturing")
                cam.stop_capture()

                print("Close Camera")
                cam.close()

            except XenethAPIException as e:
                print(e.message)


if __name__ == "__main__":

    url = "cam://0"
    if len(sys.argv) > 1:
        url = sys.argv[1]

    main(url)
