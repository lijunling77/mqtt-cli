import os
import sys
curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

from paho.mqtt import client as mqtt
import datetime
import uuid
import queue

from paho.mqtt.enums import CallbackAPIVersion


message_queue = queue.Queue()


class Subscription:
    def __init__(self, mt_ip, port, mt_user, mt_pwd):
        self.mt_ip = mt_ip
        self.port = port
        self.mt_user = mt_user
        self.mt_pwd = mt_pwd

    def on_connect(self, client, userdata, flags, rc):
        """一旦连接成功, 回调此方法"""
        rc_status = ["连接成功", "协议版本不正确", "客户端标识符无效", "服务器不可用", "用户名或密码不正确", "未经授权"]
        print("connect：", rc_status[rc])

    def on_message(self, client, userdata, msg):
        """
        表示将 msg.payload 使用 GB2312 进行解码，并指定当遇到无法解码的字符时使用 ignore 参数进行错误处理，即忽略无法解码的字符
        """
        result = [msg.topic, msg.payload.decode('gb2312', 'ignore')]
        # 将收到的消息放入到消息队列中
        message_queue.put(result)

    def mqtt_connect(self):
        """连接MQTT服务器"""
        mqttClient = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1, client_id=str(uuid.uuid4()))
        mqttClient.on_connect = self.on_connect  # 返回连接状态的回调函数
        mqttClient.on_message = self.on_message  # 返回订阅消息回调函数
        mqttClient.username_pw_set(self.mt_user, self.mt_pwd)  # MQTT服务器账号密码
        mqttClient.connect(self.mt_ip, self.port, 60)  # MQTT地址、端口、心跳间隔（单位为秒）
        mqttClient.loop_start()  # 启用线程连接
        return mqttClient

    def on_subscribe(self, mqttClient, sub_topic, qos=0):
        """订阅主题"""
        mqttClient.subscribe(sub_topic, qos)

    def on_publish(self, mqttClient, pub_topic, msg, qos=0):
        """发布消息"""
        result = mqttClient.publish(pub_topic, msg, qos)
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = result[0]
        if status == 0:
            print(now + ", " + "{}, Send msg:{} ".format(pub_topic, msg))
        else:
            print(now + ", " + "{}, Failed to send message:{} ".format(pub_topic, msg))

