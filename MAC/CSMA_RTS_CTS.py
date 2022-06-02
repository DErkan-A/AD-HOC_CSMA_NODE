#Disclaimer!!!
# CSMA with RTS/CTS written by Doğu Erkan Arkadaş, CSMA part is taken from the ad hoc library

import time, random, math
from enum import Enum
from pickle import FALSE
#from pickle import dumps as pickle_serialize
from threading import Timer
from adhoccomputing.Networking.MacProtocol.GenericMAC import GenericMac, GenericMacEventTypes
from adhoccomputing.Generics import Event, EventTypes, GenericMessageHeader,GenericMessage

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
    def __init__(self, slot_time = 0.001, NAV_RTS = 0.010, NAV_CTS = 0.080, NAV_DATA = 0.003, cca_threshold = -35):
        self.slot_time = slot_time
        self.NAV_RTS = NAV_RTS
        self.NAV_CTS = NAV_CTS
        self.NAV_DATA = NAV_DATA
        self.cca_threshold = cca_threshold


class MacCsmaRTS_CTS(GenericMac):
    #Constructor
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None, uhd=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology, uhd)
    #def __init__(self, componentname, componentinstancenumber, configurationparameters:MacCsmaPPersistentConfigurationParameters, uhd=uhd):
        self.p = configurationparameters.p
        self.slot_time = configurationparameters.slot_time
        self.NAV_RTS = configurationparameters.NAV_RTS
        self.NAV_CTS = configurationparameters.NAV_CTS
        self.NAV_DATA = configurationparameters.NAV_DATA
        self.cca_threshold = configurationparameters.cca_threshold
        
        self.contention_backoff = 3
        self.initial_backoff = 0
        self.retry_max=4

    
    #on_init will be called from topo.start to initialize components
    def on_init(self, eventobj: Event):
        #initial back_off is 0
        self.back_off_counter =self.initial_backoff
        self.retrial_counter = 0
        self.STATE = MAC_States.IDLE
        
        self.RTS_timer = Timer(self.NAV_RTS,self.Timer_func())
        self.CTS_timer = Timer(self.NAV_CTS,self.Timer_func())
        self.DATA_timer = Timer(self.NAV_DATA,self.Timer_func())
        #Statistic variables
        self.sent_DATA_counter = 0
        self.received_DATA_counter = 0
        self.sent_ACK_counter = 0
        self.received_ACK_counter = 0

        self.sent_RTS_counter = 0
        self.received_RTS_counter = 0
        self.received_CTS_counter = 0
        super().on_init(eventobj)  # required because of inheritence
        #print("Initialized", self.componentname, ":", self.componentinstancenumber)
   
    def Timer_func(self):
        self.STATE = MAC_States.Contention
        
    def Cancel_Timer(self):
        self.RTS_timer.cancel()
        self.CTS_timer.cancel()
        self.DATA_timer.cancel()
        
    def on_message_from_bottom(self, eventobj: Event):
        evt = Event(self, EventTypes.MFRT, eventobj.eventcontent)
        #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom}: {eventobj.eventcontent.payload}")
        
        #If the message was targetting this node        
        if self.componentinstancenumber == eventobj.eventcontent.header.messageto:
            self.Cancel_Timer()
            #Generate and send the ACK message (paylod is the same as original message) to the sender
            if(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.RTS):
                self.received_RTS_counter += 1
                #Print the received DATA message content
                #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} {eventobj.eventcontent.payload}")
                evt.eventcontent.header.messagetype = MACLayerMessageTypes.CTS   
                evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                evt.eventcontent.header.messagefrom = self.componentinstancenumber
                evt.eventcontent.payload = None
                self.STATE=MAC_States.Blocked
                self.RTS_timer.start()
                self.send_down(evt)  # Send the CTS
                
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.CTS):
                self.received_CTS_counter += 1
                #Immediatly send the DATA message back
                payload = self.framequeue.queue[0]
                hdr = GenericMessageHeader(MACLayerMessageTypes.DATA,self.componentinstancenumber,eventobj.eventcontent.header.messagefrom)
                DATA_message = GenericMessage(hdr, payload)
                DATA_evt = Event(self, EventTypes.MFRT, DATA_message)                
                self.STATE == MAC_States.ACK_pending
                self.CTS_timer.start()
                self.send_down(DATA_evt)

            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.DATA):
                self.received_DATA_counter += 1
                #Print the received DATA message content
                #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} {eventobj.eventcontent.payload}")
                hdr = GenericMessageHeader(MACLayerMessageTypes.ACK,self.componentinstancenumber,eventobj.eventcontent.header.messagefrom)
                ACK_message = GenericMessage(hdr, None)
                ACK_evt = Event(self, EventTypes.MFRT, ACK_message)
                self.send_down(ACK_evt)          
                self.sent_ack_counter += 1
                self.send_up(eventobj.eventcontent.payload)   

            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.ACK):                
                self.received_ACK_counter += 1
                #self.STATE.ACK_received
                #Even if we are the one to receive the ACK we move on to the contention rather than idle
                self.STATE==MAC_States.Contention
                self.back_off_counter = self.initial_backoff
                self.retrial_counter=0
                self.framequeue.get()


        #if the message was for another node
        else:
            if(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.RTS):
                self.STATE=MAC_States.Blocked
                self.RTS_timer.start()
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.CTS):
                self.STATE=MAC_States.Blocked
                self.CTS_timer.start()
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.DATA):     
                self.STATE=MAC_States.Blocked
                self.DATA_timer.start()
            elif(eventobj.eventcontent.header.messagetype == MACLayerMessageTypes.ACK):
                pass

    def handle_frame(self):
        #TODO: not a good solution put message in queue, schedule a future event to retry yhe first item in queueu    
        #print("handle_frame")
            #If we just exited blocked state because of someone elses RTS/CTS do a special backoff
        if self.STATE==MAC_States.Contention:
            time.sleep(random.randrange(0,math.pow(2,self.contention_backoff))*self.slot_time)
            self.STATE=MAC_States.IDLE
            
        if self.framequeue.qsize() > 0:
            if self.STATE==MAC_States.IDLE:
                #If we exceed the maximum retry count for a packet drop it and send the packet with -1 message_from to the top
                if self.retrial_counter > self.retry_max:
                    self.retrial_counter=0
                    eventobj=self.framequeue.get()
                    evt = Event(self, EventTypes.MFRB, eventobj.eventcontent)
                    evt.eventcontent.header.messagefrom = -1
                    self.send_up(evt)
                else:    
                    #print("handle_frame", "queue not empty")
                    clearmi, powerdb  = self.ahcuhd.ischannelclear(threshold=self.cca_threshold)
                    #print("Component:", self.componentinstancenumber, "clear mi=", clearmi, " Power=", powerdb)
                    if  clearmi == True:
                        #Wait DIFS then sense again
                        time.sleep(self.slot_time)
                        clearmi, powerdb  = self.ahcuhd.ischannelclear(threshold=self.cca_threshold)
                        if  clearmi == True:
                            try:
                                #Peak at the foremost message and construct a RTS message
                                eventobj = self.framequeue.queue[0]
                                hdr = GenericMessageHeader(MACLayerMessageTypes.RTS,self.componentinstancenumber,eventobj.messageto)
                                RTS_message = GenericMessage(hdr, None)
                                RTS_evt = Event(self, EventTypes.MFRT, RTS_message)
                                self.send_down(RTS_evt)
                                self.retrial_counter+=1
                                self.back_off_counter = self.retrial_counter
                                self.STATE = MAC_States.CTS_pending
                                self.DATA_timer.start()
                            except Exception as e:
                                print("MacCsma handle_frame exception, ", e)
                        else:
                            if(self.back_off_counter<8):
                                self.retback_off_counterrialcnt = self.back_off_counter + 1
                            time.sleep(random.randrange(0,math.pow(2,self.back_off_counter))*self.slot_time)
                    else:
                        if(self.back_off_counter<8):
                            self.retback_off_counterrialcnt = self.back_off_counter + 1
                        time.sleep(random.randrange(0,math.pow(2,self.back_off_counter))*self.slot_time)
                        #print("Busy")
                    
            #IF ack is received take the packet off the queue    
            #elif self.STATE == MAC_States.ACK_received:
                #Even if we are the one to receive the ACK we move on to the contention rather than idle
                #self.STATE==MAC_States.Contention
                #self.back_off_counter = self.initial_backoff
                #self.retrial_counter=0
                #self.framequeue.get()
                
        else:
            #print("Queue size", self.framequeue.qsize())            
            pass
        time.sleep(0.00001) # TODO: Think about this otherwise we will only do cca
        self.send_self(Event(self, GenericMacEventTypes.HANDLEMACFRAME, None)) #Continuously trigger handle_frame
