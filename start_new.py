import threading
import curses
import queue
import signal
import time
import can
import datetime
import re
from flask import Flask
from flask import request
from flask import redirect
from flask import url_for
from flask import render_template
from curses import wrapper

import logging
from logging.handlers import RotatingFileHandler

import os.path
import shutil

from flask_socketio import SocketIO#, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
from builtins import str

outStr = ""

def outStr_add(value):
    global outStr
    outStr += value

def mergeList(lista):
    out_list = []
    index = 0
    for item in lista:
        out_list.append(item[index])
        index += 1
    return [out_list]

def _formatLine(content):
    if(len(content)>1):
        local_str = "{:20s}{:16s}{:25s}{:9s}{:30s}".format(content[0],content[1],content[2],content[3],content[4])
    else:
        local_str = content[0]
    return local_str

def _td(content, colspan, tag_class, tag_id):
    local_str = "<td"
    if(colspan != ""):
        local_str +=  " colspan=\""+colspan+"\""
    if(tag_class != ""):
        local_str += " class=\""+tag_class+"\""
    if(tag_id != ""):
        local_str += " id=\""+tag_id+"\""
    local_str += ">"+content+"</td>\n"
    return local_str

def _tr(serial,tableSize,tag_class,tag_id):
    colspan = tableSize - len(serial) + 1
    local_str = "<tr>\n"
    for item in serial:
        local_str += _td(item,str(colspan),tag_class+"_td","")
        colspan = 0
    local_str += "</tr>\n"
    return local_str

def _table(content, title,dataType_input,tablezise,tag_class_input, tag_id_input):
    str = ""
    tag_class = "table_"+tag_class_input.replace(' ', '_').lower()
    tag_id    = "table_"+tag_class_input.replace(' ', '_').lower()
    dataType  = "table_"+tag_class_input.replace(' ', '_').lower()
    if(len(content) > 0):
        if(len(title)>0):
            str += "<p tag_class=\""+tag_class+"\" tag_id=\""+tag_id+"\" name=\"title_generateListOfSignals\">List of "+title+":</p>\n"#+data[0]+"\n"
        str += "<table class = \""+tag_class+"\" name=\"list_generateListOfSignals_"+dataType+"\">\n"
        for item in content:
            str += _tr(item,tablezise,tag_class+"_tr","")
        str += "</table>\n"
    return str

def _div_toggled(name,content_a,content_b,short_data,toggle,notitle):
    p_name = "titile_"+name.replace(' ', '_').lower()+""
    p_id = "titile_"+name.replace(' ', '_').lower()+""
    p_class = "titile_"+name.replace(' ', '_').lower()+""
    div1_name = "node_"+name.replace(' ', '_').lower()+""
    div1_id = "node_"+name.replace(' ', '_').lower()+""
    div1_class = "node_"+name.replace(' ', '_').lower()+""
    div2_name = "node_"+name.replace(' ', '_').lower()+"_small"
    div2_id = "node_"+name.replace(' ', '_').lower()+"_small"
    div2_class = "node_"+name.replace(' ', '_').lower()+"_small"
    
    if(1 == toggle):
        script = "$('#"+div1_id+"').show();\n"
        script += "$('#"+div2_id+"').hide();\n"
    else:
        script = "$('#"+div1_id+"').hide();\n"
        script += "$('#"+div2_id+"').show();\n"

    script += "$('#"+div1_id+"').click(function() {\n$('#"+div1_id+"').hide('slow');\n$('#"+div2_id+"').show('fast');\nreturn false;\n});\n\n"
    script += "$('#"+div2_id+"').click(function() {\n$('#"+div1_id+"').show('slow');\n$('#"+div2_id+"').hide('fast');\nreturn false;\n});\n\n"
    
    str  = "<div id=\""+div1_id+"\" name=\""+div1_name+"\">\n"
    if(1 == notitle):
        str += "<p class=\""+p_class+"\" name=\""+p_name+"\">"+name+"</p>\n"
    str += "<div class=\"div_inner\">\n"
    str += content_a
    str += "</div>\n"
    str += "</div>\n"
    
    str += "<div id=\""+div2_id+"\" name=\""+div2_name+"\">\n"
    if(1 == notitle):
        str += "<div class=\"div_title_short\">\n"
        str += "<p class=\""+p_class+"\" name=\""+p_name+"\">"+name+"</p>"
        #short_data[0].insert(0, loca)
        if(len(short_data) > 0):
            size = len(short_data[0][0])
        else:
            size = 1
        str += _table(short_data, "", "x", size, "table_title_short","")
        str += "</div>\n"
    if(content_b != ""):
        str += "<div class=\"div_inner\">\n"
        str += content_b
        str += "</div>\n"
    str += "</div>\n"

    return [str, script]     

listOfPages = []
listOfNodes = []
listOfDevices = []

deviceNameList = {0x0000:'RTC-Nixie',0x1000:'rTC-Storczyki',0x1001:'rTC-Akwarium',0x2100:'PM-Meter',0x2000:'Salon-Nixie',0x4000:'Nixie-Display',0x2001:'Storczyki',0x2002:'Balkon',0x2003:'Chomik',0x2004:'Akwarium'}

log = logging.getLogger('werkzeug')
log.setLevel(logging.DEBUG)
file_handler = RotatingFileHandler('app.run.log', maxBytes=10000000, backupCount=5)
log.addHandler(file_handler)
formatter = logging.Formatter("[%(asctime)s] %(message)s -- {%(pathname)s:%(lineno)d} %(levelname)s")
file_handler.setFormatter(formatter)
app = Flask(__name__)
app.config['SECRET_KEY'] = 'onomatopeja!'
socketio = SocketIO(app)

class CANframe (object):
    def __init__(self,msg):
        self.multiplexedList = [0x02002000, 0x02002100, 0x02002001, 0x02002002, 0x02002003, 0x02002004]
        self.frameName = ['Default frame']
        self.frameNameLevel = 0
        self.id = msg.arbitration_id
        self.deviceName = deviceNameList.get(0x0000FFFF & self.id,"xxx")  
        self.dlc = msg.dlc
        self.data = []
        self.frameType = ""
        self.dataStr_A = ""
        self.dataStr_B = ""
        for i in range(0,self.dlc): 
            self.data.append(msg.data[i])
        self.timestamp = msg.timestamp
        self.timestampStr = datetime.datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        if(self.checkMultiplexed()):
            self.multiplexed = self.data[0]
        else:
            self.multiplexed = -1
    def __lt__(self, other):
        return ((self.id < other.id) or (self.id == other.id and self.multiplexed < other.multiplexed))
    def getId(self):
        return self.id
    def getFrameType(self):
        return (self.id & 0x7F000000)
    def getFrameName(self,level):
        if(level > self.frameNameLevel):
            level = self.frameNameLevel
        return self.frameName[level]
    def getMultiplexed(self):
        return self.multiplexed
    def checkMultiplexed(self):
        return self.multiplexedList.count(self.id)
    def dataStr(self):
        return ' '.join("%02x" % b for b in self.data)
    def calculateValue(self,dataShow):
        self.frameType = self.frameName[self.frameNameLevel]
        self.dataStr_A = "{:08x} {:02x}".format(self.id, self.dlc)
        self.dataStr_B = self.dataStr() #self.multiplexedStr()+" "+
    def multiplexedStr(self):
        if(-1 == self.multiplexed):
            return '  '
        else:
            return '{mul:2d}'.format(mul = self.multiplexed)
    def outputData(self):
        return ["ABC"]
    def serializeData(self,dataShow):
        self.calculateValue(dataShow)
        if(dataShow < 2):
            data = [self.timestampStr, self.deviceName, self.frameType, self.dataStr_A, self.dataStr_B]
        else:
            data = self.outputData()
        return data
    

