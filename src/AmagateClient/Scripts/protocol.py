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


def exec_script_pack(script, uid=""):
    pass


def exec_script_recv(b_data):
    locals_dict = {}
    compiled = compile(b_data, "<AmagateServer>", "exec")
    eval(compiled, globals(), locals_dict)
    return locals_dict.get("result", None)


############################
def exec_script_ret_pack(script, uid):
    pass


def exec_script_ret_recv(b_data):
    result = exec_script_recv(b_data)
    return pickle.dumps(result, 1)


def exec_script_ret_resp(result):
    pass


############################
def set_attr_pack(obj_type, obj_name, attrs_dict):
    pass


def set_attr_recv(b_data):
    obj_type = int(struct.unpack("!B", b_data[0])[0])
    obj_name_len = int(struct.unpack("!B", b_data[1])[0])
    obj_name = b_data[2 : 2 + obj_name_len]
    if obj_type == T_ENTITY:
        obj = Bladex.GetEntity(obj_name)
    #
    offset = 2 + obj_name_len
    while offset < len(b_data):
        attr = int(struct.unpack("!H", b_data[offset : offset + 2])[0])
        offset = offset + 2
        attr_name = Codec[attr][NAME]
        # 获取解码器和数据长度
        _, unpacker, data_len, _ = Codec[attr]
        if data_len is None:
            data_len = struct.unpack("!H", b_data[offset : offset + 2])[0]
            offset = offset + 2
            # py1.5 解包H的类型是长整型，需要转成int
            data_len = int(data_len)
        # 解码数据
        attr_val = unpacker(b_data[offset : offset + data_len])
        offset = offset + data_len
        setattr(obj, attr_name, attr_val)


############################
def get_attr_pack(obj_type, obj_name, attrs, uid):
    pass


def get_attr_recv(b_data):
    obj_type = int(struct.unpack("!B", b_data[0])[0])
    obj_name_len = int(struct.unpack("!B", b_data[1])[0])
    obj_name = b_data[2 : 2 + obj_name_len]
    if obj_type == T_ENTITY:
        obj = Bladex.GetEntity(obj_name)
    #
    result = []
    offset = 2 + obj_name_len
    while offset < len(b_data):
        b_attr = b_data[offset : offset + 2]
        attr = int(struct.unpack("!H", b_attr)[0])
        attr_name = Codec[attr][NAME]
        b_attr_val = Codec[attr][PACK](getattr(obj, attr_name))
        result.append(b_attr + b_attr_val)
        offset = offset + 2
    return string.join(result, "")  # type: ignore


def get_attr_resp(b_data):
    pass


Handlers = {
    # packer, receiver, responder
    EXEC_SCRIPT: (exec_script_pack, exec_script_recv, None),
    EXEC_SCRIPT_RET: (exec_script_ret_pack, exec_script_ret_recv, exec_script_ret_resp),
    SET_ATTR: (set_attr_pack, set_attr_recv, None),
    GET_ATTR: (get_attr_pack, get_attr_recv, get_attr_resp),
}
