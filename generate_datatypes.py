#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""Extract MasterTable schemas from an IL2CPP dump, without manual overrides.

Usage: python3 generate_datatypes.py /path/to/dump.cs [-o class_fields.txt]

Each table occupies two output lines: its name and its pipe-separated fields.
MessagePackMember numbers determine column order, including inherited members.
Legacy records without those attributes retain alphabetical field order.
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re


TABLE_RE = re.compile(
    r"^public\s+(?:(?:sealed|abstract)\s+)?class\s+(\w+Table)\s*"
    r":\s*MasterTable<[^,>]+,\s*(\w+Record)>"
)
RECORD_RE = re.compile(
    r"^public\s+(?:(?:sealed|abstract)\s+)?class\s+(\w+Record)\s*"
    r":\s*(\w+Record)(?:<[^>]+>)?\b"
)
MEMBER_RE = re.compile(r"\[MessagePackMember\(\s*(\d+)\s*\)\]")
FIELD_RE = re.compile(
    r"^(public|private|protected|internal)\s+(.+?)\s+([A-Za-z_]\w*)\s*;"
)


@dataclass(frozen=True)
class Member:
    index: int | None
    name: str
    type_name: str


@dataclass
class Record:
    base: str
    members: list[Member] = field(default_factory=list)


def parse_dump(text: str) -> tuple[dict[str, str], dict[str, Record]]:
    """Read table declarations and instance fields, excluding methods/hotfixes."""
    tables: dict[str, str] = {}
    records: dict[str, Record] = {}
    current: str | None = None
    in_fields = False
    pending_index: int | None = None

    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        table_match = TABLE_RE.match(line)
        if table_match:
            table_name, record_name = table_match.groups()
            if table_name in tables:
                raise ValueError(f"Line {line_number}: duplicate table {table_name}")
            tables[table_name] = record_name

        record_match = RECORD_RE.match(line)
        if record_match:
            current, base = record_match.groups()
            if current in records:
                raise ValueError(f"Line {line_number}: duplicate record {current}")
            records[current] = Record(base)
            in_fields = False
            pending_index = None
            continue
        if current is None:
            continue
        if line == "// Fields":
            in_fields = True
            continue
        if line in ("// Properties", "// Methods", "}"):
            if pending_index is not None:
                raise ValueError(f"Line {line_number}: member index without a field")
            in_fields = False
            if line == "}":
                current = None
            continue
        if not in_fields:
            continue

        indices = MEMBER_RE.findall(line)
        if indices:
            if pending_index is not None or len(indices) != 1:
                raise ValueError(f"Line {line_number}: ambiguous member index")
            pending_index = int(indices[0])
            line = MEMBER_RE.sub("", line).strip()

        member_match = FIELD_RE.match(line)
        if not member_match:
            continue
        access, type_name, name = member_match.groups()
        modifiers = type_name.split()
        if "static" in modifiers or "const" in modifiers:
            if pending_index is not None:
                raise ValueError(f"Line {line_number}: serialized static/const field")
        elif access == "public" or pending_index is not None:
            records[current].members.append(Member(pending_index, name, type_name))
        pending_index = None

    if pending_index is not None:
        raise ValueError("End of dump: member index without a field")
    if not tables:
        raise ValueError("No MasterTable declarations found in dump")
    return tables, records


def resolve_members(records: dict[str, Record]) -> dict[str, list[Member]]:
    """Resolve inheritance before checking and ordering serialization indices."""
    resolved: dict[str, list[Member]] = {}
    resolving: set[str] = set()

    def resolve(name: str) -> list[Member]:
        if name in resolved:
            return resolved[name]
        if name in resolving:
            raise ValueError(f"Cyclic record inheritance: {name}")
        if name not in records:
            raise ValueError(f"Missing base/record declaration: {name}")
        resolving.add(name)
        record = records[name]
        inherited = [] if record.base == "MasterRecord" else resolve(record.base)
        members = inherited + record.members
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError(f"{name}: duplicate inherited field names")
        if not members:
            raise ValueError(f"{name}: no serialized fields found")
        if any(member.index is not None for member in members):
            if any(member.index is None for member in members):
                raise ValueError(f"{name}: mixed indexed and unindexed fields")
            members = sorted(members, key=lambda member: member.index)
            indices = [member.index for member in members]
            if indices != list(range(len(members))):
                raise ValueError(f"{name}: member indices must be unique and contiguous: {indices}")
        else:
            members = sorted(members, key=lambda member: member.name)
        resolving.remove(name)
        resolved[name] = members
        return members

    for name in records:
        resolve(name)
    return resolved


def extract_schemas(text: str) -> dict[str, list[str]]:
    tables, records = parse_dump(text)
    members = resolve_members(records)
    schemas = {}
    for table, record in tables.items():
        if record not in members:
            raise ValueError(f"{table}: missing record declaration {record}")
        schemas[table] = [member.name for member in members[record]]
    return schemas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", nargs="?", type=Path, default=Path("dump.cs"))
    parser.add_argument("-o", "--output", type=Path, default=Path("class_fields.txt"))
    args = parser.parse_args()
    try:
        schemas = extract_schemas(args.dump.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Schema extraction failed: {error}\n")
    content = "".join(f"{name}\n{'|'.join(fields)}\n" for name, fields in schemas.items())
    args.output.write_text(content, encoding="utf-8")
    print(f"Generated {len(schemas)} table schemas from {args.dump} -> {args.output}")


if __name__ == "__main__":
    main()
