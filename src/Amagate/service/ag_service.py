# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import asyncio
import threading
import struct

#
from asyncio import run_coroutine_threadsafe
from typing import Any, TYPE_CHECKING

#
import bpy
from bpy.app.translations import pgettext
from mathutils import *  # type: ignore

#
from . import protocol
from ..scripts import data
from ..scripts import ag_utils

#
if TYPE_CHECKING:
    import bpy_stub as bpy

    Context = bpy.__Context
    Object = bpy.__Object
    Image = bpy.__Image
    Scene = bpy.__Scene
    Collection = bpy.__Collection

############################
logger = data.logger


############################ Global variables
server_thread = None  # type: AsyncServerThread | None

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 16730

SYNC_INTERVAL = 1.0 / 40  # 同步频率

HEARTBEAT_INTERVAL = 10  # 心跳间隔(秒)
HEARTBEAT_TIMEOUT = 15  # 心跳超时(秒)
############################


def get_status():
    return True if server_thread else False


def get_client_status():
    return True if server_thread and server_thread.clients else False


############################
# 执行脚本操作
def send_exec_script(script):
    # 打包数据
    packer = protocol.Handlers[protocol.EXEC_SCRIPT][protocol.PACK]
    msg = packer(script)
    # 添加到消息队列
    run_coroutine_threadsafe(server_thread.queue.put(msg), server_thread.loop)


# 发送摄像机数据
def send_camera_data(cam):
    # type: (Object) -> None
    cam_pos, target_pos = ag_utils.get_camera_transform(cam)
    # 打包数据
    packer = protocol.Handlers[protocol.SET_ATTR][protocol.PACK]
    msg = packer(
        protocol.T_ENTITY,
        "Camera",
        {
            protocol.A_POSITION: cam_pos,
            protocol.A_TPOS: target_pos,
        },
    )
    # 添加到消息队列
    run_coroutine_threadsafe(server_thread.queue.put(msg), server_thread.loop)


# 请求摄像机数据
def request_camera_data(callback):
    uid = AsyncRequestResponse.callback_register(callback)
    packer = protocol.Handlers[protocol.GET_ATTR][protocol.PACK]
    msg = packer(
        protocol.T_ENTITY, "Camera", (protocol.A_POSITION, protocol.A_TPOS), uid
    )
    # 添加到消息队列
    run_coroutine_threadsafe(server_thread.queue.put(msg), server_thread.loop)


############################


# 异步请求-响应
class AsyncRequestResponse:
    callbacks = {}

    # 回调注册
    @classmethod
    def callback_register(cls, callback):
        uid = len(cls.callbacks)
        cls.callbacks[uid] = callback
        return struct.pack("!B", uid)

    # pop回调
    @classmethod
    def callback_pop(cls, uid):
        return cls.callbacks.pop(uid, None)


