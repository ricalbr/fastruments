"""
Pixel conversion and ColourMode example.
"""

# import all from high level API
import os
import sys

from PIL import Image
from xenics.xeneth.capi.enums import ColourMode, XFrameType, XGetFrameFlags
from xenics.xeneth.errors import XenethAPIException
from xenics.xeneth.xcamera import XCamera


def main(url):
    """
    Main Program function
    """

    cam = XCamera()

    print(f"Opening connection to {url}")
    cam.open(url)

    if cam.is_initialized:
        print("Start capturing.")
        cam.start_capture()

        if cam.is_capturing:

            print("Grabbing a frame - FT_NATIVE.")
            buffer = cam.create_buffer(XFrameType.FT_NATIVE)

            try:
                # XGF_Blocking → ritorna solo quando un frame è pronto
                if cam.get_frame(buffer, flags=XGetFrameFlags.XGF_Blocking):
                    img = Image.fromarray(buffer.image_data)
                    img.save("img1.png")
                    print("Frame acquired and saved.")
                else:
                    print("No frame received.")

            except XenethAPIException as e:
                print(e.message)

        print("Stop capturing.")
        cam.stop_capture()

    print("Closing connection to camera.")
    cam.close()


if __name__ == "__main__":

    url = "cam://0"
    if len(sys.argv) > 1:
        url = sys.argv[1]

    main(url)


# # import all from high level API
# import sys
# from xenics.xeneth import *
# from xenics.xeneth.errors import XenethAPIException

# def save_as_bin(data, file_path):
#     """
#     Save data as binary file
#     """
#     with open(file_path, 'wb') as f:
#         f.write(data)

#     # Result can viewed with ImageJ: File > Import > Raw > 16-bit unsigned, Little-endian byte order

# def main(url):
#     """
#     Main program function
#     """
#     cam = XCamera()

#     # open camera and start capturing
#     try:
#         cam.open(url)
#         buffer = cam.create_buffer()
#         if cam.is_initialized:
#             print("Start capturing")
#             cam.start_capture()

#             if cam.get_frame(buffer, flags=XGetFrameFlags.XGF_Blocking):
#                 print("Image Captured.")
#                 # Save the frame as binary
#                 save_as_bin(buffer.image_data, "image_with_overlay.bin")

#         else:
#             print("Initialization failed")

#     except XenethAPIException as e:
#         print(e.message)
#     finally:
#         # Cleanup
#         if cam.is_capturing:
#             try:
#                 print("Stop capturing")
#                 cam.stop_capture()

#                 print("Close Camera")
#                 cam.close()

#             except XenethAPIException as e:
#                 print(e.message)


# if __name__ == '__main__':

#     url = "gev://192.168.1.11"
#     if len(sys.argv) > 1:
#         url = sys.argv[1]

#     main(url)