class NM_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('NM frame')
        self.frameNameLevel += 1
      
class Sensor_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Sensor frame')
        self.frameNameLevel += 1

class Actuator_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Actuator frame')
        self.frameNameLevel += 1

class ERROR_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('ERROR frame')
        self.frameNameLevel += 1

class Display_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Display frame')
        self.frameNameLevel += 1

class ConfREQ_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Config request frame')
        self.frameNameLevel += 1
        
class ConfRES_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Config response frame')
        self.frameNameLevel += 1
        
class DiagREQ_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Diag request frame')
        self.frameNameLevel += 1
        
class DiagRES_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Diag response frame')
        self.frameNameLevel += 1
        
class BootREQ_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Boot request frame')
        self.frameNameLevel += 1
        
class BootRES_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Boot response frame')
        self.frameNameLevel += 1

class Critical_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName.append('Boot response frame')
        self.frameNameLevel += 1

class EnvironmentSensor_CANframe(Sensor_CANframe):
    def __init__(self,msg):
        Sensor_CANframe.__init__(self,msg)
        self.frameName.append('Environment Sensor frame')
        self.frameNameLevel += 1
        self.multiplexedValues = {0:'Humidity', 1:'Temperature (hum)', 2:'Pressure', 3:'Temperature (press)'}
        self.multiplexedType = {0:'%', 1:'\xb0C',2:'hPa',3:'\xb0C'}
        self.value = 0.
        self.outputDataValues = ["","","","","",""]
    def calculateValue(self,dataShow):
        if(dataShow == 1):
            value = ((self.data[4])+(self.data[3]<<8)+(self.data[2]<<16))
            if value & 0x800000:
                value = 0xFF000000 | value
                value = 0xFFFFFFFF - value
                value += 1
                value = -1*value
            self.value = value/100.
            self.dataStr_A =  "{:.1f}".format(self.value)
            self.getValueName()
            self.outputDataValues[self.getMultiplexed()] = self.dataStr_A+""+self.dataStr_B+"  "
        else:
            Sensor_CANframe.calculateValue(self,dataShow)
    def getValueName(self):
        if(self.getMultiplexed() < 4):
            self.frameType = self.multiplexedValues.get(self.getMultiplexed(),"???")
            self.dataStr_B = self.multiplexedType.get(self.getMultiplexed(),"???")
        else:
            self.frameType = "Temperature"
            self.dataStr_B = "\xb0C"
    def outputData(self):
        return self.outputDataValues
    
class PMSensor_CANframe(Sensor_CANframe):
    def __init__(self,msg):
        Sensor_CANframe.__init__(self,msg)
        self.frameName.append('PM Sensor frame')
        self.frameNameLevel += 1
        self.multiplexedValues = {0:'Time', 1:'PMS3003 PM 1.0', 2:'PMS3003 PM 2.5', 3:'PMS3003 PM 10', 4:'GP2Y10 PM 1.0-10.0'}
        self.multiplexedType = {0:'', 1:'ug/m3',2:'ug/m3',3:'ug/m3',4:'ug/m3'}    
        self.dataStr_A = "00:00:00"
        self.dataStr_B = "Poniedzialek, 00. Styczen 1900"  
        self.frameType = self.multiplexedValues.get(self.getMultiplexed(),'???')
    def calculateValue(self,dataShow):
        if(dataShow == 1):
            if(self.getMultiplexed() == 0):
                self.dataStr_A = "{:02x}:{:02x}:{:02x}".format(self.data[1],self.data[2],self.data[3])
                self.dataStr_B = "{:s}, {:02x}. {:s} 20{:02x}".format(getDay(self.data[4]),self.data[5],getMonth(self.data[6]),self.data[7])
            elif(self.getMultiplexed() < 4):
                self.dataStr_A = ((self.data[4])+(self.data[3]<<8))
            elif(self.getMultiplexed() == 4):
                self.dataStr_A = ((self.data[2])+(self.data[1]<<8))
        else:
            Sensor_CANframe.calculateValue(self,dataShow)
    
class RTC_CANframe(Sensor_CANframe):
    def __init__(self,msg):
        Sensor_CANframe.__init__(self,msg)
        self.frameName.append('RTC on CAN')
        self.frameNameLevel += 1
        self.dataStr_A = "00:00:00"
        self.dataStr_B = "Poniedzialek, 00. Styczen 1900"
        self.frameType = "Time"
        self.outputDataValues = [""]
    def calculateValue(self,dataShow):
        if(dataShow == 1):
            self.dataStr_A = "{:02x}:{:02x}:{:02x}".format(self.data[0],self.data[1],self.data[2])
            self.dataStr_B = "{:s}, {:02x}. {:s} 20{:02x}".format(getDay(self.data[4]),self.data[5],getMonth(self.data[6]),self.data[7])
            self.outputDataValues[0] = self.dataStr_A+" "+self.dataStr_B
        else:
            Sensor_CANframe.calculateValue(self,dataShow)
    def outputData(self):
        return self.outputDataValues

class RTCrelay_CANframe(Sensor_CANframe):
    def __init__(self,msg):
        Sensor_CANframe.__init__(self,msg)
        self.frameName.append('Relay on CAN')
        self.frameNameLevel += 1
        self.dataStr_A = "00:00:00"
        self.dataStr_B = "Poniedzialek, 00. Styczen 1900"
        self.frameType = "Time"
        self.outputDataValues = [""]
    def calculateValue(self,dataShow):
        if(dataShow == 1):
            self.dataStr_A = "{:02x}:{:02x}:{:02x}".format(self.data[1],self.data[2],self.data[3])
            self.dataStr_B = "{:s}, {:02x}. {:s} 20{:02x}".format(getDay(self.data[4]),self.data[5],getMonth(self.data[6]),self.data[7])
            self.outputDataValues[0] = self.dataStr_A+" "+self.dataStr_B
        else:
            Sensor_CANframe.calculateValue(self,dataShow)
    def outputData(self):
        return self.outputDataValues
    
def getDay(value):
    weekdays = {7:'Niedziela',1:'Poniedzialek',2:'Wtorek',3:'Sroda',4:'Czwartek',5:'Piatek',6:'Sobota'}
    return weekdays.get(value,'?weekday?') 
    
