#Disclaimer!!!
# CSMA with RTS/CTS written by Doğu Erkan Arkadaş, CSMA part is taken from the ad hoc library

import os
import sys
import time, random, math
from enum import Enum
from pickle import FALSE



from adhoccomputing.GenericModel import GenericModel
from adhoccomputing.Generics import Event, EventTypes, ConnectorTypes, GenericMessageHeader,GenericMessage
from adhoccomputing.Networking.PhysicalLayer.UsrpB210OfdmFlexFramePhy import  UsrpB210OfdmFlexFramePhy
from adhoccomputing.Networking.MacProtocol.CSMA import MacCsmaPPersistent, MacCsmaPPersistentConfigurationParameters

#registry = ComponentRegistry()
#from ahc.Channels.Channels import FIFOBroadcastPerfectChannel
#from ahc.EttusUsrp.UhdUtils import AhcUhdUtils

#framers = FramerObjects()


# Message types that will be carried in eventcontent header
class MACLayerMessageTypes(Enum):
    DATA = "DATA"
    ACK = "ACK"
    RTS = "RTS"
    CTS = "CTS"

#Our aplication layer for nodes, basically all the logic happens here
class CSMA_RTS_CTS(GenericModel):
    def on_init(self, eventobj: Event):
        self.sent_data_counter = 0
        self.received_data_counter = 0
        self.sent_ack_counter = 0
        self.received_ack_counter = 0
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology)
        #Might include new parts to the init
        
    def on_message_from_top(self, eventobj: Event):
        self.send_down(Event(self, EventTypes.MFRT, eventobj.eventcontent))
    
    def on_message_from_bottom(self, eventobj: Event):
        evt = Event(self, EventTypes.MFRT, eventobj.eventcontent)
        #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom}: {eventobj.eventcontent.payload}")
        #If the message was targetting this node        
        if self.componentinstancenumber == eventobj.eventcontent.header.messageto:
            #Generate and send the ACK message (paylod is the same as original message) to the sender
            if(eventobj.eventcontent.header.messagetype == ApplicationLayerMessageTypes.DATA):
                self.received_data_counter += 1
                #Print the received DATA message content
                #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} {eventobj.eventcontent.payload}")
                evt.eventcontent.header.messagetype = ApplicationLayerMessageTypes.ACK   
                evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                evt.eventcontent.header.messagefrom = self.componentinstancenumber
                evt.eventcontent.payload =eventobj.eventcontent.payload
                self.send_down(evt)  # Send the ACK
                self.sent_ack_counter += 1
            #Print the message content if you receive an ACK message and increase the counter   
            elif(eventobj.eventcontent.header.messagetype == ApplicationLayerMessageTypes.ACK):
                self.received_ack_counter += 1
                #print(f"Node.{self.componentinstancenumber}, received ACK from Node.{eventobj.eventcontent.header.messagefrom} For: {eventobj.eventcontent.payload}")

    #handler function for message generation event
    def on_startbroadcast(self, eventobj: Event):
        #select a random destination node that is not yourself
        destination_node = random.randint(0,3)
        while destination_node == self.componentinstancenumber:
            destination_node = random.randint(0,3)
        hdr = GenericMessageHeader(ApplicationLayerMessageTypes.DATA,self.componentinstancenumber , destination_node)
        self.sent_data_counter += 1       
        payload = "Message" + str(self.sent_data_counter) + " from NODE-" + str(self.componentinstancenumber)
        #print("size of payload is:",sys.getsizeof(payload))
        broadcastmessage = GenericMessage(hdr, payload)
        evt = Event(self, EventTypes.MFRT, broadcastmessage)
        #print(f"I am Node.{self.componentinstancenumber}, sending a message to Node.{hdr.messageto}")
        self.send_down(evt)
