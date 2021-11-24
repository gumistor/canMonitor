import threading
import curses
import queue
import signal
import time
import can
import datetime
from flask import Flask
from flask import render_template

import logging
from logging.handlers import RotatingFileHandler

log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)
file_handler = RotatingFileHandler('app.run.log', maxBytes=10000000, backupCount=5)
log.addHandler(file_handler)
formatter = logging.Formatter("[%(asctime)s] %(message)s -- {%(pathname)s:%(lineno)d} %(levelname)s")
file_handler.setFormatter(formatter)
app = Flask(__name__)

class CANframe (object):
    def __init__(self,msg):
        self.multiplexedList = [0x02002000, 0x02002100, 0x02002001, 0x02002002, 0x02002003, 0x02002004]
        self.deviceNameList = {0x0000:'RTC-Nixie',0x1000:'rTC-Storczyki',0x2100:'PM-Meter',0x2000:'Salon-Nixie',0x4000:'Nixie-Display',0x2001:'Storczyki',0x2002:'Balkon',0x2003:'Chomik',0x2004:'Akwarium'}
        self.frameName = ''
        self.id = msg.arbitration_id
        self.deviceName = self.deviceNameList.get(0x0000FFFF & self.id,"xxx")  
        self.dlc = msg.dlc
        self.data = []
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
    def getMultiplexed(self):
        return self.multiplexed
    def checkMultiplexed(self):
        return self.multiplexedList.count(self.id)
    def dataStr(self):
        return ' '.join("%02x" % b for b in self.data)# .join(map(str,self.data))
    def multiplexedStr(self):
        if(-1 == self.multiplexed):
            return '  '
        else:
            return '{mul:2d}'.format(mul = self.multiplexed)
    def stringCAN(self):
        return '{t:20s}{id:08x} {dlc:02x}{mul:3s}{data:24s}{fN:25s}{dN:14s}'.format(id=self.id, dlc=self.dlc, t=self.timestampStr, mul = self.multiplexedStr(), data = self.dataStr(),fN = self.frameName, dN = self.deviceName)
    def showData(self):
        return self.stringCAN()
    def showHtmlData(self):
        return '<td colspan=\'6\'>{str:s}</td>'.format(str = self.stringCAN())
    

class NM_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'NM frame'
      
class Sensor_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Sensor frame'

class Actuator_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Actuator frame'

class ERROR_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'ERROR frame'

class Display_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Display frame'

class ConfREQ_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Config request frame'
        
class ConfRES_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Config response frame'
        
class DiagREQ_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Diag request frame'
        
class DiagRES_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Diag response frame'
        
class BootREQ_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Boot request frame'
        
class BootRES_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Boot response frame'

class Critical_CANframe(CANframe):
    def __init__(self,msg):
        CANframe.__init__(self,msg)
        self.frameName = 'Boot response frame'