def getMonth(value):
    months = {0x01:'Styczen',0x02:'Luty',0x03:'Marzec',0x04:'Kwiecien',0x05:'Maj',0x06:'Czerwiec',0x07:'Lipiec',0x08:'Sierpien',0x09:'Wrzesien',0x10:'Pazdziernik',0x11:'Listopad',0x12:'Grudzien'}
    return months.get(value,'?month?') 

class windowManagement (threading.Thread):
    def __init__(self,run_event,queueData,queueButton,msgList,msgListLock):
        threading.Thread.__init__(self)
        self.window = curses.initscr()
        self.window.nodelay(1)
        (self.h, self.w) = self.window.getmaxyx()
        curses.noecho()
        self.queueButton = queueButton
        self.dataSetDisplay = 0x31
        self.run_event = run_event
        self.msgList = msgList 
        self.msgListLock = msgListLock 
    def __del__(self):
        pass
    def run(self):
        while self.run_event.is_set():
            key_char = self.window.getch()
            if(-1 != key_char):
                self.dataSetDisplay = key_char
            if(not self.queueButton.empty()):
                self.dataSetDisplay = self.queueButton.get()
            if(0x31 == self.dataSetDisplay):
                self.listData(1)
            else:
                self.listData(0)
            
            pass
        self.window.refresh()
    def listData(self, show):
        with self.msgListLock:
            j = 0
            self.msgList.sort()
            for item in self.msgList:
                if(j < self.h):
                    self.window.addstr(j,0,_formatLine(item.serializeData(show)))
                    j += 1
        self.window.refresh()            

class canEngine (threading.Thread):
    def __init__(self,run_event,queueReceived,queueSend):
        threading.Thread.__init__(self)
        self.msgBuffer_receiver = queueReceived
        self.msgBuffer_sender = queueSend
        self.run_event = run_event
        self.bus = can.interface.Bus(channel='can0', bustype='socketcan_native')
        
    def run(self):
        while self.run_event.is_set():
            if(not self.msgBuffer_sender.empty()):
                self.bus.send(self.msgBuffer_sender.get())
            msg = self.bus.recv()
            if msg is None:
                pass
            else:
                self.msgBuffer_receiver.put(msg)
            
                
class manageCAN (threading.Thread):
    def __init__(self,run_event,queueReceived,queuesSend,msgList,msgListLock):
        threading.Thread.__init__(self)        
        self.queue = queueReceived
        self.msgBuffer = queuesSend
        self.run_event = run_event
        self.msgList = msgList 
        self.msgListLock = msgListLock 
        
        #self.bus = can.interface.Bus(channel='can0', bustype='socketcan_native')
        self.ConfigReqResponseByte = 0xFF
        self.ConfigReqResponseID = 0xFFFF
        self.ConfigReqResponseCount = 0x00
        self.ConfigReqList = []
        
    def run(self):
        while self.run_event.is_set():
        #    if(not self.msgBuffer.empty()):
        #        self.bus.send(self.msgBuffer.get())
        #    msg = self.bus.recv()
            if(not self.queue.empty()):
                msg = self.queue.get() 
                for item in mainPage.listOfDevices:
                    item.updateMessageList(msg)
                if((msg.arbitration_id & 0x1FFF0000) == 0x10FF0000):
                    p = NM_CANframe(msg)
                elif((msg.arbitration_id & 0x1FFF0000) == 0x02000000):
                    if((msg.arbitration_id & 0x0000FF00) == 0x00002000):
                        p = EnvironmentSensor_CANframe(msg)
                    elif((msg.arbitration_id & 0x0000FF00) == 0x00002100):
                        p = PMSensor_CANframe(msg)
                    elif((msg.arbitration_id & 0x0000FF00) == 0x00000000):
                        p = RTC_CANframe(msg)
                    elif((msg.arbitration_id & 0x0000FF00) == 0x00001000):
                        p = RTCrelay_CANframe(msg)
                    else:
                        p = Sensor_CANframe(msg)   
                elif((msg.arbitration_id & 0x1FFF0000) == 0x05000000):
                    if((msg.arbitration_id & 0x0000FFFF) == self.ConfigReqResponseID  and msg.data[0] == self.ConfigReqResponseByte):
                        if(self.ConfigReqResponseCount > 0):
                            self.ConfigReqResponseCount -= 1
                            self.ConfigReqList.append(msg)
                        else:
                            self.ConfigReqResponseID = 0xFFFF;
                            self.ConfigReqResponseByte = 0xFF;
                elif((msg.arbitration_id & 0x1FFF0000) == 0x04000000): 
                    p = Actuator_CANframe(msg)
                elif((msg.arbitration_id & 0x1FFF0000) == 0x10000000):
                    p = ERROR_CANframe(msg) 
                elif((msg.arbitration_id & 0x1FFF0000) == 0x06000000):
                    p = Display_CANframe(msg)  
                elif((msg.arbitration_id & 0x1FFF0000) == 0x08000000):
                    p = ConfREQ_CANframe(msg) 
                elif((msg.arbitration_id & 0x1FFF0000) == 0x09000000):
                    p = ConfRES_CANframe(msg)
                elif((msg.arbitration_id & 0x1FFF0000) == 0x0EFF0000):
                    p = DiagREQ_CANframe(msg) 
                elif((msg.arbitration_id & 0x1FFF0000) == 0x0FFF0000):
                    p = DiagRES_CANframe(msg) 
                elif((msg.arbitration_id & 0x1FFF0000) == 0x1FFF0000): 
                    p = BootREQ_CANframe(msg) 
                elif((msg.arbitration_id & 0x1FFF0000) == 0x1FF00000):
                    p = BootRES_CANframe(msg) 
                elif((msg.arbitration_id & 0x1FFF0000) == 0x00000000): 
                    p = Critical_CANframe(msg) 
                else:
                    p = CANframe(msg)
                with self.msgListLock:
                    element_found = 0
                    for item in self.msgList:
                        if(item.getId() == p.getId() and item.getMultiplexed() == p.getMultiplexed()):
                            self.msgList[self.msgList.index(item)] = p
                            element_found = 1
                            break
                    if(element_found == 0):
                        self.msgList.append(p)
                #self.queue.put(p)
    def getFilteredData(self, keyword_search, type, show):
        frName = 'all frames'
        data_out = []
        with self.msgListLock:
            for item in self.msgList:
                if((keyword_search == item.deviceName or keyword_search == '') and (item.getFrameType() == type or type == 0)):
                    data_out.append(item.serializeData(show))
                    if(type > 0):
                        frName = item.getFrameName(1) 
        return [data_out, frName]
    def getData(self,keyword_search,type):
        data_out = []
        with self.msgListLock:
            for item in self.msgList:
                if(keyword_search == item.deviceName and item.getFrameType() == type):
                    data_out.append(item.serializeData(2))
        return data_out
    def sendActuatorFrame(self, id, dataToSend):
        localmsg = can.Message(arbitration_id=(0x04000000 | id), data=dataToSend, extended_id=True)
        #self.bus.send(localmsg)
        self.msgBuffer.put(localmsg)#append(localmsg)
        return '{}'.format(localmsg)
    def sendConfigReqFrame(self, id, dataToSend, dataSize):
        returnValue = ""
        if(self.ConfigReqResponseCount == 0):
            if(dataSize != 0):
                self.ConfigReqResponseByte = dataToSend[0]
                self.ConfigReqResponseCount = dataSize
                self.ConfigReqResponseID = id
                self.ConfigReqList.clear()
            localmsg = can.Message(arbitration_id=(0x08000000 | id), data=dataToSend, extended_id=True)
            #self.bus.send(localmsg)
            self.msgBuffer.put(localmsg)#append(localmsg)
            retrunValue = '{}'.format(localmsg) 
        else:
            returnValue = "Busy. Try again."
        #for i in range(20):
        #list[0][3] = 0xFF
        return returnValue
    def configResponseReady(self):
        return self.ConfigReqResponseCount
    def getConfigReqFrame(self): 
        return self.ConfigReqList
    #def getFrameResponse(self, send_id, dataToSend, receive_id, dataLength):
        #self.sendConfigReqFrame(send_id, dataToSend)
        #return [0]
    
