# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

import struct

############################
############################ 2字节标识符
############################
# Attribute
POSITION = 0x0000  # 位置更新
TPOS = 0x0001  # 目标位置更新
NAME = 0x0002  # 字符串
STRING = 0x0003  # 字符串

# Operation
HEARTBEAT = 0x0400  # 心跳包
EXEC_SCRIPT = 0x0401  # 执行脚本
ENTITY_ATTR = 0x0402  # 实体属性更新
LOAD_LEVEL = 0x0403  # 加载地图


############################
############################
############################
def pack_float3(data):
    return struct.pack("!fff", *data)


def unpack_float3(data):
    return struct.unpack("!fff", data)


def pack_string(data):
    bytes_data = data.encode(encoding="utf-8")
    return struct.pack("!H", len(bytes_data)) + bytes_data


def unpack_string(data):
    return data.decode(encoding="utf-8")


############################
############################
############################
PROTOCOL = {
    # packer, unpacker, data_len, name
    POSITION: (pack_float3, unpack_float3, 12, "Position"),
    TPOS: (pack_float3, unpack_float3, 12, "TPos"),
    NAME: (pack_string, unpack_string, None, ""),
    STRING: (pack_string, unpack_string, None, ""),
}


def pack_data(op_type, data_dict):
    msg_type = struct.pack("!H", op_type)
    parts = [struct.pack("!H", dt) + PROTOCOL[dt][0](d) for dt, d in data_dict.items()]
    msg_body = b"".join(parts)
    msg_len = struct.pack("!H", len(msg_body))
    return msg_type + msg_len + msg_body