class EnvironmentSensor_CANframe(Sensor_CANframe):
    def __init__(self,msg):
        Sensor_CANframe.__init__(self,msg)
        self.frameName = 'Environment Sensor frame'
        self.multiplexedValues = {0:'Humidity', 1:'Temperature (hum)', 2:'Pressure', 3:'Temperature (press)'}
        self.multiplexedType = {0:'%', 1:'\xb0C',2:'hPa',3:'\xb0C'}
    def calculateHum(self):
        return 0
    def calculateHumTemp(self):
        return 0
    def calculatePress(self):
        return 0
    def calculatePressTemp(self):
        return 0
    def calculateTemp(self):
        return 0
    def showData(self):
        value = ((self.data[4])+(self.data[3]<<8)+(self.data[2]<<16))
        if value & 0x800000:
            value = 0xFF000000 | value
            value = 0xFFFFFFFF - value
            value += 1
            value = -1*value
        val = value/100.
        
        if(self.getMultiplexed() < 4):
            str = '{dN:14s}{name:25s}{value:.1f} {type:4s}{inne:70s}'.format(name = self.multiplexedValues.get(self.getMultiplexed(),'???'), value = val, type = self.multiplexedType.get(self.getMultiplexed(),'???'),inne=' ', data = self.dataStr(),fN = self.frameName, dN = self.deviceName)
        elif(self.getMultiplexed() == -1):
            str = self.stringCAN()
        else:
            str = '{dN:14s}{name:25s}{value:.1f} {type:4s}{inne:70s}'.format(name = 'Temperature', value = val, type = '\xb0C',inne=' ', data = self.dataStr(),fN = self.frameName, dN = self.deviceName)
        return '{t:20s}{line:s}'.format(t=self.timestampStr, line=str)
    def showHtmlData(self):
        value = ((self.data[4])+(self.data[3]<<8)+(self.data[2]<<16))
        if value & 0x800000:
            value = 0xFF000000 | value
            value = 0xFFFFFFFF - value
            value += 1
            value = -1*value
        val = value/100.
        
        if(self.getMultiplexed() < 4):
            str = '<td>{dN:s}</td><td>{name:s}</td><td>{value:.1f}</td><td>{type:4s}</td><td>{inne:70s}</td>'.format(name = self.multiplexedValues.get(self.getMultiplexed(),'???'), value = val, type = self.multiplexedType.get(self.getMultiplexed(),'???'),inne=' ', data = self.dataStr(),fN = self.frameName, dN = self.deviceName)
        elif(self.getMultiplexed() == -1):
            str = self.stringCAN()
        else:
            str = '<td>{dN:s}</td><td>{name:s}</td><td>{value:.1f}</td><td>{type:4s}</td><td>{inne:70s}</td>'.format(name = 'Temperature', value = val, type = '\xb0C',inne=' ', data = self.dataStr(),fN = self.frameName, dN = self.deviceName)
        return '<td>{t:20s}</td>{line:s}'.format(t=self.timestampStr, line=str)
    
class PMSensor_CANframe(Sensor_CANframe):
    def __init__(self,msg):
        Sensor_CANframe.__init__(self,msg)
        self.frameName = 'PM Sensor frame'
        self.multiplexedValues = {0:'Time', 1:'PMS3003 PM 1.0', 2:'PMS3003 PM 2.5', 3:'PMS3003 PM 10', 4:'GP2Y10 PM 1.0-10.0'}
        self.multiplexedType = {0:'', 1:'ug/m3',2:'ug/m3',3:'ug/m3',4:'ug/m3'}      
    def showData(self):
        if(self.getMultiplexed() == 0):
            str = '{dN:14s}{name:25s}{h:02x}:{m:02x}:{s:02x} {w:s}, {d:02x}-{mm:s}-20{y:02x}'.format(name = self.multiplexedValues.get(self.getMultiplexed(),'???'), dN = self.deviceName, m=self.data[2], h=self.data[1], s=self.data[3], w=getDay(self.data[4]), d=self.data[5], mm=getMonth(self.data[6]), y=self.data[7])
        elif(self.getMultiplexed() < 4):
            value = ((self.data[4])+(self.data[3]<<8))
            str = '{dN:14s}{name:25s}{value:d} {type:4s}{inne:70s}'.format(name = self.multiplexedValues.get(self.getMultiplexed()), value = value, type = self.multiplexedType.get(self.getMultiplexed(),'???'),inne=' ', data = self.dataStr(),fN = self.frameName, dN = self.deviceName)
        elif(self.getMultiplexed() == 4):
            value = ((self.data[2])+(self.data[1]<<8))
            str = '{dN:14s}{name:25s}{value:d} {type:4s}{inne:70s}'.format(name = self.multiplexedValues.get(self.getMultiplexed()), value = value, type = self.multiplexedType.get(self.getMultiplexed(),'???'),inne=' ', data = self.dataStr(),fN = self.frameName, dN = self.deviceName)            
        else:
            str = self.stringCAN()
        return '{t:20s}{line:s}'.format(t=self.timestampStr, line=str)
    def showHtmlData(self):
        if(self.getMultiplexed() == 0):
            str = '<td>{dN:s}</td><td>{name:s}</td><td>{h:02x}:{m:02x}:{s:02x}</td><td>{w:s}, {d:02x}-{mm:s}-20{y:02x}</td>'.format(name = self.multiplexedValues.get(self.getMultiplexed(),'???'), dN = self.deviceName, m=self.data[2], h=self.data[1], s=self.data[3], w=getDay(self.data[4]), d=self.data[5], mm=getMonth(self.data[6]), y=self.data[7])
        elif(self.getMultiplexed() < 4):
            value = ((self.data[4])+(self.data[3]<<8))
            str = '<td>{dN:s}</td><td>{name:s}</td><td>{value:d}</td><td>{type:s}</td><td>{inne:s}</td>'.format(name = self.multiplexedValues.get(self.getMultiplexed()), value = value, type = self.multiplexedType.get(self.getMultiplexed(),'???'),inne=' ', data = self.dataStr(),fN = self.frameName, dN = self.deviceName)
        elif(self.getMultiplexed() == 4):
            value = ((self.data[2])+(self.data[1]<<8))
            str = '<td>{dN:s}</td><td>{name:s}</td><td>{value:d}</td><td>{type:s}</td><td>{inne:s}</td>'.format(name = self.multiplexedValues.get(self.getMultiplexed()), value = value, type = self.multiplexedType.get(self.getMultiplexed(),'???'),inne=' ', data = self.dataStr(),fN = self.frameName, dN = self.deviceName)
        else:
            str = self.stringCAN()
        return '<td>{t:20s}</td>{line:s}'.format(t=self.timestampStr, line=str)
    
