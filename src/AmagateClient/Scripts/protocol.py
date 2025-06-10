# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 1.5
# License: MIT

import Bladex

#
import struct
import string
import pickle

#
from AmagateClient.Scripts import utils

############################
logger = utils.logger

############################
############################ 2字节标识符
############################

# Operation 0x0000-0x0FFF
HEARTBEAT = 0x0000  # 心跳包
EXEC_SCRIPT = 0x0001  # 执行脚本
EXEC_SCRIPT_RET = 0x0002  # 执行脚本并返回结果
GET_ATTR = 0x0003  # 获取属性
SET_ATTR = 0x0004  # 设置属性
CALL_FUNC = 0x0005  # 调用函数
CALL_FUNC_RET = 0x0006  # 调用函数并返回结果
LOAD_LEVEL = 0x0007  # 加载地图

# Attribute 0x1000-0x1FFF
A_POSITION = 0x1000  # 位置更新
A_TPOS = 0x1001  # 目标位置更新
A_NAME = 0x1002  # 字符串
A_STRING = 0x1003  # 字符串

# Method 0x2000-0x2FFF

# Object Type 0x00-0xFF
T_MODULE = 0x00  # 模块
T_ENTITY = 0x01  # 实体

############################
############################
############################
PACK = 0
UNPACK = 1
LENGTH = 2
NAME = 3

RECV = 1
RESP = 2


############################
############################ 编码/解码处理
############################
def pack_float3(data):
    return struct.pack("!fff", data[0], data[1], data[2])


def unpack_float3(data):
    return struct.unpack("!fff", data)


def pack_string(data):
    bytes_data = data
    return struct.pack("!H", len(bytes_data)) + bytes_data


def unpack_string(data):
    return data


Codec = {
    # packer, unpacker, data_len, name
    A_POSITION: (pack_float3, unpack_float3, 12, "Position"),
    A_TPOS: (pack_float3, unpack_float3, 12, "TPos"),
    A_NAME: (pack_string, unpack_string, None, ""),
    A_STRING: (pack_string, unpack_string, None, ""),
}

############################
############################
############################