class pageDefinition():
    def __init__(self,title, fileName, pattern, deviceID):
        self.title = title
        self.pageFileName = fileName.lower()
        self.searchPattern = pattern
        self.deviceID = deviceID
        self.actionDefinition = []
        self.actionName = 'action_'+pattern
        self.additionalFormData = ""
        #self.deviceType = ''
        self.script = ""
        self.script = self.script + "$('input_text').click(function(event) {\n event.cancelBubble = true;\nif(event.stopPropagation) event.stopPropagation();\n \n});\n\n"
        self.responseForm = None
    def getTitle(self):
        return self.title    
    def getMainData(self):
        data = busCANThread.getData(self.searchPattern,0x02 << 8*3)
        if(len(data) > 1):
            data_out = mergeList(data)
        else:
            data_out = data
        return data_out
    def generateListOfSignalsType(self,type):
        str = ""
        data = busCANThread.getFilteredData(self.searchPattern,type,1)
        str1 = _table(data[0],data[1],self.searchPattern,5,"table_"+self.searchPattern,"table_"+self.searchPattern)
        data = busCANThread.getFilteredData(self.searchPattern,type,0)
        str2 = _table(data[0],data[1],self.searchPattern,5,"table_"+self.searchPattern+"_small","table_"+self.searchPattern+"_small")
        
        if(len(data[0])>0):
            [str, local_script] = _div_toggled("div_table"+self.searchPattern+"{:x}".format(type),str1,str2,[],1,0)
            self.script += local_script
        
        return str
    def generateListOfOther(self):
        return "<p name=\"title_generateListOfOther\">List of other possibilites:</p>\n"
    def generateListOfActions(self, oldHrefValue,otherData):
        str = ""
        if(len(self.actionDefinition) > 0):
            #self.script = self.script + "$( '#form_"+self.searchPattern+"' ).submit();\n"#function( event ) {\nevent.preventDefault(); \nevent.cancelBubble = true;\nif(event.stopPropagation) event.stopPropagation();\n alert('doing'); \n $.ajax({\ntype: \"POST\",\nurl: \"/index?Akwarium&"+oldHrefValue+"\",\ndata: $(\"#form_"+self.searchPattern+"\").serialize(),\nsuccess: function() {\nalert('send'); location.reload();\n}, error: function() { alert('errror'); }\n}); \n });\n\n" #event.preventDefault(); \nvar $form = $(this),\n url = $form.attr('action'), term = $form.find('input[name=\"s\"]').val(); var posting = $.post(url, { s: term });\n});\n\n"
            for localAction in self.actionDefinition: #$.ajax({\ntype: \"POST\",\nurl: \"index"+oldHrefValue+"\",\ndata: $(\"#form_"+self.searchPattern+"\").serialize(),\nsuccess: function(data) {\nalert(data);\n}\n});
                str = str+localAction[2]+"\n"
                self.script = self.script + "$('#button_"+localAction[0]+"').click(function(event) {\n event.cancelBubble = true;\nif(event.stopPropagation) event.stopPropagation();$( '#form_"+self.searchPattern+"' ).submit();\n \n});\n\n"
        else:
            str = "No action for this node/view."
        #str += "<BR>"+request.remote_addr+"<BR>"+request.remote_addr[:3]+"<BR>"
        if(request.remote_addr[:3] != "192"):
            str += "Authorization needed: <BR><input type=\"text\" name=\"authorization\" value=\"\" size=\"6\"><BR>"
            self.script = self.script + "$('#authorization').click(function(event) {\n event.cancelBubble = true;\nif(event.stopPropagation) event.stopPropagation();\n \n});\n\n"
        return "<p name=\"title_generateListOfActions\">List of actions:</p>\n<form action=\"index"+oldHrefValue+"\" method=\"post\" id=\"form_"+self.searchPattern+"\" >\n"+str+otherData+"</form><BR><BR>\n" #
        #return ""
    def generateListOfFooter(self):
        return ""#'<a href=\"{:s}\">Go back</a>\n<BR><BR><BR>\n'.format('index')
    #def getSchedulerPart(self):
    #    return ""
    def addResponseForm(self,values):
        self.responseForm = values
    def performAction(self):
        search = self.responseForm.get(self.actionName)
        for localListElement in self.actionDefinition:
            if(localListElement[0] == search):
                if(localListElement[3] is not None):
                    return localListElement[3](*localListElement[4])
                else:
                    return None
    def generateSubPageContent(self,hrefValue,content):
        str = ""
        #self.script = ""
        
        for i in range(0x7F):
            str = str + self.generateListOfSignalsType(i << 8*3)
        str = str + self.generateListOfActions(hrefValue,self.additionalFormData)
        str = str + self.generateListOfOther()
        str = str + self.generateListOfFooter()
        
        if self.searchPattern == "":
            name = 'index'
        else:
            name = self.searchPattern
            
        [str, local_script] = _div_toggled(name,str,"","X Y Z",content,1)
        
        self.script += local_script
        
        return str
         
    def generateScriptContent(self):
        str = self.script
        self.script = ''
        self.script = self.script + "$('.input_text').click(function(event) {\n event.cancelBubble = true;\nif(event.stopPropagation) event.stopPropagation();\n \n});\n\n"
        return str
    def addHref(self,link,description):
        return '<a href=\"{:s}\">{:s}</a>'.format(link,description)
    def addButton(self,link,description,function, arg):
        self.actionDefinition.append([link, description, '<button class=\"action_button\" name=\"{:s}\" id=\"button_{:s}\" type=\"submit\" value=\"{:s}\">{:s}</button>\n'.format(self.actionName,link,link,description),function,arg])
    def getAction(self):
        return '/index?'+self.title
    
class pageDefinition_index(pageDefinition):
    def __init__(self,title, fileName, pattern, deviceID):
        pageDefinition.__init__(self,title, fileName, pattern, deviceID)
        #self.title = 'Main page'
        #self.searchPattern = ''
    def generateListOfFooter(self):
        return '<a href=\"{:s}\">Reload</a>\n'.format('index')