class RTC_CANframe(Sensor_CANframe):
    def __init__(self,msg):
        Sensor_CANframe.__init__(self,msg)
        self.frameName = 'RTC on CAN'
    def showData(self):
        str = '{dN:14s}{name:25s}{h:02x}:{m:02x}:{s:02x} {w:s}, {d:02x}. {mm:s} 20{y:02x}            '.format(name = 'Time', dN = self.deviceName, m=self.data[1], h=self.data[0], s=self.data[2], w=getDay(self.data[4]), d=self.data[5], mm=getMonth(self.data[6]), y=self.data[7])
        return '{t:20s}{line:s}'.format(t=self.timestampStr, line=str)
    def showHtmlData(self):
        str = '<td>{dN:s}</td><td>{name:s}</td><td>{h:02x}:{m:02x}:{s:02x} </td><td>{w:s}, {d:02x}. {mm:s} 20{y:02x}</td>'.format(name = 'Time', dN = self.deviceName, m=self.data[1], h=self.data[0], s=self.data[2], w=getDay(self.data[4]), d=self.data[5], mm=getMonth(self.data[6]), y=self.data[7])
        return '<td>{t:s}</td>{line:s}'.format(t=self.timestampStr, line=str)

class RTCrelay_CANframe(Sensor_CANframe):
    def __init__(self,msg):
        Sensor_CANframe.__init__(self,msg)
        self.frameName = 'RTC on CAN'
    def showData(self):
        str = '{dN:14s}{name:25s}{h:02x}:{m:02x}:{s:02x} {w:s}, {d:02x}. {mm:s} 20{y:02x}            '.format(name = 'Time', dN = self.deviceName, m=self.data[2], h=self.data[1], s=self.data[3], w=getDay(self.data[4]), d=self.data[5], mm=getMonth(self.data[6]), y=self.data[7])
        return '{t:20s}{line:s}'.format(t=self.timestampStr, line=str)
    def showHtmlData(self):
        str = '<td>{dN:s}</td><td>{name:s}</td><td>{h:02x}:{m:02x}:{s:02x} </td><td>{w:s}, {d:02x}. {mm:s} 20{y:02x}</td>'.format(name = 'Time', dN = self.deviceName, m=self.data[2], h=self.data[1], s=self.data[3], w=getDay(self.data[4]), d=self.data[5], mm=getMonth(self.data[6]), y=self.data[7])
        return '<td>{t:s}</td>{line:s}'.format(t=self.timestampStr, line=str)
    
def getDay(value):
    weekdays = {7:'Niedziela',1:'Poniedzialek',2:'Wtorek',3:'Sroda',4:'Czwartek',5:'Piatek',6:'Sobota'}
    return weekdays.get(value,'?weekday?') 
    

