#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
This script process dump.cs and extract all Table data types and the result is
written into "class_fields.txt". The format is one line of Table name, followed
by one line of all fields (splited using '|'). For example:

  UnitTable
  id|name|...

"""

import re

f = open("dump.cs")
lines = []
record_line_nums: dict[str, int] = {}

for idx, line in enumerate(f):
    line_content = line.strip()
    lines.append(line_content)
    record_gp = re.findall(r"class ([a-zA-Z]+)Record : ([a-zA-Z]+)Record", line_content)
    if len(record_gp) > 0:
        if record_gp[0][1] != "Master":
            print(
                "unable to handle inherited data type: "
                + record_gp[0][0]
                + ", skipping"
            )
        else:
            record_line_nums[record_gp[0][0]] = idx

fo = open("class_fields.txt", "w")

for class_name, line_num in record_line_nums.items():
    fo.write(class_name + "Table\n")
    assert lines[line_num + 1] == "{"
    assert lines[line_num + 2] == "// Fields"
    idx = line_num + 3
    cur_line = lines[idx]
    class_fields: list[str] = []
    msgpack_ids: list[int] = []
    while (
        lines[idx].startswith("public")
        or lines[idx].startswith("private")
        or lines[idx].startswith("protected")
        or lines[idx].startswith("[MessagePackMember")
    ):
        cur_line = lines[idx]
        if (
            "const" not in cur_line
            and "static DelegateBridge" not in cur_line
            and "XLua_Gen_Delegate" not in cur_line
            and cur_line.startswith("public")
        ):
            fields = [s for s in cur_line.split() if s.endswith(";")]
            assert len(fields) == 1
            class_fields.append(fields[0][:-1])
        elif cur_line.startswith("[Mess"):
            msgpack_id = re.findall(r"MessagePackMember\((\d+)\)", cur_line)
            assert len(msgpack_id) == 1
            msgpack_ids.append(int(msgpack_id[0]))
        idx += 1
    if len(msgpack_ids) > 0:
        # msgpack_ids should be [0, 1, 2, ..., n-1]
        assert (
            len(msgpack_ids) == len(class_fields)
            and min(msgpack_ids) == 0
            and max(msgpack_ids) == len(msgpack_ids) - 1
            and msgpack_ids == sorted(list(set(msgpack_ids)))
        )
    else:
        class_fields = sorted(class_fields)
    fo.write("|".join(class_fields) + "\n")

fo.close()
f.close()
