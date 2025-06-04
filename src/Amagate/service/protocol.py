# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

import struct

############################ 2字节标识符
############################ Attribute
POSITION = 0x0000  # 位置更新
TPOS = 0x0001  # 目标位置更新
NAME = 0x0002  # 字符串
STRING = 0x0003  # 字符串
############################ Operation
EXEC_SCRIPT = 0x0400  # 执行脚本
ENTITY_ATTR = 0x0401  # 实体属性更新
############################


def pack_float3(data):
    return struct.pack("!fff", *data)


def unpack_float3(data):
    return struct.unpack("!fff", data)


def pack_string(data):
    bytes_data = data.encode()
    return struct.pack("!H", len(bytes_data)) + bytes_data


def unpack_string(data):
    return data.decode()


PROTOCOL = {
    POSITION: (pack_float3, unpack_float3, 12),
    TPOS: (pack_float3, unpack_float3, 12),
    NAME: (pack_string, unpack_string, None),
    STRING: (pack_string, unpack_string, None),
}


def pack_data(op_type, data_dict):
    parts = [
        struct.pack("!H", op_type),
        *(struct.pack("!H", dt) + PROTOCOL[dt][0](d) for dt, d in data_dict.items()),
    ]
    return b"".join(parts)


# pack_data(ENTITY_SYNC, {POSITION: (1, 2, 3)})


# def unpack_data(binary_data):
#     # 读取操作类型（2字节）
#     offset = 0
#     op_type = struct.unpack_from("!H", binary_data, offset)[0]
#     offset += 2
#     data_dict = {}
#     while offset < len(binary_data):
#         # 读取数据类型（2字节）
#         data_type = struct.unpack_from("!H", binary_data, offset)[0]
#         offset += 2
#         # 检查类型是否合法
#         if data_type not in PROTOCOL:
#             raise ValueError(f"Unknown data type: {hex(data_type)}")
#         # 获取解码器和数据长度
#         _, unpacker, data_len = PROTOCOL[data_type]
#         if data_len is None:
#             data_len = struct.unpack_from("!H", binary_data, offset)[0]
#             offset += 2
#         # 解码数据
#         data = unpacker(binary_data[offset : offset + data_len])
#         data_dict[data_type] = data[0] if len(data) == 1 else data
#         offset += data_len
#     return op_type, data_dict


# HANDLERS = {}