class alarmList():
    def __init__(self,id,pattern):
        self.id = id
        self.numberOfAlarms = 10
        self.listOfAlarms = []
        self.script = ""
    def returnOneHTML(self, currentInput, id):
        str = "<tr><td>\n{:d}. - \n</td>".format(currentInput[0])
        str = "{:s}<td><input type=\"text\" name=\"alarm_{:d}_0\" value=\"{:02x}\" size=\"2\" class=\"input_text\"><td>-</td>\n</td>".format(str,id,currentInput[1])
        str = "{:s}<td><input type=\"text\" name=\"alarm_{:d}_1\" value=\"{:02x}\" size=\"2\" class=\"input_text\"><td>-</td>\n</td>".format(str,id,currentInput[2])
        str = "{:s}<td><input type=\"text\" name=\"alarm_{:d}_2\" value=\"{:02x}\" size=\"2\" class=\"input_text\"><td>,</td>\n</td>".format(str,id,currentInput[3])
        str = "{:s}<td><input type=\"text\" name=\"alarm_{:d}_3\" value=\"{:02x}\" size=\"2\" class=\"input_text\"><td>:</td>\n</td>".format(str,id,currentInput[4])
        str = "{:s}<td><input type=\"text\" name=\"alarm_{:d}_4\" value=\"{:02x}\" size=\"2\" class=\"input_text\"><td>:</td>\n</td>".format(str,id,currentInput[5])
        str = "{:s}<td><input type=\"text\" name=\"alarm_{:d}_5\" value=\"{:02x}\" size=\"2\" class=\"input_text\"><td>,</td>\n</td>".format(str,id,currentInput[6])
        str = "{:s}<td><input type=\"text\" name=\"alarm_{:d}_6\" value=\"{:02x}\" size=\"2\" class=\"input_text\"><td>=</td>\n</td>".format(str,id,currentInput[7])
        str = "{:s}<td><input type=\"text\" name=\"alarm_{:d}_7\" value=\"{:02x}\" size=\"2\" class=\"input_text\">\n</td></tr>".format(str,id,currentInput[8])
        #str = "{:s}<button type=\"submit\" name=\"action\" value=\"submit_alarm_{:d}\">Submit value</button>\n".format(str,id)
        return str
    def returnListHTML(self):
        str = "<table><tr><th>Lp.</th><th>Dzien</th><th>-</th><th>Miesiac</th><th>-</th><th>Rok</th><th>-</th><th>Godzina</th><th>:</th><th>Minuta</th><th>:</th><th>Sekunda</th><th>,</th><th>Dzien tygodnia</th><th>=</th><th>Akcja</th></tr>"
        for listInput in self.listOfAlarms:
            str = str+self.returnOneHTML(listInput,self.listOfAlarms.index(listInput))
        return str+"</table>"
    def calculateSchedulerPart(self):
        self.listOfAlarms.clear()
        returnValue = busCANThread.sendConfigReqFrame(self.id,[0x20],20)
        if(returnValue != "Busy. Try again."):
            while busCANThread.configResponseReady():
                pass
            localListofFrames = busCANThread.getConfigReqFrame()
            for localMsgDate, localMsgTime in zip(localListofFrames[::2], localListofFrames[1::2]):
                self.listOfAlarms.append([localMsgDate.data[1],localMsgDate.data[2],localMsgDate.data[3],localMsgDate.data[4],localMsgTime.data[2],
                                          localMsgTime.data[3],localMsgTime.data[4],localMsgTime.data[5],localMsgTime.data[6]])
        return returnValue 
    def sperformAction(self,values):
        minValues = [0x00,0x01,0x01,0x17,0x00,0x00,0x00,0x00,0x00]
        maxValues = [0x09,0x31,0x12,0x99,0x23,0x59,0x59,0x06,0xFF]
        returnValue = ""
        #print("Button.")
        for localObject in self.listOfAlarms:
            #print("List.")
            dataOK = 1
            i = self.listOfAlarms.index(localObject)
            #str = "submit_alarm_{:d}".format(i)
            str = "apply_schedule"
            if(values is not None):
                if(str == values.get('action')):
                    #print("Update requested.")
                    for j in range(0,8):
                        str = "alarm_{:d}_{:d}".format(i,j)
                        readValue = values.get(str)
                        hexValue = int(readValue,16)
                        if((hexValue >=  minValues[j+1] and hexValue <= maxValues[j+1]) or hexValue == 0xFF):
                            self.listOfAlarms[i][j+1] = hexValue
                        else:
                            dataOK = 0
                    #if(dataOK):
                        #print("Apdejt")
                        #busCANThread.sendConfigReqFrame(self.id,[0x10,self.listOfAlarms[i][0],self.listOfAlarms[i][1],self.listOfAlarms[i][2],self.listOfAlarms[i][3]],0)
                        #busCANThread.sendConfigReqFrame(self.id,[0x11,self.listOfAlarms[i][0],self.listOfAlarms[i][4],self.listOfAlarms[i][5],
                        #                                         self.listOfAlarms[i][6],self.listOfAlarms[i][7],self.listOfAlarms[i][8]],0)
                    time.sleep(0.1) #tutaj trzeba poprawic komunikacje miedzy ecu i pythonem, po zapytaniu bez odpowiedzi, kolejne z odpowiedzia sie blokuje
                    returnValue = self.calculateSchedulerPart()
            else:
                print("some action here")
                
        if('update_schedule_storczyki' == values.get('action')):
            returnValue = self.calculateSchedulerPart()    
        return returnValue
    def updateScheduler(self,values):
        minValues = [0x00,0x01,0x01,0x17,0x00,0x00,0x00,0x00,0x00]
        maxValues = [0x09,0x31,0x12,0x99,0x23,0x59,0x59,0x06,0xFF]
        returnValue = ""
        for localObject in self.listOfAlarms:
            dataOK = 1
            i = self.listOfAlarms.index(localObject)
            dataChange = False
            for j in range(0,8):
                str = "alarm_{:d}_{:d}".format(i,j)
                readValue = values.get(str)
                hexValue = int(readValue,16)
                if((hexValue >=  minValues[j+1] and hexValue <= maxValues[j+1]) or hexValue == 0xFF):
                    if(self.listOfAlarms[i][j+1] != hexValue):
                        self.listOfAlarms[i][j+1] = hexValue
                        dataChange = True
                else:
                    dataOK = 0
            if(dataOK):
                if(dataChange):
                    #print("Update")
                    busCANThread.sendConfigReqFrame(self.id,[0x10,self.listOfAlarms[i][0],self.listOfAlarms[i][1],self.listOfAlarms[i][2],self.listOfAlarms[i][3]],0)
                    busCANThread.sendConfigReqFrame(self.id,[0x11,self.listOfAlarms[i][0],self.listOfAlarms[i][4],self.listOfAlarms[i][5],
                                                             self.listOfAlarms[i][6],self.listOfAlarms[i][7],self.listOfAlarms[i][8]],0)
        if(dataChange):
            time.sleep(0.1) #tutaj trzeba poprawic komunikacje miedzy ecu i pythonem, po zapytaniu bez odpowiedzi, kolejne z odpowiedzia sie blokuje
            returnValue = self.calculateSchedulerPart() 
        #    else:
        #        print("some action here")
                
        #if('update_schedule_storczyki' == values.get('action')):
        #   returnValue = self.calculateSchedulerPart()    
        return returnValue
    
