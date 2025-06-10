# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 1.5
# License: MIT

import Bladex

#
import threading
import sys
import string
import select
import time
import struct
import os
import traceback
import pickle

sys.path.append("../../LIB/PythonLib/Plat-Win")

import socket

#
import BODLoader

#
from AmagateClient.Scripts import utils
from AmagateClient.Scripts import protocol

############################
true = 1 == 1
false = not true

client_thread = None

KEY = "AmagateClient"

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 16730

SYNC_INTERVAL = 1.0 / 60  # 同步频率

HEARTBEAT_INTERVAL = 10  # 心跳间隔(秒)
HEARTBEAT_TIMEOUT = 15  # 心跳超时(秒)
############################

printx = utils.printx
logger = utils.logger
############################


# 恢复摄像机
def restore_camera():
    e = Bladex.GetEntity("Camera")
    e.SetPersonView("Player1")
    e.Cut()


# 移动玩家到摄像机
def player_to_camera():
    e = Bladex.GetEntity("Player1")
    e.Position = Bladex.GetEntity("Camera").Position
    e.SetOnFloor()


# 加载地图
def load_map(map_directory):
    if not os.path.exists("../%s" % map_directory):
        return 0
    eval_str = (
        'Bladex.SetAfterFrameFunc("AG.load_map", lambda t: Bladex.LoadLevel("%s",))'
        % map_directory
    )
    eval(eval_str)
    return 1


# 重载地图
def reload_map():
    Bladex.SetAfterFrameFunc(
        "AG.reload_map", lambda t: Bladex.LoadLevel(Bladex.GetCurrentMap())
    )


############################
############################
############################


def exec_script_send(script, uid=""):
    pass


def exec_script_recv(b_data):
    locals_dict = {}
    compiled = compile(b_data, "<AmagateServer>", "exec")
    eval(compiled, globals(), locals_dict)
    return locals_dict.get("result", None)


############################
def exec_script_ret_send(script, uid):
    pass


def exec_script_ret_recv(b_data):
    result = exec_script_recv(b_data)
    return pickle.dumps(result, 1)


def exec_script_ret_resp(result):
    pass


############################
def set_attr_send(obj_type, obj_name, attrs_dict):
    pass


def set_attr_recv(b_data):
    obj_type = int(struct.unpack("!B", b_data[0])[0])
    obj_name_len = int(struct.unpack("!B", b_data[1])[0])
    obj_name = b_data[2 : 2 + obj_name_len]
    if obj_type == protocol.T_ENTITY:
        obj = Bladex.GetEntity(obj_name)
    #
    offset = 2 + obj_name_len
    while offset < len(b_data):
        attr = int(struct.unpack("!H", b_data[offset : offset + 2])[0])
        offset = offset + 2
        attr_name = protocol.Codec[attr][protocol.NAME]
        # 获取解码器和数据长度
        _, unpacker, data_len, _ = protocol.Codec[attr]
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
def get_attr_send(obj_type, obj_name, attrs, uid):
    pass


def get_attr_recv(b_data):
    obj_type = int(struct.unpack("!B", b_data[0])[0])
    obj_name_len = int(struct.unpack("!B", b_data[1])[0])
    obj_name = b_data[2 : 2 + obj_name_len]
    if obj_type == protocol.T_ENTITY:
        obj = Bladex.GetEntity(obj_name)
    #
    result = []
    offset = 2 + obj_name_len
    while offset < len(b_data):
        b_attr = b_data[offset : offset + 2]
        attr = int(struct.unpack("!H", b_attr)[0])
        attr_name = protocol.Codec[attr][protocol.NAME]
        b_attr_val = protocol.Codec[attr][protocol.PACK](getattr(obj, attr_name))
        result.append(b_attr + b_attr_val)
        offset = offset + 2
    return string.join(result, "")  # type: ignore


def get_attr_resp(b_data):
    pass


############################
Handlers = {
    # sender, receiver, responder
    protocol.EXEC_SCRIPT: (exec_script_send, exec_script_recv, None),
    protocol.EXEC_SCRIPT_RET: (
        exec_script_ret_send,
        exec_script_ret_recv,
        exec_script_ret_resp,
    ),
    protocol.SET_ATTR: (set_attr_send, set_attr_recv, None),
    protocol.GET_ATTR: (get_attr_send, get_attr_recv, get_attr_resp),
}
############################
############################
############################


