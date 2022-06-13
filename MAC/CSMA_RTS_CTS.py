#Disclaimer!!!
# CSMA with RTS/CTS written by Doğu Erkan Arkadaş, CSMA part is taken from the ad hoc library
# Apperantly the same timer cannot be called more than once so we need to create a new timer everytime we need one

import time, random, math
from enum import Enum
from sys import getsizeof
from pickle import FALSE, dumps
#from pickle import dumps as pickle_serialize
from threading import Timer
from adhoccomputing.Networking.MacProtocol.GenericMAC import GenericMac, GenericMacEventTypes
from adhoccomputing.Generics import Event, EventTypes, GenericMessageHeader,GenericMessage
import queue

# Message types that will be carried in eventcontent header
class MACLayerMessageTypes(Enum):
    DATA = "DATA"
    ACK = "ACK"
    RTS = "RTS"
    CTS = "CTS"
    
# MAC states for the algorithm
class MAC_States(Enum):
    IDLE = "IDLE"
    Contention ="Contention"
    CTS_pending = "CTS_pending"
    ACK_pending = "ACK_pending"
    Blocked ="Blocked"
    

class ComponentConfigurationParameters():
    pass

class MacCsmaRTS_CTS_ConfigurationParameters (ComponentConfigurationParameters):
    def __init__(self, slot_time = 0.05, NAV_RTS = 0.2, NAV_CTS = 0.15, NAV_DATA = 0.1, message_threshold=100, cca_threshold = -35):
        self.slot_time = slot_time
        self.NAV_RTS = NAV_RTS
        self.NAV_CTS = NAV_CTS
        self.NAV_DATA = NAV_DATA
        self.message_threshold=message_threshold
        self.cca_threshold = cca_threshold