class pageDefinition_rtc_storczyki(pageDefinition):
    def __init__(self,title, fileName, pattern, deviceID):
        pageDefinition.__init__(self,title, fileName, pattern, deviceID)
        self.title = 'rTC-Storczyki'
        self.searchPattern = 'rTC-Storczyki'
        self.alarmListLocal = alarmList(self.deviceID,self.searchPattern)
        self.addButton('pst', 'Water orchids.',busCANThread.sendActuatorFrame,(self.deviceID,[0xAA]))
        self.addButton('on', 'Light on.',busCANThread.sendActuatorFrame,(self.deviceID,[0x00]))
        self.addButton('off', 'Light off.',busCANThread.sendActuatorFrame,(self.deviceID,[0x01]))
        self.addButton('off3h', 'Light off for 3 hours.',busCANThread.sendActuatorFrame,(self.deviceID,[0xBB]))
        self.addButton('update_schedule_storczyki', 'Update scheduler.',self.generateAdditionalFormData,())
        self.addButton('apply_schedule_storczyki', 'Apply scheduler.',self.updateAlarmData,())
    def generateAdditionalFormData(self):
        self.alarmListLocal.calculateSchedulerPart()
        self.additionalFormData = "<BR><BR>"+self.alarmListLocal.returnListHTML()+"<BR><BR>"
    def updateAlarmData(self):
        self.alarmListLocal.updateScheduler(self.responseForm)
    #def generateListOfOther(self):
    #    str=pageDefinition.generateListOfOther(self)
        #str = str+self.alarmListLocal.returnListHTML()+"<BR><BR>"
    #    return str
    #def performAction(self,values): 
     #   pageDefinition.performAction(self, self.responseForm)
      #  return self.alarmListLocal.performAction(self.responseForm)

class pageDefinition_rtc_akwarium(pageDefinition):
    def __init__(self,title, fileName, pattern, deviceID):
        pageDefinition.__init__(self,title, fileName, pattern, deviceID)
        self.title = 'rTC-Akwarium'
        self.searchPattern = 'rTC-Akwarium'
        self.alarmListLocal = alarmList(self.deviceID,self.searchPattern)
        self.addButton('on_actinic', 'Turn on Actinic light.',busCANThread.sendActuatorFrame,(self.deviceID,[0x01]))
        self.addButton('on_blue_1', 'Turn on Blue light (1).',busCANThread.sendActuatorFrame,(self.deviceID,[0x11]))
        self.addButton('on_blue_2', 'Turn on Blue light (2).',busCANThread.sendActuatorFrame,(self.deviceID,[0x21]))
        self.addButton('on_while', 'Turn on White light.',busCANThread.sendActuatorFrame,(self.deviceID,[0x31]))
        self.addButton('off_actinic', 'Turn off Actinic light.',busCANThread.sendActuatorFrame,(self.deviceID,[0x00]))
        self.addButton('off_blue_1', 'Turn off Blue light (1).',busCANThread.sendActuatorFrame,(self.deviceID,[0x10]))
        self.addButton('off_blue_2', 'Turn off Blue light (2).',busCANThread.sendActuatorFrame,(self.deviceID,[0x20]))
        self.addButton('off_while', 'Turn off White light.',busCANThread.sendActuatorFrame,(self.deviceID,[0x30]))
        self.addButton('on_all', 'Turn on all lights.',busCANThread.sendActuatorFrame,(0x1001,[0xAB]))
        self.addButton('off_all', 'Turn off all lights.',busCANThread.sendActuatorFrame,(self.deviceID,[0xAC]))
        self.addButton('update_schedule', 'Update scheduler.',self.generateAdditionalFormData,())
        self.addButton('apply_schedule', 'Apply scheduler.',self.updateAlarmData,())
    def generateAdditionalFormData(self):
        self.alarmListLocal.calculateSchedulerPart()
        self.additionalFormData = "<BR><BR>"+self.alarmListLocal.returnListHTML()+"<BR><BR>"
    def updateAlarmData(self):
        self.alarmListLocal.updateScheduler(self.responseForm)
    #def generateListOfOther(self):
    #    str=pageDefinition.generateListOfOther(self)
        #str = str+self.alarmListLocal.returnListHTML()+"<BR><BR>"
    #    return str
    #def performAction(self,values):
     #   pageDefinition.performAction(self, self.responseForm)
      #  return self.alarmListLocal.performAction(self.responseForm)

def new_id():
    time.sleep(0.000001)
    return time.time()

class classOutputControl():
    def __init__(self, outputId, actionDescription):
        self.actionId = new_id()
        self.actionDescription = actionDescription
        self.outputId = outputId
        self.outputStatus = 0xFF
    def listOutput(self):
        print(self.actionId+" "+self.actionDescription+" "+self.outputStatus)
    def sendOutput(self, value):
        return_value = 0xFF
        #send value
        #wait for response
        return return_value
    def setOutput(self):
        #send status
        #wait for response
        #store data
        pass
    def unsetOutput(self):
        pass
    def toggleOutput(self):
        pass

