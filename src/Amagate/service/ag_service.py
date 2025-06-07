# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import asyncio
import threading
import struct

#
from typing import Any, TYPE_CHECKING

#
from bpy.app.translations import pgettext

#
from . import protocol
from ..scripts import data

############################
logger = data.logger


############################ Global variables
server_thread = None  # type: AsyncServerThread | None

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 1673

HEARTBEAT_INTERVAL = 3  # 5  # 心跳间隔(秒)
HEARTBEAT_TIMEOUT = 6  # 10  # 心跳超时(秒)
############################


def get_status():
    return pgettext("Closed") if server_thread is None else f'{pgettext("Running")}...'


def get_client_status():
    return (
        pgettext("Connected", "Server")
        if server_thread and server_thread.clients
        else pgettext("Not connected")
    )


class AsyncServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = asyncio.new_event_loop()
        self.server = None  # type: asyncio.AbstractServer | None
        self.queue: asyncio.Queue | None = None
        self.clients = []  # type: list[tuple[asyncio.Future, asyncio.Event]]
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
                logger.debug(f"Received message: {msg}")
                msg_type = struct.unpack("!H", msg)[0]
                if msg_type == protocol.HEARTBEAT:
                    logger.debug("Received heartbeat")

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
        #
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
            self.server_closed.set()

        # try:
        #     await tasks
        # except asyncio.CancelledError:
        #     pass
        # finally:
        #     writer.close()  # 关闭连接
        #     await writer.wait_closed()
        #     logger.info(f"{addr} - Connection closed")

        # while True:
        #     try:
        #         # 从队列获取消息
        #         message = await message_queue.get()
        #         # writer.write(message.encode())
        #         # await writer.drain()
        #     # except queue.Empty:
        #     #     await asyncio.sleep(0.03)
        #     except asyncio.IncompleteReadError:
        #         # 处理客户端非正常中断的情况（比如连接被重置）
        #         logger.debug(f"{addr} - Connection closed unexpectedly.")
        #         break
        #     except ConnectionResetError:
        #         # 处理连接重置的情况（通常是客户端强行关闭连接）
        #         logger.debug(f"{addr} - Connection reset by peer.")
        #         break
        #     except Exception as e:
        #         # 捕获其他未预料到的异常
        #         logger.debug(f"{addr} - Unexpected error: {e}")
        #         break

        # writer.close()
        # await writer.wait_closed()
        # logger.info(f"Connection with {addr} closed")

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
            server_thread.server.close()
            await server_thread.server.wait_closed()
            # server_thread.loop.stop()

        # server_thread.loop.call_soon_threadsafe(lambda: asyncio.create_task(shutdown()))
        logger.debug(f"Server thread stopping...")
        asyncio.run_coroutine_threadsafe(shutdown(), server_thread.loop).result()
