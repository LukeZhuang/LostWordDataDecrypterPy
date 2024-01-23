#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
"""

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import msgpack
import json
import wget
import sys
import os

SECRECT_KEY = (
    "jR3GTK6vR6gPz2MNA7hPiGEYbG6vBsMAS5jaretmHu4PS78zz3YcijFBM9yJha5HL7wn3DFYd4XaFNLB"
)
KEY_LENGTH = 16
IV_LENGTH = 16


def get_download_url_prefix(ver: str) -> str:
    return f"http://thcdn.gggamedownload.com/source/Master_v{ver}/".format(ver=ver)


# some magic shuffle method, concat the last X bytes and the remaining,
# in which X is 1<<k and k is from 1 to 26
def shuffle_src(src: bytes, enc_key: int) -> bytes:
    assert enc_key >= 1 and enc_key <= 26
    if encKey == -1:
        return src
    shuffle_len = (1 << encKey) % len(src)
    return src[-shuffle_len:] + src[:-shuffle_len]


def get_encryption_key_bytes(table_name: str) -> bytes:
    index = len(table_name)
    key_arr = bytearray(KEY_LENGTH)
    for idx in range(KEY_LENGTH):
        name_byte = table_name[idx % len(table_name)]
        key_byte = SECRECT_KEY[index % len(SECRECT_KEY)]
        key_arr[idx] = name_byte ^ key_byte
        index += name_byte
    return key_arr


def decrypt(src: bytes, table_name: str) -> bytes:
    if table_name == "GachaTable":
        enc_key = 9
    elif table_name == "UnitTable":
        enc_key = 15
    elif table_name == "PriceTable":
        enc_key = 12
    else:
        enc_key = -1
    src = shuffle_src(src, enc_key)
    key_bytes = get_encryption_key_bytes(table_name)
    iv_bytes = src[:IV_LENGTH]
    decrypted_bytes = Decrypt(src[IV_LENGTH:], key_bytes, iv_bytes)
    return decrypted_bytes


def unpack(decrypted_bytes: bytes) -> json:
    unpacked_bytes = msgpack.unpackb(
        decrypted_bytes, use_list=False, raw=False, strict_map_key=False
    )
    json_data = json.dumps(unpacked_bytes, ensure_ascii=False, indent=1)
    return json_data


ver = sys.argv[1]
download_url_prefix = get_download_url_prefix(ver)
downloads_dir = os.path.join(".", "downloads")
manifest_file_path = os.path.join(
    downloads_dir, f"manifest_ch_v{ver}.json".format(ver=ver)
)
if not os.path.exists(manifest_file_path):
    print("downloading manifest:")
    try:
        manifest_url = download_url_prefix + "manifest.json"
        output = wget.download(manifest_url, manifest_file_path)
    except:
        print("download manifest failed, exiting")
        sys.exit(1)