class nodeClass():
    def __init__(self, deviceClass, nodeId, name):
        self.nodeClass = deviceClass
        self.nodeId = nodeId
        self.nodeName = name
        self.nodeSearchPattern = re.sub(r"\s", "", name)
        self.nodeMessageList = []
        self.nodeActionList = []
    def assignSignalClass(self, msg):
        if((msg.arbitration_id & 0x1FFF0000) == 0x10FF0000):
            p = NM_CANframe(msg)
        elif((msg.arbitration_id & 0x1FFF0000) == 0x02000000):
            p = Sensor_CANframe(msg)   
        elif((msg.arbitration_id & 0x1FFF0000) == 0x05000000):
            p = CANframe(msg)
            self.responsePending(msg)
        #    if((msg.arbitration_id & 0x0000FFFF) == self.ConfigReqResponseID  and msg.data[0] == self.ConfigReqResponseByte):
        #        if(self.ConfigReqResponseCount > 0):
        ##            self.ConfigReqResponseCount -= 1
        #            self.ConfigReqList.append(msg)
        #        else:
        #            self.ConfigReqResponseID = 0xFFFF;
        #            self.ConfigReqResponseByte = 0xFF;
        elif((msg.arbitration_id & 0x1FFF0000) == 0x04000000): 
            p = Actuator_CANframe(msg)
        elif((msg.arbitration_id & 0x1FFF0000) == 0x10000000):
            p = ERROR_CANframe(msg) 
        elif((msg.arbitration_id & 0x1FFF0000) == 0x06000000):
            p = Display_CANframe(msg)  
        elif((msg.arbitration_id & 0x1FFF0000) == 0x08000000):
            p = ConfREQ_CANframe(msg) 
        elif((msg.arbitration_id & 0x1FFF0000) == 0x09000000):
            p = ConfRES_CANframe(msg)
        elif((msg.arbitration_id & 0x1FFF0000) == 0x0EFF0000):
            p = DiagREQ_CANframe(msg) 
        elif((msg.arbitration_id & 0x1FFF0000) == 0x0FFF0000):
            p = DiagRES_CANframe(msg) 
        elif((msg.arbitration_id & 0x1FFF0000) == 0x1FFF0000):
            p = BootREQ_CANframe(msg) 
        elif((msg.arbitration_id & 0x1FFF0000) == 0x1FF00000):
            p = BootRES_CANframe(msg) 
        elif((msg.arbitration_id & 0x1FFF0000) == 0x00000000):
            p = Critical_CANframe(msg) 
        else:
            p = CANframe(msg)
        return p 
    def responsePending(self, message):
        pass
    def updateSignalList(self, message):
        tempObject = None
        objectUpdated = False
        if(True):
            if((message.arbitration_id & 0x0000FFFF) == ((self.nodeClass << 8)|(self.nodeId))):
                tempObject = self.assignSignalClass(message) #CANframe(message)#EnvironmentSensor_CANframe(message)
                for item in self.nodeMessageList:
                    if(item.getId() == tempObject.getId() and item.getMultiplexed() == tempObject.getMultiplexed()):
                        self.nodeMessageList[self.nodeMessageList.index(item)] = tempObject
                        objectUpdated = True
                        break
                if(not objectUpdated):
                    self.nodeMessageList.append(tempObject)
    def generatePage(self, stringOfPages):
        strng = self.nodeName+"<BR>"
        strng += self.generateListOfSignals()
        strng += self.generateListOfActions()
        strng += self.generateListOfOther()
        strng += self.generateListOfFooter()
        
        [return_string, return_script] = _div_toggled(self.nodeName,strng,"","X Y Z",1,1)
        
        return [return_string, return_script]#str#"AAA"#self.nodeClass+"\n"+self.nodeName+"\n"+self.nodeSearchPattern+"\n\n"
    def categorizeData(self):
        typeName = "xxx"
        return_list = []
        for i in range(0x7F):
            local_list_data = [item.serializeData(1) for item in self.nodeMessageList if (item.getFrameType() == (i<<24))]
            local_list_signal = [item.serializeData(0) for item in self.nodeMessageList if (item.getFrameType() == (i<<24))]
            if(len(local_list_data) > 0):
                return_list.append([local_list_signal, local_list_data, typeName])
        return return_list
    def categorizeSignals(self):
        return_list = [item.serializeData(0) for item in self.nodeMessageList if (item.getFrameType() == 0x02000000)]
        return return_list
    def generateListOfSignals(self):
        #str = "List of signals<BR> "
        out_string = ""
        out_script = ""
        listOfCategorizedSignals = self.categorizeData()
        for item in listOfCategorizedSignals:
            strng1 = _table(item[0],item[2]+" frames",self.nodeName,5,self.nodeName,self.nodeName)
            strng2 = _table(item[1],item[2]+" values",self.nodeName,5,self.nodeName,self.nodeName) 
            [local_string, local_script] = _div_toggled("div_table"+self.nodeName,strng1,strng2,[],1,0)
            out_string += local_string
            out_script += local_script
        #for item in self.nodeMessageList:
        #    str += ":".join(item.serializeData(1))
        #    str += "<BR>"
        return out_string
    def generateListOfActions(self):
        str = "List of actions<BR>"
        return str
    def generateListOfOther(self):
        str = "List of others<BR>"
        return str
    def generateListOfFooter(self):
        str = "List of footer<BR>"
        return str

class nodeClass_EnvironmentSensors(nodeClass):
    def __init__(self, nodeId, name):
        nodeClass.__init__(self, 0x20, nodeId, name)
    def assignSignalClass(self, msg):
        if((msg.arbitration_id & 0x1FFF0000) == 0x02000000):
            p = EnvironmentSensor_CANframe(msg)
        else:
            p = nodeClass.assignSignalClass(self, msg)
        return p
             
class nodeClass_RTCOnCAN(nodeClass):
    def __init__(self, nodeId, name):
        nodeClass.__init__(self, 0x00, nodeId, name)
    def assignSignalClass(self, msg):     
        if((msg.arbitration_id & 0x1FFF0000) == 0x02000000):
            p = RTC_CANframe(msg)
        else:
            p = nodeClass.assignSignalClass(self, msg)
        return p
                
class nodeClass_RelayOnCAN(nodeClass):
    def __init__(self, nodeId, name):
        nodeClass.__init__(self, 0x10, nodeId, name)
    def assignSignalClass(self, msg):    
        if((msg.arbitration_id & 0x1FFF0000) == 0x02000000):
            p = RTCrelay_CANframe(msg)
        else:
            p = nodeClass.assignSignalClass(self, msg)
        return p
                
class nodeClass_NixieDisplay(nodeClass):
    def __init__(self, nodeId, name):
        nodeClass.__init__(self, 0x40, nodeId, name)
        
class nodeClass_PMmeter(nodeClass):
    def __init__(self, nodeId, name):
        nodeClass.__init__(self, 0x21, nodeId, name)
    def assignSignalClass(self, msg):    
        if((msg.arbitration_id & 0x1FFF0000) == 0x02000000):
            p = PMSensor_CANframe(msg)
        else:
            nodeClass.assignSignalClass(self, msg)
        
class deviceClass():
    def __init__(self, deviceName):
        self.deviceName = deviceName
        self.nodeList = []
    def updateMessageList(self, message):
        for node in self.nodeList:
            node.updateSignalList(message)
    def generatePage(self, stringOfPages):
        return_string = ""
        return_script = ""
        return_string += self.deviceName+":\n"
        
        for items in self.nodeList:
            [str, scr] = items.generatePage(stringOfPages)
            return_string += str
            return_script += scr
            
        [return_string, scr] = _div_toggled(self.deviceName,return_string,"","X Y Z",1,1)
        return_script += scr
        return [return_string, return_script]
            
class deviceClass_NixieClock(deviceClass):
    def __init__(self):
        deviceClass.__init__(self, "Zegar Nixie")
        self.nodeList.append(nodeClass_RTCOnCAN(0x00,"RTC-Nixie"))
        self.nodeList.append(nodeClass_NixieDisplay(0x00,"Nixie-Display"))
        self.nodeList.append(nodeClass_EnvironmentSensors(0x00,"Salon-Nixie"))

class deviceClass_Aquarium(deviceClass):
    def __init__(self):
        deviceClass.__init__(self, "Sterownik akwarium")
        self.nodeList.append(nodeClass_EnvironmentSensors(0x04,"Akwarium"))
        self.nodeList.append(nodeClass_RelayOnCAN(0x01,"rTC-Akwarium"))

class deviceClass_Orchids(deviceClass):
    def __init__(self):
        deviceClass.__init__(self, "Sterownik orchidarium")
        self.nodeList.append(nodeClass_EnvironmentSensors(0x01,"Storczyki"))
        self.nodeList.append(nodeClass_RelayOnCAN(0x00,"rTC-Storczyki"))

