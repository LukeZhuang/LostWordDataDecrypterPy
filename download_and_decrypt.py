#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
Decrypt and unpack master tables. If a class is in class_fields.txt, which is
generated from dump.cs, and it matches the unpacked dict, then we can create
an accurate json file. Otherwise we can create an anonymous json
"""

from typing import Any
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import msgpack
import json
import wget
import sys
import os
import re

SECRECT_KEY = (
    "jR3GTK6vR6gPz2MNA7hPiGEYbG6vBsMAS5jaretmHu4PS78zz3YcijFBM9yJha5HL7wn3DFYd4XaFNLB"
)
KEY_LENGTH = 16
IV_LENGTH = 16


def read_class_fields() -> dict[str, list[str]]:
    class_fields_file = os.path.join(".", "class_fields.txt")
    class_contents = {}
    if os.path.exists(class_fields_file):
        cff = open(class_fields_file)
        table_name = None
        for line in cff:
            cur_line = line.strip()
            if cur_line.endswith("Table"):
                assert table_name is None
                table_name = cur_line
            else:
                assert table_name is not None
                class_contents[table_name] = cur_line.split("|")
                table_name = None
    return class_contents


def get_download_url_prefix(ver: str) -> str:
    return f"http://thcdn.gggamedownload.com/source/Master_v{ver}/".format(ver=ver)


# some magic shuffle method, concat the last X bytes and the remaining,
# in which X is 1<<k and k is from 1 to 26
def shuffle_src(src: bytes, enc_key: int) -> bytes:
    if enc_key == -1:
        return src
    assert enc_key >= 1 and enc_key <= 26
    shuffle_len = (1 << enc_key) % len(src)
    return src[-shuffle_len:] + src[:-shuffle_len]


def get_encryption_key_bytes(table_name: str) -> bytes:
    index = len(table_name)
    key_arr = bytearray(KEY_LENGTH)
    table_name_bytes = table_name.encode()
    secrect_key_bytes = SECRECT_KEY.encode()
    for idx in range(KEY_LENGTH):
        name_byte = table_name_bytes[idx % len(table_name)]
        key_byte = secrect_key_bytes[index % len(SECRECT_KEY)]
        key_arr[idx] = name_byte ^ key_byte
        index += name_byte
    return key_arr


def decrypt(src: bytes, table_name: str) -> bytes:
    if table_name == "GachaTable":
        enc_key = 9
    elif table_name == "UnitTable":
        enc_key = 15
    else:
        enc_key = -1
    src = shuffle_src(src, enc_key)
    key_bytes = get_encryption_key_bytes(table_name)
    iv_bytes = src[:IV_LENGTH]
    aes = AES.new(key_bytes, AES.MODE_CBC, iv=iv_bytes)
    try:
        decrypted_bytes = aes.decrypt(src[IV_LENGTH:])
        decrypted_bytes = unpad(decrypted_bytes, 16)
    except Exception:
        print("decrypt " + table_name + " failed")
        return bytearray()
    return decrypted_bytes


def unpack(decrypted_bytes: bytes, table_name: str) -> dict[Any, tuple[Any]]:
    try:
        unpacked_dict = msgpack.unpackb(
            decrypted_bytes, use_list=False, raw=False, strict_map_key=False
        )
        assert isinstance(unpacked_dict, dict)
        return unpacked_dict
    except Exception:
        print("unpack " + table_name + " failed")
        return {}


def refine_unpacked_dict(
    table_name: str,
    unpacked_dict: dict[Any, tuple[Any]],
    class_contents: dict[str, list[str]],
) -> tuple[bool, dict[Any, dict[str, Any]]]:
    if table_name not in class_contents:
        return False, unpacked_dict
    field_names = class_contents[table_name]
    refined_dict = {}
    for key, content in unpacked_dict.items():
        if isinstance(content, tuple) and len(content) == len(field_names):
            named_content: dict[str, Any] = {}
            for idx, item in enumerate(content):
                named_content[field_names[idx]] = item
            refined_dict[key] = named_content
        else:
            return False, unpacked_dict
    return True, refined_dict


def dict_to_csv(
    csv_output_path: str,
    table_name: str,
    class_contents: dict[str, list[str]],
    unpacked_dict: dict[Any, dict[str, Any]],
):
    if table_name not in class_contents:
        return
    class_content = class_contents[table_name]
    fo = open(csv_output_path, "w")
    fo.write(",".join(class_content) + "\r\n")
    for key, content in unpacked_dict.items():
        values: list[str] = []
        for field_name, value in content.items():
            value_str = str(value)
            value_str = value_str.replace("\r\n", "<ret>")
            value_str = value_str.replace("\n", "<ret>")
            value_str = value_str.replace(",", "|")
            if re.search(r"^\s*$", value_str):
                value_str = "(empty)"
            values.append(value_str)
        fo.write(",".join(values) + "\r\n")
    fo.close()


ver = sys.argv[1]
download_url_prefix = get_download_url_prefix(ver)
downloads_dir = os.path.join(".", "downloads")
outputs_dir = os.path.join(".", "outputs")

manifest_file_path = os.path.join(
    downloads_dir, f"manifest_ch_v{ver}.json".format(ver=ver)
)
class_contents = read_class_fields()
if not os.path.exists(manifest_file_path):
    print("downloading manifest:")
    try:
        manifest_url = download_url_prefix + "manifest.json"
        output = wget.download(manifest_url, manifest_file_path)
    except Exception:
        print("download manifest failed, exiting")
        sys.exit(1)

manifest_file = open(manifest_file_path)
data = json.load(manifest_file)
asset_infos = data["AssetInfos"]
for asset_info in asset_infos:
    file_name = asset_info["Name"]
    asset_paths = asset_info["AssetPaths"]
    if "Master.bytes" not in "".join(asset_paths):
        continue
    assert len(asset_paths) == 1
    reg = re.findall(r"Assets/East/Master/(.*)Master.bytes", asset_paths[0])
    assert len(reg) == 1
    table_name = reg[0] + "Table"
    print("Processing " + table_name)
    file_path = os.path.join(downloads_dir, file_name)
    if not os.path.exists(file_path):
        file_url = download_url_prefix + file_name
        try:
            output = wget.download(file_url, file_path, bar=None)
        except Exception:
            print("download " + table_name + " failed")
            continue
    src_file = open(file_path, "rb")
    src_bytes = src_file.read()
    src_file.close()
    os.remove(file_path)
    decrypted_bytes = decrypt(src_bytes, table_name)
    unpacked_dict = unpack(decrypted_bytes, table_name)
    refined, unpacked_dict = refine_unpacked_dict(
        table_name, unpacked_dict, class_contents
    )
    output_file = os.path.join(
        outputs_dir, table_name + ("" if refined else ".anonymous") + ".json"
    )
    fo = open(output_file, "w")
    for key, content in unpacked_dict.items():
        content_json = json.dumps(
            content,
            ensure_ascii=False,
        )
        fo.write(content_json + "\n")
    fo.close()
    # only produce csv file if we have accurate json
    if refined:
        csv_output_path = os.path.join(outputs_dir, table_name + ".csv")
        dict_to_csv(csv_output_path, table_name, class_contents, unpacked_dict)
