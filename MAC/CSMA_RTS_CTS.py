#Disclaimer!!!
# CSMA with RTS/CTS written by Doğu Erkan Arkadaş, CSMA part is taken from the ad hoc library

import os
import sys
import time, random, math
from enum import Enum
from pickle import FALSE
#from pickle import dumps as pickle_serialize
from threading import Lock
from adhoccomputing.Generics import Event, EventTypes
from adhoccomputing.Networking.MacProtocol.GenericMAC import GenericMac, GenericMacEventTypes
from adhoccomputing.Generics import Event, EventTypes, ConnectorTypes, GenericMessageHeader,GenericMessage

#Lock when you hear another nodes RTS_CTS
RTS_CTS_mutex = Lock()
#Lock for when you are sending to only send 1 message at a time, starts locked
my_CTS_mutex = Lock()
my_CTS_mutex.acquire()
my_ACK_mutex = Lock()
my_ACK_mutex.acquire()
# Message types that will be carried in eventcontent header
class MACLayerMessageTypes(Enum):
    DATA = "DATA"
    ACK = "ACK"
    RTS = "RTS"
    CTS = "CTS"

class ComponentConfigurationParameters():
    pass    

class MacCsmaRTS_CTS_PPersistentConfigurationParameters (ComponentConfigurationParameters):
    def __init__(self, p, RTS_sleep_amount, CTS_sleep_amount):
        self.p=p
        self.CTS_sleep_amount = CTS_sleep_amount
        self.RTS_sleep_amount = RTS_sleep_amount


class MacCsmaRTS_CTS_PPersistent(GenericMac):
    #Constructor
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None, uhd=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology, uhd)
    #def __init__(self, componentname, componentinstancenumber, configurationparameters:MacCsmaPPersistentConfigurationParameters, uhd=uhd):
        self.p = configurationparameters.p
        self.RTS_sleep_amount = configurationparameters.RTS_sleep_amount
        self.CTS_sleep_amount = configurationparameters.CTS_sleep_amount

    
    #on_init will be called from topo.start to initialize components
    def on_init(self, eventobj: Event):
        self.back_off_counter =2

        self.sent_DATA_counter = 0
        self.received_DATA_counter = 0
        self.sent_ACK_counter = 0
        self.received_ACK_counter = 0

        self.sent_RTS_counter = 0
        self.received_RTS_counter = 0
        self.sent_CTS_counter = 0
        self.received_CTS_counter = 0
        super().on_init(eventobj)  # required because of inheritence
        #print("Initialized", self.componentname, ":", self.componentinstancenumber)

    def on_message_from_bottom(self, eventobj: Event):
        evt = Event(self, EventTypes.MFRT, eventobj.eventcontent)
        #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom}: {eventobj.eventcontent.payload}")
        #If the message was targetting this node        
        if self.componentinstancenumber == eventobj.eventcontent.header.messageto:
            #Generate and send the ACK message (paylod is the same as original message) to the sender
            if(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.RTS):
                self.received_RTS_counter += 1
                #Print the received DATA message content
                #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} {eventobj.eventcontent.payload}")
                evt.eventcontent.header.messagetype = MACLayerMessageTypes.CTS   
                evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                evt.eventcontent.header.messagefrom = self.componentinstancenumber
                evt.eventcontent.payload = None
                self.send_down(evt)  # Send the CTS
                self.sent_CTS_counter += 1
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.CTS):
                self.received_CTS_counter += 1
                #Release the my_CTS mutex so that DATA message can be sent
                my_CTS_mutex.release()
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.DATA):
                self.received_DATA_counter += 1
                #Print the received DATA message content
                #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} {eventobj.eventcontent.payload}")
                evt.eventcontent.header.messagetype = MACLayerMessageTypes.ACK   
                evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                evt.eventcontent.header.messagefrom = self.componentinstancenumber
                # Send the DATA message payload to the upper layer
                self.send_up(eventobj.eventcontent.payload)               
                evt.eventcontent.payload = None
                self.framequeue.put_nowait(RTS_evt)
                self.handle_frame()  # Send the ACK                
                self.sent_ack_counter += 1
                my_CTS_mutex.release()
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.ACK):
                self.received_ACK_counter += 1
                #Release the my_CTS mutex so that DATA message can be sent
                my_ACK_mutex.release()    

        #if the message was for another node
        else:
            if(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.RTS):
                RTS_CTS_mutex.acquire()
                time.sleep(self.RTS_sleep_amount)
                RTS_CTS_mutex.release()
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.CTS):
                RTS_CTS_mutex.acquire() 
                time.sleep(self.CTS_sleep_amount)
                RTS_CTS_mutex.release()   
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.DATA):     
                print("I am seeing a DATA signal RTS and CTS failed")
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.ACK):
                print("I am seeing ACK signal RTS and CTS failed") 
                
    def on_message_from_top(self, eventobj: Event):
        #NO need for RTS_CTS mutex here since it is already checked in handle_frame       
        hdr = GenericMessageHeader(MACLayerMessageTypes.RTS,self.componentinstancenumber,eventobj.messageto)
        RTS_message = GenericMessage(hdr, None)
        RTS_evt = Event(self, EventTypes.MFRT, RTS_message)
        self.framequeue.put_nowait(RTS_evt)
        self.handle_frame()
        my_CTS_mutex.acquire()
        hdr = GenericMessageHeader(MACLayerMessageTypes.DATA,self.componentinstancenumber,eventobj.messageto)
        DATA_message = GenericMessage(hdr, eventobj)
        DATA_evt = Event(self, EventTypes.MFRT, DATA_message)
        self.framequeue.put_nowait(DATA_evt)
        self.handle_frame()


    def handle_frame(self):
        #TODO: not a good solution put message in queue, schedule a future event to retry yhe first item in queueu    
        #print("handle_frame")
        if self.framequeue.qsize() > 0:
            RTS_CTS_mutex.acquire() 
            #print("handle_frame", "queue not empty")
            randval = random.random()
            if randval < self.p: # TODO: Check if correct
                clearmi, powerdb  = self.ahcuhd.ischannelclear(threshold=-35)
                #print("Component:", self.componentinstancenumber, "clear mi=", clearmi, " Power=", powerdb)
                if  clearmi == True:
                    try:
                        eventobj = self.framequeue.get()
                        evt = Event(self, EventTypes.MFRT, eventobj.eventcontent)
                        self.send_down(evt)
                        self.back_off_counter = 2
                    except Exception as e:
                        print("MacCsmaPPersistent handle_frame exception, ", e)
                else:
                    if(self.back_off_counter<8):
                        self.retback_off_counterrialcnt = self.back_off_counter + 1
                    time.sleep(random.randrange(0,math.pow(2,self.back_off_counter))*0.001)
                    self.send_self(Event(self, GenericMacEventTypes.HANDLEMACFRAME, None)) #Continuously trigger handle_frame    
                    #print("Busy")
            RTS_CTS_mutex.release()             
        else:
            #print("Queue size", self.framequeue.qsize())
            pass
        
             