# 客户端线程
class ClientThread(threading.Thread):
    def __init__(self, *args):
        # threading.Thread.__init__(self, *args)
        apply(threading.Thread.__init__, (self,) + args)
        self.name = "Amagate Client Thread"
        self.sock = None  # type: socket.socket | None
        self.last_heartbeat = time.time()
        self.sock_lock = threading.Lock()
        self.sock_lock.acquire()
        self.callback = None
        self.callback_args = ()
        #

    def handle_message(self):
        # print不是线程安全的，会导致游戏崩溃
        sock = self.sock
        while 1:
            # 如果客户端被卸载，则退出循环
            if not BODLoader.BLModInfo["Amagate Client"]["Installed"]:
                logger.debug("Client uninstalled")
                break
            # 如果客户端被禁用，则退出循环
            if not BODLoader.BLModInfo["Amagate Client"]["Enabled"]:
                logger.debug("Client disabled")
                break
            # 如果用户断开连接（锁被释放），则退出循环
            if not self.sock_lock.locked():
                logger.debug("Socket lock released")
                break

            readable, writable, exceptional = select.select([sock], [sock], [sock], 1.0)
            if readable:
                msg = sock.recv(2)
                if not msg:  # 服务器关闭连接
                    logger.debug("Server closed connection")
                    break

                msg_type = int(struct.unpack("!H", msg)[0])
                # logger.debug("msg_type: 0x%04X" % msg_type)
                # 心跳包
                if msg_type == protocol.HEARTBEAT:
                    # logger.debug("Received heartbeat")
                    self.last_heartbeat = time.time()
                    if writable:
                        sock.send(struct.pack("!H", protocol.HEARTBEAT))  # type: ignore
                        # logger.debug("Sent heartbeat")
                else:
                    try:
                        handler_select = int(struct.unpack("!B", sock.recv(1))[0])
                        responder = Handlers[msg_type][protocol.RESP]
                        handler = Handlers[msg_type][handler_select]
                        if responder:
                            uid = int(struct.unpack("!B", sock.recv(1))[0])

                        msg_len = int(struct.unpack("!H", sock.recv(2))[0])
                        recv_len = 0
                        msg_body = ""
                        while recv_len < msg_len:
                            chunk = sock.recv(msg_len - recv_len)
                            msg_body = msg_body + chunk  # type: ignore
                            recv_len = recv_len + len(chunk)

                        result = handler(msg_body)
                        if handler_select == protocol.RESP:
                            pass
                        elif responder:
                            sock.send(struct.pack("!H", msg_type) + struct.pack("!B", protocol.RESP) + struct.pack("!B", uid) + struct.pack("!H", len(result)) + result)  # type: ignore
                    except:
                        traceback.print_exc(file=logger.output)
                        logger.output.flush()

            else:
                current_time = time.time()
                if current_time - self.last_heartbeat > HEARTBEAT_TIMEOUT:
                    logger.debug("heartbeat timeout")
                    break
            time.sleep(SYNC_INTERVAL)
        # 关闭连接
        sock.close()

    def run(self):
        logger.output.write("\n")
        logger.debug("Client thread started")
        self.handle_message()
        self.on_exit()

    def on_exit(self):
        global client_thread
        client_thread = None
        Bladex.DeleteStringValue(KEY)
        if self.callback:
            apply(self.callback, self.callback_args)
        restore_camera()
        logger.debug("Client thread exited")


# 连接到服务器
def connect_server(callback=None, callback_args=()):
    global client_thread
    if client_thread is None:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.setblocking(0)  # 非阻塞模式 # type: ignore
        try:
            client_socket.connect((SERVER_HOST, SERVER_PORT))
        except:
            pass  # 非阻塞模式下 connect 会立即返回
        # 用 select 检测是否可写（连接成功）
        readable, writable, exceptional = select.select(
            [client_socket], [client_socket], [client_socket], 1.0
        )
        if writable:
            client_thread = ClientThread()
            client_thread.callback = callback
            client_thread.callback_args = callback_args
            client_thread.sock = client_socket
            client_thread.setDaemon(true)
            client_thread.start()
            Bladex.SetStringValue(KEY, "1")
            printx("success")
            return 1
        else:
            client_socket.close()
            printx("fail")
    return 0


# 自动连接
def auto_connect():
    if Bladex.GetStringValue(KEY):
        logger.debug("reconnecting...")
        result = connect_server()
        if result == 0:
            Bladex.DeleteStringValue(KEY)
            printx("Failed to connect to server")


# 断开服务器连接
def disconnect_server(callback=None, callback_args=()):
    global client_thread
    if client_thread is not None:
        # client_thread.sock.close()
        # client_thread.join()
        # client_thread = None
        logger.debug("Disconnecting...")
        client_thread.callback = callback
        client_thread.callback_args = callback_args

        client_thread.sock_lock.release()


############################
auto_connect()
