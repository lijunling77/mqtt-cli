# -*- coding: utf-8
import json
import os
import sys
curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

# 消息模板
class MqttMsgDC:

    # dc充电启动状态
    def publish_dc_starting(self, cif=1, tradeID=0, orderID="", vin="", type=0, state=0, reason='', errcode="",
                            bhmMaxAllowVol=0.0, batType=3, maxAllowTemp=0, maxAllowVol=0.0, cellMaxAllowVol=0.0,
                            maxAllowCur=0.0, ratedVol=0.0, batVol=0.0, ratedAH=0.0, ratedKWh=0.0, batSOC=0.0,
                            bmsPVer=None,
                            batVendor=None, batNo=0, batDate=None, batChaTimes=0, batProperty=0, bmsSoftVer=None,
                            maxOutVol=0.0, minOutVol=0.0, maxOutCur=0.0, minOutCur=0.0):
        """
        直流桩启动状态
        :param cif:充电接口编号
                1：A 枪
                2：B 枪
                依此类推
        :param tradeID:交易流水号，10位十进制整数
        :param orderID:订单ID，20字符
        :param vin:车辆VIN，17字符
        :param type:本次启动充电类型
                0：小鹏汽车插抢启动充电
                1：远程启动充电
                2：小鹏汽车自恢复启动充电
                99：未知
        :param state:状态
                0：开始启动
                1：车辆辨识（识别车辆，鉴定是否小鹏汽车）
                2：充电自检（电池电压检测、接触器粘连检测、绝缘检测等）
                3：车辆握手
                4：车辆充电参数配置（预允电）
                5：进入充电状态
                255：启动失败
        :param reason:启动失败原因，当$state:255 时：填充对应的启动失败原因，其它情况填充 0 或不上传此字段
        :param errcode:启动失败时对应的故障编码列表，当$state:255 时：若为故障导致启动失败，填充对应的故障编码，其它情况置为空或不上传此字段若有多个故障编码，则以分号为间隔；
        :param bhmMaxAllowVol:BMS 最高允许充电总电压(取 BHM SPN2601 数据项值)，充电桩收到 BHM 后开始上传；未收到 BHM 不上传此字段
                0.0 V~950.0 V  保留 1 位小数
        :param batType:电池类型。当$state:5 时上传
                电池类型：
                01H： 铅酸电池；
                02H： 镍氢电池；
                03H： 磷酸铁锂电池；
                04H： 锰酸锂电池；
                05H： 钴酸锂电池；
                06H： 三元材料电池；
                07H： 聚合物锂离子电池；
                08H： 钛酸锂电池；
                FFH： 其他电池。
        :param maxAllowTemp:BMS 最高允许温度。当$state:5 时上传
                数据分辨率： 1ºC/位， -50 ºC 偏移量； 数据范围：-50ºC~+200 ºC；
        :param maxAllowVol:
        :param cellMaxAllowVol:
        :param maxAllowCur:
        :param ratedVol:
        :param batVol:
        :param ratedAH:
        :param ratedKWh:
        :param batSOC:
        :param bmsPVer:
        :param batVendor:
        :param batNo:
        :param batDate:
        :param batChaTimes:
        :param batProperty:
        :param bmsSoftVer:
        :param maxOutVol:
        :param minOutVol:
        :param maxOutCur:
        :param minOutCur:
        :return:
        """
        message = {"msg": "starting", "cif": cif, "tradeID": tradeID, "orderID": orderID, "vin": vin, "type": type,
                   "state": state, "reason": reason, "errcode": errcode, "bhmMaxAllowVol": bhmMaxAllowVol,
                   "batType": batType, "maxAllowTemp": maxAllowTemp, "maxAllowVol": maxAllowVol,
                   "cellMaxAllowVol": cellMaxAllowVol, "maxAllowCur": maxAllowCur, "ratedVol": ratedVol,
                   "batVol": batVol,
                   "ratedAH": ratedAH, "ratedKWh": ratedKWh, "batSOC": batSOC, "bmsPVer": bmsPVer,
                   "batVendor": batVendor,
                   "batNo": batNo, "batDate": batDate, "batChaTimes": batChaTimes, "batProperty": batProperty,
                   "bmsSoftVer": bmsSoftVer, "maxOutVol": maxOutVol, "minOutVol": minOutVol, "maxOutCur": maxOutCur,
                   "minOutCur": minOutCur}

        json_msg = json.dumps(message)
        return json_msg

    # 车辆验证请求
    def publish_carchk(self, cif=1, vin="", psuID="", psuAuthRes=99,vsrc=1, mfrs='', pwd=''):
        """
        车辆鉴权，vin或psu
        :param cif: 充电接口编号
                1：A 枪
                2：B 枪
                依此类推
        :param vin: 车辆VIN，17字符
        :param psuID
        :param psuAuthRes
        :param vsrc: 车辆来源
                0：小鹏汽车
                1：其他
        :param mfrs: 车辆制造商
        :param pwd: 车辆密码
        :return:
        """
        message = {"msg": "carChk", "cif": cif, "vin": vin, "psuID":psuID,"psuAuthRe":psuAuthRes, "vsrc": vsrc,"mfrs": mfrs, "pwd": pwd}
        # message = {"msg":"carChk","cif":$cif,"vin":vin,"psuID":psuID,"psuAuthRe":psuAuthRes}

        json_msg = json.dumps(message)
        return json_msg

    # 结束充电
    def publish_chargend(self, cif=1, tradeID=2007232732, orderID="20200723150109564439", vin="LMVHFEFZXKA666495",
                         t1="0",
                         t2="20200723150104", t3="20200723150142", t4="20200723161738", energy=28.81, energy1=0.0,
                         energy2=0.0, energy3=28.81, energy4=0.0, secEnergy=0.03, secEnergy1=0.0, secEnergy2=0.0,
                         secEnergy3=0.03, secEnergy4=0.0, time=75, time1=40, time2=30, time3=5, beginSoC=37, endSoC=95,
                         csr=114, errCode=""):
        """
        充电结束
        :param errCode:
        :param cif: 充电接口编号
                1：A 枪
                2：B 枪
                依此类推
        :param tradeID:
        :param orderID:
        :param vin:
        :param t1:
        :param t2:
        :param t3:
        :param t4:
        :param energy:
        :param energy1:
        :param energy2:
        :param energy3:
        :param energy4:
        :param secEnergy:
        :param secEnergy1:
        :param secEnergy2:
        :param secEnergy3:
        :param secEnergy4:
        :param time:
        :param time1:
        :param time2:
        :param time3:
        :param beginSoC:
        :param endSoC:
        :param csr:
        :return:
        """
        message = {"msg": "chargEnd", "cif": cif, "tradeID": tradeID, "orderID": orderID, "vin": vin, "t1": t1,
                   "t2": t2,
                   "t3": t3, "t4": t4, "energy": energy, "energy1": energy1, "energy2": energy2, "energy3": energy3,
                   "energy4": energy4, "secEnergy": secEnergy, "secEnergy1": secEnergy1, "secEnergy2": secEnergy2,
                   "secEnergy3": secEnergy3, "secEnergy4": secEnergy4, "time": time, "time1": time1, "time2": time2,
                   "time3": time3, "beginSoC": beginSoC, "endSoC": endSoC, "csr": csr, "errCode": errCode,
                   "energyDetail": []}

        json_msg = json.dumps(message)
        return json_msg

    # 充电交易上传
    def publish_trade(self, cif=1, tradeID=2007232732, orderID="20200723150109564439", vin="LMVHFEFZXKA666495", t1="0",
                      t2="20200723150104", t3="20200723150142", t4="20200723161738", t5="20200723162344", t6="0",
                      energy=28.81, energy1=0.0, energy2=0.0, energy3=28.81, energy4=0.0, secEnergy=0.03,
                      secEnergy1=0.0,
                      secEnergy2=0.0, secEnergy3=0.03, secEnergy4=0.0, time=75, time1=40, time2=30, time3=5,
                      beginSoC=37,
                      endSoC=95, csr=114, errCode=""):
        """
        实时订单
        :param cif:充电接口编号
                1：A 枪
                2：B 枪
                依此类推
        :param tradeID:
        :param orderID:
        :param vin:
        :param t1:
        :param t2:
        :param t3:
        :param t4:
        :param t5:
        :param t6:
        :param energy:
        :param energy1:
        :param energy2:
        :param energy3:
        :param energy4:
        :param secEnergy:
        :param secEnergy1:
        :param secEnergy2:
        :param secEnergy3:
        :param secEnergy4:
        :param time:
        :param time1:
        :param time2:
        :param time3:
        :param beginSoC:
        :param endSoC:
        :param csr:
        :param errCode:
        :return:
        """
        message = {"msg": "trade", "cif": cif, "tradeID": tradeID, "orderID": orderID, "vin": vin, "t1": t1, "t2": t2,
                   "t3": t3, "t4": t4, "t5": t5, "t6": t6, "energy": energy, "energy1": energy1, "energy2": energy2,
                   "energy3": energy3, "energy4": energy4, "secEnergy": secEnergy, "secEnergy1": secEnergy1,
                   "secEnergy2": secEnergy2, "secEnergy3": secEnergy3, "secEnergy4": secEnergy4, "time": time,
                   "time1": time1, "time2": time2, "time3": time3, "beginSoC": beginSoC, "endSoC": endSoC, "csr": csr,
                   "errCode": errCode, "energyDetail": []}
        json_msg = json.dumps(message)
        return json_msg

    # 遥信数据
    def publish_yx(self, cif=1, status=0, time="", error=0, errcode="0", alarm=0, alarm1=0, alarm2=0, alarm3=0,
                   alarm4=0, alarm5=0, alarm6=0, alarm7=0, alarm8=0, yx1=0, yx2=0, yx3=0, yx4=0, yx5=0, yx6=0, yx7=0,
                   yx8=0,
                   yx9=0, yx10=1, rssi=31, linkType=0, link4g=1, linkWifi=99, linkEth=99, simId=1):
        """
        遥信，默认30s发送一次
        :param cif:
        :param status: 0 待机，1 工作(充电中/充电停止中/先扫码等待插枪)，2 充电完成，3 充电暂停，4 充电预约，5 启动失败，99 充电服务暂停
        :param time:
        :param error: 0 正常，1 故障
        :param errcode:
        :param alarm:
        :param alarm1:
        :param alarm2:
        :param alarm3:
        :param alarm4:
        :param alarm5:
        :param alarm6:
        :param alarm7:
        :param alarm8:
        :param yx1:
        :param yx2:
        :param yx3:
        :param yx4:
        :param yx5:
        :param yx6:
        :param yx7:
        :param yx8:
        :param yx9:
        :param rssi:
        :param linkType:
        :return:
        """
        message = {
            "msg": "yx", "cif": cif, "status": status, "time": time, "error": error, "errcode": errcode,
            "alarm": alarm, "alarm1": alarm1, "alarm2": alarm2, "alarm3": alarm3, "alarm4": alarm4, "yx1": yx1,
            "yx2": yx2, "yx3": yx3, "yx4": yx4, "yx5": yx5, "yx6": yx6, "yx7": yx7, "yx8": yx8, "yx9": yx9,
            "yx10": yx10, "rssi": rssi
        }

        json_msg = json.dumps(message)
        return json_msg

    # 离线交易上传
    def publish_ol_trade(self, cif=1, tradeID=2021112201, orderID="", vin="XPENGE28PANYJ0002",
                         t1="0",
                         t2="20200815200718", t3="20200815200719", t4="20200815211115", t5="20200815211215", t6="0",
                         energy=0, energy1=0.0, energy2=0.0, energy3=20.0, energy4=0.0, time=60, beginSoC=20,
                         endSoC=85, csr=114, errCode=""):
        """

        :param cif:
        :param tradeID:
        :param orderID:
        :param vin:
        :param t1:
        :param t2:
        :param t3:
        :param t4:
        :param t5:
        :param t6:
        :param energy:
        :param energy1:
        :param energy2:
        :param energy3:
        :param energy4:
        :param time:
        :param beginSoC:
        :param endSoC:
        :param csr:
        :param errCode:
        :return:
        """
        message = {"msg": "olTrade", "cif": cif, "tradeID": tradeID, "orderID": orderID, "vin": vin, "t1": t1, "t2": t2,
                   "t3": t3, "t4": t4, "t5": t5, "t6": t6, "energy": energy, "energy1": energy1, "energy2": energy2,
                   "energy3": energy3, "energy4": energy4, "time": time, "beginSoC": beginSoC, "endSoC": endSoC,
                   "csr": csr,
                   "errCode": errCode, "energyDetail": []}
        json_msg = json.dumps(message)
        return json_msg

    # bootNotification
    def publish_bootNoti(self, p_ver=100, p1_ver=12, type=1, vendor="EN+", loadMode=0, s_ver=100898, s_ver1=101002,
                         s_ver2=101003, h_ver=100000,
                         h_ver1=16,
                         h_ver2=16, psu_h_ver=100000, psu_s_ver=100000, blistID=0, imei="000000", iccid="000000"):
        """

        :param p_ver: 运营平台与充电桩通信协议版本
        :param type: 0：直流，1：交流
        :param vendor: 供应商
        :param loadMode: 文件上传/下载方式，0：支持 HTTP(S)，1：支持 FTP(S)
        :param s_ver: 充电桩固件版本，交流桩用，记录到a_equip表的ver字段
        :param s_ver1: 充电桩固件版本，直流桩用，记录到a_equip表的ver字段
        :param s_ver2: 充电主机固件版本，直流桩才会带
        :param h_ver: 充电桩硬件版本，交流桩用
        :param h_ver1: 充电桩硬件版本，直流桩用
        :param h_ver2: 充电主机硬件版本，直流桩用
        :param psu_h_ver: PSU 硬件版本
        :param psu_s_ver: PSU 软件版本
        :param blistID: 黑名单 ID
        :param imei:
        :param iccid:
        """

        message = {}
        message['msg'] = "bootNoti"
        message['p_ver'] = p_ver
        message['type'] = type
        message['vendor'] = vendor
        message['loadMode'] = loadMode
        if type == 0:
            message['p1_ver'] = p1_ver
            message['s_ver1'] = s_ver1
            message['s_ver2'] = s_ver2
            message['h_ver1'] = h_ver1
            message['h_ver2'] = h_ver2
        elif type == 1:
            message['s_ver'] = s_ver
            message['h_ver'] = h_ver
        message['psu_h_ver'] = psu_h_ver
        message['psu_s_ver'] = psu_s_ver
        message['blistID'] = blistID
        message['imei'] = imei
        message['iccid'] = iccid

        json_msg = json.dumps(message)
        return json_msg

    # 遥信数据 - 采集数据
    def publish_ycAnalog(self, a_vol=226.0, b_vol=0.0, c_vol=0.0, a_cur=0.0, b_cur=0.0, c_cur=0.0, power=0.0,
                         connVol=0.0, dutyCycle=0.0, devTemp=36.0, cifTemp1=-50.0, cifTemp2=-50.0, cifTemp3=-50.0,
                         cifTemp4=-50.0):

        msg = {"msg": "ycAnalog", "cif": 1, "a_vol": a_vol, "b_vol": b_vol, "c_vol": c_vol, "a_cur": a_cur,
               "b_cur": b_cur,
               "c_cur": c_cur, "power": power, "connVol": connVol, "dutyCycle": dutyCycle, "devTemp": devTemp,
               "cifTemp1": cifTemp1,
               "cifTemp2": cifTemp2, "cifTemp3": cifTemp3, "cifTemp4": cifTemp4}

        json_msg = json.dumps(msg)
        return json_msg

    # 遥信数据 - 计量数据
    def publish_ycMeas(self, tradeID, t2, time, energy=20.134, energy1=0, energy2=0, energy3=20.134, energy4=0,
                       secEnergy=0, secEnergy1=0, secEnergy2=0, secEnergy3=0, secEnergy4=0, meterEnergy=336061.6,
                       acMeterEnergy=805742.44):
        msg = {"msg": "ycMeas", "tradeID": tradeID, "t2": t2, "time": time,
               "energy": energy, "energy1": energy1, "energy2": energy2, "energy3": energy3, "energy4": energy4,
               "secEnergy": secEnergy, "secEnergy1": secEnergy1, "secEnergy2": secEnergy2, "secEnergy3": secEnergy3,
               "secEnergy4": secEnergy4,
               "meterEnergy": meterEnergy, "acMeterEnergy": acMeterEnergy
               }
        json_msg = json.dumps(msg)
        return json_msg

    # 遥信数据 - BMS数据
    def publish_ycBMS(self, cif=1, tradeID=2305171224, r_vol=427.6, r_cur=-250.0, mode=2, soc=11, remainTime=72,
                      cellMaxVol=3.50, minTemp=28, maxTemp=29, m_vol=336.1, m_cur=-2.7,
                      soc1=None, cdFlag=None):
        """
        BMS 数据上报
        :param soc1: 协议 v1.19 新增，SOC1 值，传入时包含在 JSON 中，不传时不包含
        :param cdFlag: 协议 v1.19 新增，充检标志，传入时包含在 JSON 中，不传时不包含
                       2 表示 BMS 支持充检
        """
        msg = {"msg": "ycBMS", "cif": cif, "tradeID": tradeID, "r_vol": r_vol, "r_cur": r_cur, "mode": mode, "soc": soc,
               "remainTime": remainTime, "cellMaxVol": cellMaxVol, "minTemp": minTemp, "maxTemp": maxTemp,
               "m_vol": m_vol, "m_cur": m_cur}
        if soc1 is not None:
            msg["soc1"] = soc1
        if cdFlag is not None:
            msg["cdFlag"] = cdFlag
        json_msg = json.dumps(msg)
        return json_msg

    # 桩属性数据消息
    def publish_pileProp(self, vendor="XPENG", ratedPower=360.0, maxOutVol=1000.0,
                         minOutVol=200.0, maxOutCur=800.0, minOutCur=1.0, cdEn=1):
        """
        桩属性数据消息，包含 dev 对象
        :param vendor: 供应商
        :param ratedPower: 额定功率
        :param maxOutVol: 最大输出电压
        :param minOutVol: 最小输出电压
        :param maxOutCur: 最大输出电流
        :param minOutCur: 最小输出电流
        :param cdEn: 充检使能，1 表示桩支持充检
        """
        msg = {"msg": "pileProp",
               "dev": {
                   "vendor": vendor, "ratedPower": ratedPower,
                   "maxOutVol": maxOutVol, "minOutVol": minOutVol,
                   "maxOutCur": maxOutCur, "minOutCur": minOutCur,
                   "cdEn": cdEn
               }}
        json_msg = json.dumps(msg)
        return json_msg

    # 电池充检进度消息
    def publish_cdProgress(self, cif=1, id="", type=1, state=1,
                           tradeID=None, vin=None, beginTime=None, endTime=None,
                           bp_r_cur=None, beginSoC=None, endSoC=None,
                           errcode=None, errmsg=None):
        """
        电池充检进度/状态消息（协议 v1.19 新增）
        :param cif: 充电接口编号
        :param id: 充检 ID，格式如 CJ{YYMMDDHHmmss}{随机6位数字}
        :param type: 充检类型
        :param state: 充检状态
                1：待检测
                2/3/4：检测中
                100：检测完成或取消
        :param tradeID: 交易流水号，state=100 时包含
        :param vin: 车辆 VIN，state=100 时包含
        :param beginTime: 充检开始时间，state=100 时包含
        :param endTime: 充检结束时间，state=100 时包含
        :param bp_r_cur: 充检电流，state=100 时包含
        :param beginSoC: 开始 SOC，state=100 时包含
        :param endSoC: 结束 SOC，state=100 时包含
        :param errcode: 错误码，state=100 时包含（0=成功）
        :param errmsg: 错误信息，state=100 时包含
        """
        msg = {"msg": "cdProgress", "cif": cif, "id": id, "type": type, "state": state}
        if state == 100:
            if tradeID is not None:
                msg["tradeID"] = tradeID
            if vin is not None:
                msg["vin"] = vin
            if beginTime is not None:
                msg["beginTime"] = beginTime
            if endTime is not None:
                msg["endTime"] = endTime
            if bp_r_cur is not None:
                msg["bp_r_cur"] = bp_r_cur
            if beginSoC is not None:
                msg["beginSoC"] = beginSoC
            if endSoC is not None:
                msg["endSoC"] = endSoC
            if errcode is not None:
                msg["errcode"] = errcode
            if errmsg is not None:
                msg["errmsg"] = errmsg
        json_msg = json.dumps(msg)
        return json_msg





