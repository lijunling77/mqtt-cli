# -*- coding: utf-8 -*-
"""
MQTT 连接管理模块
"""
import datetime
import uuid
import queue
import logging

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

logger = logging.getLogger(__name__)

# MCP 模式下静默 print
_mcp_mode = __import__("os").environ.get("MQTT_CLI_MCP_MODE") == "1"

message_queue = queue.Queue()


class Subscription:
    def __init__(self, mt_ip, port, mt_user, mt_pwd):
        self.mt_ip = mt_ip
        self.port = port
        self.mt_user = mt_user
        self.mt_pwd = mt_pwd

    def on_connect(self, client, userdata, flags, rc):
        """连接回调"""
        rc_status = ["连接成功", "协议版本不正确", "客户端标识符无效",
                     "服务器不可用", "用户名或密码不正确", "未经授权"]
        if not _mcp_mode:
            print("connect：", rc_status[rc])

    def on_message(self, client, userdata, msg):
        """消息回调，将收到的消息放入队列"""
        result = [msg.topic, msg.payload.decode('gb2312', 'ignore')]
        message_queue.put(result)

    def mqtt_connect(self):
        """连接 MQTT 服务器，返回 client 实例"""
        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION1,
            client_id=str(uuid.uuid4())
        )
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.username_pw_set(self.mt_user, self.mt_pwd)
        client.connect(self.mt_ip, self.port, 60)
        client.loop_start()
        return client

    def on_subscribe(self, client, sub_topic, qos=0):
        """订阅主题"""
        client.subscribe(sub_topic, qos)

    def on_publish(self, client, pub_topic, msg, qos=0):
        """发布消息"""
        result = client.publish(pub_topic, msg, qos)
        if not _mcp_mode:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            short = msg[:150] + ("..." if len(str(msg)) > 150 else "")
            if result[0] == 0:
                print(f"{now}, {pub_topic}, Send msg:{short}")
            else:
                print(f"{now}, {pub_topic}, Failed to send: {short}")