class MacCsmaRTS_CTS(GenericMac):
    #Constructor
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None, sdr=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology, sdr)
    #def __init__(self, componentname, componentinstancenumber, configurationparameters:MacCsmaPPersistentConfigurationParameters, uhd=uhd):
        self.received_framequeue = queue.Queue(maxsize=10000)
        self.slot_time = configurationparameters.slot_time
        self.NAV_RTS = configurationparameters.NAV_RTS
        self.NAV_CTS = configurationparameters.NAV_CTS
        self.NAV_DATA = configurationparameters.NAV_DATA
        self.message_threshold=configurationparameters.message_threshold
        self.cca_threshold = configurationparameters.cca_threshold
        
        self.contention_backoff = 8
        self.initial_backoff = 2
        self.retry_max=4

    
    #on_init will be called from topo.start to initialize components
    def on_init(self, eventobj: Event):
        #initial back_off is 0
        self.back_off_counter =self.initial_backoff
        self.back_off_max = 4
        self.retrial_counter = 0
        self.STATE = MAC_States.IDLE
        
        self.Timer = Timer(self.NAV_CTS,self.Timer_func)
        #Statistic variables
        self.sent_DATA_counter = 0
        self.received_DATA_counter = 0
        self.sent_ACK_counter = 0
        self.received_ACK_counter = 0

        self.sent_RTS_counter = 0
        self.received_RTS_counter = 0
        self.received_CTS_counter = 0
        self.send_self(Event(self, GenericMacEventTypes.HANDLEMACFRAME, None))
        super().on_init(eventobj)  # required because of inheritence
        #print("Initialized", self.componentname, ":", self.componentinstancenumber)
   
    def Timer_func(self):
        self.contention_counter=0
        self.STATE = MAC_States.Contention

    def on_message_from_top(self, eventobj: Event):
        # put message in queue and try accessing the channel
        self.framequeue.put_nowait(eventobj)      

    def on_message_from_bottom(self, eventobj: Event):
        if eventobj.eventcontent.header.messagefrom==self.componentinstancenumber:
            pass
        else:    
            self.received_framequeue.put_nowait(eventobj)

    def handle_frame(self):
        #TODO: not a good solution put message in queue, schedule a future event to retry yhe first item in queueu    
        #print("handle_frame")
        #If we received frames from other nodes we must first check them
        if self.received_framequeue.qsize()>0:
            while self.received_framequeue.qsize()>0:
                eventobj = self.received_framequeue.get()
            evt = Event(self, EventTypes.MFRT, eventobj.eventcontent)
            self.Timer.cancel()
            if self.componentinstancenumber == eventobj.eventcontent.header.messageto:
                #Send different messages depending on which message came
                if(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.RTS):
                    print(f"Node{self.componentinstancenumber}: Sending CTS to {eventobj.eventcontent.header.messagefrom} ")
                    self.received_RTS_counter += 1
                    evt.eventcontent.header.messagetype = MACLayerMessageTypes.CTS   
                    evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                    evt.eventcontent.header.messagefrom = self.componentinstancenumber
                    evt.eventcontent.payload = None
                    self.STATE=MAC_States.Blocked
                    self.Timer =Timer(self.NAV_RTS,self.Timer_func)
                    self.Timer.start()
                    self.send_down(evt)  # Send the CTS
                
                elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.CTS):
                    print(f"Node{self.componentinstancenumber}: Sending DATA to {eventobj.eventcontent.header.messagefrom} ")
                    self.received_CTS_counter += 1
                    #Immediatly send the DATA message back
                    payload = self.framequeue.queue[0]
                    hdr = GenericMessageHeader(MACLayerMessageTypes.DATA,self.componentinstancenumber,eventobj.eventcontent.header.messagefrom)
                    DATA_message = GenericMessage(hdr, payload)
                    DATA_evt = Event(self, EventTypes.MFRT, DATA_message)                
                    self.STATE = MAC_States.ACK_pending
                    self.Timer =Timer(self.NAV_CTS,self.Timer_func)
                    self.Timer.start()
                    self.send_down(DATA_evt)

                elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.DATA):
                    print(f"Node{self.componentinstancenumber}: Sending ACK to {eventobj.eventcontent.header.messagefrom} ")
                    self.received_DATA_counter += 1
                    hdr = GenericMessageHeader(MACLayerMessageTypes.ACK,self.componentinstancenumber,eventobj.eventcontent.header.messagefrom)
                    ACK_message = GenericMessage(hdr, None)
                    ACK_evt = Event(self, EventTypes.MFRT, ACK_message)
                    self.send_down(ACK_evt)          
                    self.sent_ACK_counter += 1
                    self.Timer =Timer(self.NAV_DATA,self.Timer_func)
                    self.Timer.start()
                    evt = Event(self, EventTypes.MFRB, eventobj.eventcontent.payload.eventcontent)
                    self.send_up(evt)   

                elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.ACK):
                    print(f"Node{self.componentinstancenumber}: Received ACK from {eventobj.eventcontent.header.messagefrom} ")               
                    self.received_ACK_counter += 1
                    #Even if we are the one to receive the ACK we move on to the contention rather than idle
                    self.STATE=MAC_States.Contention
                    self.contention_counter=0
                    self.back_off_counter = self.initial_backoff
                    self.retrial_counter=0
                    #Deque the packet
                    if self.framequeue.qsize() > 0:
                        eventobj=self.framequeue.get()                

            #if the message was for another node
            else:                
                if(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.RTS):
                    print(f"Node{self.componentinstancenumber}: Received RTS_{eventobj.eventcontent.header.messagefrom}_{eventobj.eventcontent.header.messageto} ")
                    self.STATE=MAC_States.Blocked
                    self.Timer =Timer(self.NAV_RTS,self.Timer_func)
                    self.Timer.start()
                elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.CTS):
                    print(f"Node{self.componentinstancenumber}: Received CTS_{eventobj.eventcontent.header.messagefrom}_{eventobj.eventcontent.header.messageto} ")
                    self.STATE=MAC_States.Blocked
                    self.Timer =Timer(self.NAV_CTS,self.Timer_func)
                    self.Timer.start()
                elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.DATA):
                    print(f"Node{self.componentinstancenumber}: Received DATA_{eventobj.eventcontent.header.messagefrom}_{eventobj.eventcontent.header.messageto} ")     
                    self.STATE=MAC_States.Blocked
                    self.Timer =Timer(self.NAV_DATA,self.Timer_func)
                    self.Timer.start()
                elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.ACK):
                    self.STATE=MAC_States.Contention
                    self.contention_counter=0
                    print(f"Node{self.componentinstancenumber}: Received ACK_{eventobj.eventcontent.header.messagefrom}_{eventobj.eventcontent.header.messageto} ")
                    #If we just exited blocked state because of someone elses RTS/CTS do a special backoff
        elif self.STATE==MAC_States.Contention:
            if(self.contention_counter==0):
                print(f"Node{self.componentinstancenumber}, in contention")
                self.contention_selected=random.randint(0,math.pow(2,self.contention_backoff))
            if(self.contention_counter<self.contention_selected):
                self.contention_counter+=1
                time.sleep(self.slot_time)
            else:
                self.STATE=MAC_States.IDLE

        elif self.framequeue.qsize() > 0:
            if self.STATE==MAC_States.IDLE:
                #If we exceed the maximum retry count for a packet drop it and send the packet with -1 message_from to the top
                if self.retrial_counter > self.retry_max:                   
                    self.retrial_counter=0
                    eventobj=self.framequeue.get()
                    print(f"Node{self.componentinstancenumber}, Droping a packet destined for Node{eventobj.eventcontent.header.messageto} since max retry is reached ")
                    evt = Event(self, EventTypes.MFRB, eventobj.eventcontent)
                    evt.eventcontent.header.messagefrom = -1
                    self.send_up(evt)
                else:
                     #print("handle_frame", "queue not empty")
                    clearmi, powerdb  = self.sdrdev.ischannelclear(threshold=self.cca_threshold)
                    #print("Component:", self.componentinstancenumber, "clear mi=", clearmi, " Power=", powerdb)
                    if  clearmi == True:
                        #Wait DIFS then sense again
                        time.sleep(self.slot_time)
                        clearmi, powerdb  = self.sdrdev.ischannelclear(threshold=self.cca_threshold)
                        if  clearmi == True:                  
                            try:
                                #Peak at the foremost message and construct a RTS message
                                eventobj = self.framequeue.queue[0]
                                message_size = getsizeof(eventobj.eventcontent.payload)
                                print("Size of the message is", message_size, "Retry count: ",self.retrial_counter)
                                if(message_size>self.message_threshold):
                                    print(f"Node{self.componentinstancenumber}, Sending RTS to {eventobj.eventcontent.header.messageto} ")
                                    hdr = GenericMessageHeader(MACLayerMessageTypes.RTS,self.componentinstancenumber,eventobj.eventcontent.header.messageto)
                                    RTS_message = GenericMessage(hdr, None)
                                    RTS_evt = Event(self, EventTypes.MFRT, RTS_message)                                                       
                                    self.retrial_counter+=1
                                    self.back_off_counter = self.retrial_counter
                                    self.STATE = MAC_States.CTS_pending
                                    self.Timer =Timer(self.NAV_RTS +self.slot_time,self.Timer_func)
                                    self.Timer.start()
                                    self.send_down(RTS_evt)
                                else:
                                    print(f"Node{self.componentinstancenumber}: Sending DATA to {eventobj.eventcontent.header.messageto} ")
                                    hdr = GenericMessageHeader(MACLayerMessageTypes.DATA,self.componentinstancenumber,eventobj.eventcontent.header.messageto)                           
                                    DATA_message = GenericMessage(hdr, eventobj)
                                    DATA_evt = Event(self, EventTypes.MFRT, DATA_message)    
                                    self.retrial_counter+=1
                                    self.back_off_counter = self.retrial_counter
                                    self.STATE = MAC_States.ACK_pending
                                    self.Timer =Timer(self.NAV_CTS,self.Timer_func)
                                    self.Timer.start()
                                    self.send_down(DATA_evt)
                            except Exception as e:
                                print("Node",self.componentinstancenumber, " MacCsma handle_frame exception, ", e)
                        else:
                            if(self.back_off_counter<self.back_off_max):
                                self.retback_off_counterrialcnt = self.back_off_counter + 1
                            time.sleep(random.randrange(0,math.pow(2,self.back_off_counter))*self.slot_time)
                    else:
                        if(self.back_off_counter<self.back_off_max):
                            self.retback_off_counterrialcnt = self.back_off_counter + 1
                        time.sleep(random.randrange(0,math.pow(2,self.back_off_counter))*self.slot_time)
                                   
        else:
            pass           
        time.sleep(self.slot_time/10) # TODO: Think about this otherwise we will only do cca
        self.send_self(Event(self, GenericMacEventTypes.HANDLEMACFRAME, None)) #Continuously trigger handle_frame