def getMonth(value):
    months = {0x01:'Styczen',0x02:'Luty',0x03:'Marzec',0x04:'Kwiecien',0x05:'Maj',0x06:'Czerwiec',0x07:'Lipiec',0x08:'Sierpien',0x09:'Wrzesien',0x10:'Pazdziernik',0x11:'Listopad',0x12:'Grudzien'}
    return months.get(value,'?month?') 


class httpManagement (threading.Thread):
    def __init__(self,run_event):
        default = 'Hello word'
    def run(self):
        app.run(debug=True, host='0.0.0.0')
        
class windowManagement (threading.Thread):
    def __init__(self,run_event,queueData,queueButton):
        threading.Thread.__init__(self)
        self.window = curses.initscr()
        self.window.nodelay(1)
        (self.h, self.w) = self.window.getmaxyx()
        curses.noecho()
        self.i = []        
        self.queue = queueData
        self.queueButton = queueButton
        self.dataSetDisplay = 0
        self.run_event = run_event
    def run(self):
        while self.run_event.is_set():
            key_char = self.window.getch()
            if(-1 != key_char):
                self.dataSetDisplay = key_char
            if(not self.queue.empty()):
                received = self.queue.get()
                element_found = 0
                for p in self.i:
                    if(p.getId() == received.getId() and p.getMultiplexed() == received.getMultiplexed()):
                        self.i[self.i.index(p)] = received
                        element_found = 1
                        break
                if(element_found == 0):
                    self.i.append(received)
            if(not self.queueButton.empty()):
                self.dataSetDisplay = self.queueButton.get()
            self.filterDysplay()
    def filterDysplay(self):
        self.i.sort()
        if(0x31 == self.dataSetDisplay):
            j = 0
            for p in self.i:
                if(j < self.h):
                    self.window.addstr(j,0,p.stringCAN())
                    j += 1
        elif (0x32 == self.dataSetDisplay):
            self.window.addstr(0,0,'C: {ii:x} {s:10s}'.format(ii=self.dataSetDisplay,s=""))
        else:
            j = 0
            for p in self.i:
                if(j < self.h):
                    self.window.addstr(j,0,p.showData())
                    j += 1
        self.window.refresh()
    def httpFilterDysplay(self):
        str = ''
        for p in self.i:
            str = '{old:s}<tr>{new:s}</tr>'.format(old = str, new = p.showHtmlData()) 
        return str 

class manageCAN (threading.Thread):
    def __init__(self,bus,run_event,queueData):
        threading.Thread.__init__(self)        
        self.queue = queueData
        self.run_event = run_event
        self.bus = bus
    def run(self):
        while self.run_event.is_set():
            msg = self.bus.recv()
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
            self.queue.put(p)
    def sendActuatorFrame(self, id, dataToSend):
        localmsg = can.Message(arbitration_id=(0x04000000 | id), data=dataToSend, extended_id=True)
        self.bus.send(localmsg)
        return '{}'.format(localmsg)
    
try:
    bus = can.interface.Bus(channel='can0', bustype='socketcan_native')
    
    canMsg_queue = queue.Queue()
    buttonPress_queue = queue.Queue()
    
    threadLock = threading.Lock()
    threads = []
    
    run_event = threading.Event()
    
    run_event.set()
    
    windowThread = windowManagement(run_event,canMsg_queue,buttonPress_queue)
    busCANThread = manageCAN(bus, run_event,canMsg_queue)
    
    threads.append(windowThread)
    threads.append(busCANThread)
    
    windowThread.start()
    busCANThread.start()    

    @app.route('/')
    def index():
        return render_template('index.html', content = windowThread.httpFilterDysplay())

    @app.route('/pst')
    def pst():
        return busCANThread.sendActuatorFrame(0x1000,[0xAA])
    @app.route('/off')
    def off():
        return busCANThread.sendActuatorFrame(0x1000,[0x00])
    @app.route('/on')
    def off():
        return busCANThread.sendActuatorFrame(0x1000,[0x01])
        

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
    print("pa!")