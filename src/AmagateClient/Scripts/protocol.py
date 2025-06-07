# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 1.5
# License: MIT

import Bladex

#
import struct
import traceback

#
from AmagateClient.Scripts import utils

############################
logger = utils.logger

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
    return struct.pack("!fff", data[0], data[1], data[2])


def unpack_float3(data):
    return struct.unpack("!fff", data)


def pack_string(data):
    bytes_data = data.encode()
    return struct.pack("!H", len(bytes_data)) + bytes_data


def unpack_string(data):
    return data


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

############################
############################ 数据处理器
############################


def unpack_data(binary_data):
    data_dict = {}
    offset = 0
    while offset < len(binary_data):
        data_type = struct.unpack("!H", binary_data[offset : offset + 2])[0]
        # logger.debug("data_type: 0x%04X" % data_type)
        offset = offset + 2
        # 获取解码器和数据长度
        _, unpacker, data_len, _ = PROTOCOL[data_type]
        if data_len is None:
            data_len = struct.unpack("!H", binary_data[offset : offset + 2])[0]
            data_len = int(data_len)
            offset = offset + 2
        # 解码数据
        data = unpacker(binary_data[offset : offset + data_len])
        data_dict[data_type] = data
        offset = offset + data_len
        # logger.debug("unpacked data: %s=%s" % (data_type, data))
    return data_dict


def handle_entity_attr(data_dict):
    ent = Bladex.GetEntity(data_dict[NAME])
    for k, v in data_dict.items():
        if k == NAME:
            continue

        attr_name = PROTOCOL[k][3]
        setattr(ent, attr_name, v)
        # logger.debug("Received data_dict: 0x%04X=%s" % (k, v))


def handle_exec_script(data_dict):
    compiled = compile(data_dict[STRING], "<AmagateServer>", "exec")
    eval(compiled)


HANDLERS = {ENTITY_ATTR: handle_entity_attr, EXEC_SCRIPT: handle_exec_script}
