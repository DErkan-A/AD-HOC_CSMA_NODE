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
from adhoccomputing.Networking.MacProtocol.CSMA import MacCsmaPPersistent, MacCsmaPPersistentConfigurationParameters
from adhoccomputing.Generics import Event, EventTypes, ConnectorTypes, GenericMessageHeader,GenericMessage

RTS_CTS_mutex = Lock()

# Message types that will be carried in eventcontent header
class MACLayerMessageTypes(Enum):
    DATA = "DATA"
    ACK = "ACK"
    RTS = "RTS"
    CTS = "CTS"

class MacCsmaRTS_CTS_PPersistentConfigurationParameters (MacCsmaPPersistentConfigurationParameters):
    def __init__(self, p, RTS_sleep_amount, CTS_sleep_amount):
        super().__init__(p)
        self.CTS_sleep_amount = CTS_sleep_amount
        self.RTS_sleep_amount = RTS_sleep_amount


class MacCsmaRTS_CTS_PPersistent(MacCsmaPPersistent):
    #Constructor
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None, uhd=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology, uhd)
    #def __init__(self, componentname, componentinstancenumber, configurationparameters:MacCsmaPPersistentConfigurationParameters, uhd=uhd):
    #    super().__init__(componentname, componentinstancenumber, uhd)
        self.RTS_sleep_amount = configurationparameters.RTS_sleep_amount
        self.CTS_sleep_amount = configurationparameters.CTS_sleep_amount

    
    #on_init will be called from topo.start to initialize components
    def on_init(self, eventobj: Event):
        self.back_off_constant = 1

        self.sent_data_counter = 0
        self.received_data_counter = 0
        self.sent_ack_counter = 0
        self.received_ack_counter = 0

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
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.DATA):
                self.received_data_counter += 1
                #Print the received DATA message content
                #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} {eventobj.eventcontent.payload}")
                evt.eventcontent.header.messagetype = MACLayerMessageTypes.ACK   
                evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                evt.eventcontent.header.messagefrom = self.componentinstancenumber
                # Send the DATA message payload to the upper layer
                self.send_up(eventobj.eventcontent.payload)               
                evt.eventcontent.payload = None
                self.send_down(evt)  # Send the ACK
                
                self.sent_ack_counter += 1

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
        self.send_down(Event(self, EventTypes.MFRT, eventobj.eventcontent))         