class deviceClass_Taras(deviceClass):
    def __init__(self):
        deviceClass.__init__(self, "Czujniki pogody - balkon")
        self.nodeList.append(nodeClass_EnvironmentSensors(0x02,"Balkon"))
        self.nodeList.append(nodeClass_PMmeter(0x00,"PM-Balkon"))
        
class deviceClass_Chomik(deviceClass):
    def __init__(self):
        deviceClass.__init__(self, "Czujniki temperatury - Chomik")
        self.nodeList.append(nodeClass_EnvironmentSensors(0x03,"Chomik"))
        
import hmac, base64, struct, hashlib, time

def get_hotp_token(secret, intervals_no):
    key = base64.b32decode(secret, True)
    #print(key)
    #msg = struct.pack(">Q", intervals_no)
    #print(intervals_no)
    msg = intervals_no.to_bytes(8, byteorder='big')
    #print(some_bytes)
    #msg = some_bytes#bytearray(some_bytes)
    #print(msg)
    hmac_sha1 = hmac.new(key, msg, hashlib.sha1).hexdigest()
    #print("HMAC: "+hmac_sha1)
    offset = int(hmac_sha1[-1], 16) 
    #print("Offset: "+str(offset)+": "+hmac_sha1[(offset * 2):((offset * 2) + 8)])
    binary = int(hmac_sha1[(offset * 2):((offset * 2) + 8)], 16) & 0x7fffffff
    #print(binary)
    binary = binary  % 1000000
    return "{:d}".format(binary)

def get_totp_token(secret):
    return get_hotp_token(secret, intervals_no=int(time.time())//30)
        
class pageEngine():
    def __init__(self):
        self.listOfDevices = []
        pass
    def generate(self):
        str = "<BR>No page to display.<BR>"
        href = ""
        script = ""
        title = ""
        full = 0
        if request.method == 'POST':
            str = ""
            for page in listOfPages:
                pat = 'authorization'
                val = get_totp_token('MZXW633PN5XW6MZX')
                #print("X: "+request.form.get(pat)+" == "+val)
                if(request.remote_addr[:7] == "192.168" or request.form.get('authorization') == val):
                    page.addResponseForm(request.form)
                    page.performAction()          
            str = redirect('index'+href)
        if request.method == 'GET':
            str = ""
            for page in listOfPages:
                full = 0
                if(len(request.args) > 0):
                    for line in request.args:
                        if(page.searchPattern == line):
                            full = 1
                            if(href != ""):
                                href = href + "&" + line
                                title = title + " & " + page.title
                            else:
                                href = href + "?" + line
                                title = page.title 
                if(title == ""):
                    title = "Main page" 
                str = str + page.generateSubPageContent(href,full)
                script = script + page.generateScriptContent();
            str = render_template('index.html', script_content = script, title = title, str = str)
        return str


class networkClass():
    def __init__(self):
        self.listOfDevices = []
    def append(self, deviceClassObject):
        self.listOfDevices.append(deviceClassObject)
    def pop(self, deviceClassObject):
        pass
    def sort(self):
        pass
    def generate(self):
        str = "<BR>No page to display.<BR>"
        href = ""
        script = ""
        title = ""
        if request.method == 'POST':
            str = ""
            for page in self.listOfDevices:
                #page.performAction(request.form)
                pass          
            str = redirect('index'+href)
        if request.method == 'GET':
            str = ""
            for line in request.args:
                if(href != ""):
                    href = href + "&" + line
                    #title = title + " & " + page.title
                else:
                    href = href + "?" + line
                    #title = page.title
            if(title == ""):
                    title = "Main page"
            for page in self.listOfDevices:
                [lstr, lscript] = page.generatePage(href)
                str += lstr
                script += lscript
                #script = script + page.generateScriptContent();
            str = render_template('index.html', script_content = script, title = title, str = str)
        return str

#ten smieszny sposob na wylapywanie bledow
try:
    canMsg_received = queue.Queue()
    canMsg_send = queue.Queue()
    buttonPress_queue = queue.Queue()
    
    threadLock = threading.Lock()
    threads = []
    
    run_event = threading.Event()
    
    
    msgList = []
    msgListLock = threading.Lock()
    
    run_event.set() 
    
    windowThread = windowManagement(run_event,canMsg_received,buttonPress_queue,msgList,msgListLock)
    busCANThread = manageCAN(run_event,canMsg_received,canMsg_send,msgList,msgListLock)
    canEngineThread = canEngine(run_event,canMsg_received,canMsg_send)
    
    threads.append(windowThread)
    threads.append(busCANThread)
    
    windowThread.start()
    busCANThread.start()    
    canEngineThread.start() 
 
    listOfPages.append(pageDefinition_index('Main page','index.html','',0xFFFF))
    listOfPages.append(pageDefinition('RTC-Nixie','RTC-Nixie.html','RTC-Nixie',0x0000))
    listOfPages.append(pageDefinition('Akwarium','Akwarium.html','Akwarium',0x2004))
    listOfPages.append(pageDefinition_rtc_akwarium('rTC-Akwarium','rTC-Akwarium.html','rTC-Akwarium',0x1001))
    listOfPages.append(pageDefinition('Storczyki','Storczyki.html','Storczyki',0x2001))
    listOfPages.append(pageDefinition_rtc_storczyki('rTC-Storczyki','rTC-Storczyki.html','rTC-Storczyki',0x1000))
    listOfPages.append(pageDefinition('Salon-Nixie','Salon-Nixie.html','Salon-Nixie',0x2000))
    listOfPages.append(pageDefinition('Balkon','Balkon.html','Balkon',0x2002))
    listOfPages.append(pageDefinition('Chomik','Chomik.html','Chomik',0x2003))
    listOfPages.append(pageDefinition('PM-Meter','PM-Meter.html','PM-Meter',0x2100))
    listOfPages.append(pageDefinition('Nixie-Display','Nixie-Display.html','Nixie-Display',0x4000))
    
    if(True):
        mainPage = pageEngine()
    
        #listOfDevices.append(deviceClass_NixieClock())
        #listOfDevices.append(deviceClass_Orchids())
        #listOfDevices.append(deviceClass_Aquarium())
        #listOfDevices.append(deviceClass_Chomik())
        #listOfDevices.append(deviceClass_Taras())
    else:
        mainPage = networkClass()
        mainPage.append(deviceClass_NixieClock())
        mainPage.append(deviceClass_Orchids())
        mainPage.append(deviceClass_Aquarium())
        mainPage.append(deviceClass_Chomik())
        mainPage.append(deviceClass_Taras())
    
    app.add_url_rule('/','index',mainPage.generate,methods=['GET', 'POST'])
    app.add_url_rule('/index','index',mainPage.generate,methods=['GET', 'POST'])
    #socketio.on_namespace(MyNamespace('/akwarium'))
    #socketio.run(app)
    app.run(threaded=True, debug=False, host='0.0.0.0', port=8282)
    
    while(True):
        time.sleep(.1)

except KeyboardInterrupt:
    run_event.clear()
    if(busCANThread.isAlive()):
        busCANThread.join()
    if(windowThread.isAlive()):
       windowThread.join()
    curses.endwin()
finally:
    print(str(len(msgList))+" "+outStr)