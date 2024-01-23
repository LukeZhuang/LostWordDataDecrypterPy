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
import json

f = open("dump.cs")
lines = []
record_line_nums: dict[str, int] = {}

for idx, line in enumerate(f):
    line_content = line.strip()
    lines.append(line_content)
    record_gp = re.findall(r"class ([a-zA-Z]+)Record : [a-zA-Z]+Record", line_content)
    if len(record_gp) > 0:
        record_line_nums[record_gp[0]] = idx

fo = open("class_fields.txt", "w")

for class_name, line_num in record_line_nums.items():
    fo.write(class_name + "Table\n")
    assert lines[line_num + 1] == "{"
    assert lines[line_num + 2] == "// Fields"
    idx = line_num + 3
    cur_line = lines[idx]
    class_fields: list[str] = []
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
            and not cur_line.startswith("[MessagePackMember")
        ):
            fields = [s for s in cur_line.split() if s.endswith(";")]
            assert len(fields) == 1
            class_fields.append(fields[0][:-1])
        idx += 1
    fo.write("|".join(class_fields) + "\n")

fo.close()
f.close()