# 异步服务器线程
class AsyncServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = asyncio.new_event_loop()
        self.server = None  # type: asyncio.AbstractServer | None
        self.queue: asyncio.Queue | None = None
        self.clients = []  # type: list[tuple[asyncio.Future, asyncio.Event]]
        self.server_closing = False
        self.server_closed: asyncio.Event

    # 接收消息
    async def receive_task(self, reader, cancel_event):
        # type: (asyncio.StreamReader, asyncio.Event) -> None
        try:
            while True:
                msg = await asyncio.wait_for(
                    reader.read(2), timeout=HEARTBEAT_TIMEOUT
                )  # 异步等待读取
                if not msg:  # 客户端关闭连接
                    cancel_event.set()
                    logger.debug("Client closed connection")
                    break
                #
                # logger.debug(f"Received message: {msg}")
                msg_type = struct.unpack("!H", msg)[0]
                if msg_type == protocol.HEARTBEAT:
                    pass
                    # logger.debug("Received heartbeat")
                else:
                    handler_select = struct.unpack("!B", await reader.read(1))[0]
                    responder = protocol.Handlers[msg_type][protocol.RESP]
                    handler = protocol.Handlers[msg_type][handler_select]
                    if responder:
                        uid = struct.unpack("!B", await reader.read(1))[0]

                    msg_len = struct.unpack("!H", await reader.read(2))[0]
                    msg_body = await reader.read(msg_len)

                    result = handler(msg_body)
                    if handler_select == protocol.RESP:
                        callback = AsyncRequestResponse.callback_pop(uid)
                        callback(result)
                    elif responder:
                        pass

        except asyncio.CancelledError:
            logger.debug("Receive task cancelled")
        except Exception as e:
            logger.debug(f"Receive task error: {e}")
            cancel_event.set()

    # 发送消息
    async def send_task(self, writer, cancel_event):
        # type: (asyncio.StreamWriter, asyncio.Event) -> None
        try:
            while True:
                msg = await self.queue.get()
                writer.write(msg)
                await writer.drain()
        except asyncio.CancelledError:
            logger.debug("Send task cancelled")
        except Exception as e:
            logger.debug(f"Send task error: {e}")
            cancel_event.set()
        #
        writer.close()  # 关闭连接
        try:
            await writer.wait_closed()
        except Exception as e:
            logger.debug(f"wait_closed error: {e}")

    # 定时添加心跳包到消息队列
    async def send_heartbeats(self):
        try:
            while True:
                await self.queue.put(struct.pack("!H", protocol.HEARTBEAT))
                await asyncio.sleep(HEARTBEAT_INTERVAL)
        except asyncio.CancelledError:
            logger.debug("Send heartbeats task cancelled")

    # 处理客户端连接
    async def handle_client(self, reader, writer):
        # type: (asyncio.StreamReader, asyncio.StreamWriter) -> None

        addr = writer.get_extra_info("peername")
        logger.info(f"Connected to {addr}")

        #
        cancel_event = asyncio.Event()
        tasks = asyncio.gather(
            self.receive_task(reader, cancel_event),
            self.send_task(writer, cancel_event),
            self.send_heartbeats(),
        )
        self.clients.append((tasks, cancel_event))
        client_idx = len(self.clients) - 1
        done, pending = await asyncio.wait(
            {
                tasks,
                asyncio.create_task(cancel_event.wait()),
            },
            return_when=asyncio.FIRST_COMPLETED,
        )
        # 连接中断的情况，非关闭服务器
        if cancel_event.is_set():
            logger.debug("cancel_event is set")
            self.clients.pop(client_idx)

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("pending task cancelled")

        #
        logger.info(f"{addr} - Connection closed")
        if not self.clients:
            scene_data = bpy.context.scene.amagate_data
            scene_data.operator_props["camera_sync"] = False
            # 如果是关闭了服务器
            if self.server_closing:
                self.server_closed.set()

    # 创建服务器
    async def create_server(self):
        global SERVER_PORT

        while True:
            try:
                server = await asyncio.start_server(
                    self.handle_client, SERVER_HOST, SERVER_PORT
                )
                logger.info(f"Server is listening on {SERVER_HOST}:{SERVER_PORT}")
                break
            except OSError:
                logger.warning(f"Port {SERVER_PORT} is not available")
                return
                # logger.warning(f"Port {SERVER_PORT} is not available, trying next port...")
                # SERVER_PORT += 1
        # 服务器启动成功
        self.queue = asyncio.Queue()
        self.server_closed = asyncio.Event()
        self.server = server
        async with server:
            # 服务器永久运行
            try:
                await server.serve_forever()
            except asyncio.CancelledError:
                if self.clients:
                    while self.clients:
                        task, _ = self.clients.pop()
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    await self.server_closed.wait()
                logger.debug("Server stopped")

    # 服务器线程运行函数
    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.create_server())
        self.loop.close()
        # self.loop.run_forever()
        self.on_exit()
        logger.debug(f"Server thread stopped")

    # 服务器退出时调用
    def on_exit(self):
        global server_thread
        server_thread = None


# 启动服务器
def start_server():
    global server_thread
    if server_thread is None:
        server_thread = AsyncServerThread()
        server_thread.start()
        logger.debug(f"Server thread started")
    # return server_thread


# 停止服务器
def stop_server():
    global server_thread
    if server_thread:

        async def shutdown():
            server_thread.server_closing = True
            server_thread.server.close()
            await server_thread.server.wait_closed()
            # server_thread.loop.stop()

        # server_thread.loop.call_soon_threadsafe(lambda: asyncio.create_task(shutdown()))
        logger.debug(f"Server thread stopping...")
        asyncio.run_coroutine_threadsafe(shutdown(), server_thread.loop).result()
