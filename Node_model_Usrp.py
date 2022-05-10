#Disclaimer!!!
#Written by Doğu Erkan Arkadaş by modifying the physical layer tests from https://github.com/cengwins/ahc_v2_tests/tree/main/PhysicalLayers
#About half of the functions are not majorly changed

import os
import sys
import time, random, math
from enum import Enum
from pickle import FALSE



from adhoccomputing.GenericModel import GenericModel
from adhoccomputing.Generics import Event, EventTypes, ConnectorTypes, GenericMessageHeader,GenericMessage
from adhoccomputing.Experimentation.Topology import Topology
from adhoccomputing.Networking.PhysicalLayer.UsrpB210OfdmFlexFramePhy import  UsrpB210OfdmFlexFramePhy
from adhoccomputing.Networking.MacProtocol.CSMA import MacCsmaPPersistent, MacCsmaPPersistentConfigurationParameters

#registry = ComponentRegistry()
#from ahc.Channels.Channels import FIFOBroadcastPerfectChannel
#from ahc.EttusUsrp.UhdUtils import AhcUhdUtils

#framers = FramerObjects()


# Message types that will be carried in eventcontent header
class ApplicationLayerMessageTypes(Enum):
    DATA = "DATA"
    ACK = "ACK"

#Application level new event to generate packets from the main thread, also needs a new handler
class UsrpApplicationLayerEventTypes(Enum):
    STARTBROADCAST = "startbroadcast"

#Our aplication layer for nodes, basically all the logic happens here
class UsrpApplicationLayer(GenericModel):
    def on_init(self, eventobj: Event):
        self.sent_data_counter = 0
        self.received_data_counter = 0
        self.sent_ack_counter = 0
        self.received_ack_counter = 0
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology)
        #new event handler for packet generation, same otherwise
        self.eventhandlers[UsrpApplicationLayerEventTypes.STARTBROADCAST] = self.on_startbroadcast

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
                print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} {eventobj.eventcontent.payload}")
                evt.eventcontent.header.messagetype = ApplicationLayerMessageTypes.ACK   
                evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                evt.eventcontent.header.messagefrom = self.componentinstancenumber
                evt.eventcontent.payload =eventobj.eventcontent.payload
                self.send_down(evt)  # Send the ACK
                self.sent_ack_counter += 1
            #Print the message content if you receive an ACK message    
            elif(eventobj.eventcontent.header.messagetype == ApplicationLayerMessageTypes.ACK):
                self.received_ack_counter += 1
                print(f"Node.{self.componentinstancenumber}, received ACK from Node.{eventobj.eventcontent.header.messagefrom} For: {eventobj.eventcontent.payload}")

    #handler function for message generation event
    def on_startbroadcast(self, eventobj: Event):
        #select a random destination node that is not yourself
        destination_node = random.randint(0,3)
        while destination_node == self.componentinstancenumber:
            destination_node = random.randint(0,3)
        hdr = GenericMessageHeader(ApplicationLayerMessageTypes.DATA,self.componentinstancenumber , destination_node)
        self.sent_data_counter += 1       
        payload = "Message" + str(self.sent_data_counter) + " from NODE-" + str(self.componentinstancenumber)
        broadcastmessage = GenericMessage(hdr, payload)
        evt = Event(self, EventTypes.MFRT, broadcastmessage)
        print(f"I am Node.{self.componentinstancenumber}, sending a message to Node.{hdr.messageto}")
        # time.sleep(3)
        self.send_down(evt)
        #print("Starting broadcast")
    
         
class UsrpNode(GenericModel):
    def on_init(self, eventobj: Event):
        pass
    
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology)
        # SUBCOMPONENTS
        
        #Configure the p-persisten MAC
        macconfig = MacCsmaPPersistentConfigurationParameters(0.5)
        
        self.appl = UsrpApplicationLayer("UsrpApplicationLayer", componentinstancenumber, topology=topology)
        self.phy = UsrpB210OfdmFlexFramePhy("UsrpB210OfdmFlexFramePhy", componentinstancenumber, topology=topology)
        self.mac = MacCsmaPPersistent("MacCsmaPPersistent", componentinstancenumber,  configurationparameters=macconfig, uhd=self.phy.ahcuhd,topology=topology)
        
        self.components.append(self.appl)
        self.components.append(self.phy)
        self.components.append(self.mac)

        # CONNECTIONS AMONG SUBCOMPONENTS
        # Connections are simple. From top to bottom NODE-> APP -> MAC -> Phy -> NODE
        self.appl.connect_me_to_component(ConnectorTypes.UP, self) #Not required if nodemodel will do nothing
        self.appl.connect_me_to_component(ConnectorTypes.DOWN, self.mac)
        
        self.mac.connect_me_to_component(ConnectorTypes.UP, self.appl)
        self.mac.connect_me_to_component(ConnectorTypes.DOWN, self.phy)
        
        # Connect the bottom component to the composite component....
        self.phy.connect_me_to_component(ConnectorTypes.UP, self.mac)
        self.phy.connect_me_to_component(ConnectorTypes.DOWN, self)
        
        # self.phy.connect_me_to_component(ConnectorTypes.DOWN, self)
        # self.connect_me_to_component(ConnectorTypes.DOWN, self.appl)
    
        

def main():
    topo = Topology()
# Note that the topology has to specific: usrp winslab_b210_0 is run by instance 0 of the component
# Therefore, the usrps have to have names winslab_b210_x where x \in (0 to nodecount-1)
    topo.construct_winslab_topology_without_channels(4, UsrpNode)
  # topo.construct_winslab_topology_with_channels(2, UsrpNode, FIFOBroadcastPerfectChannel)
  
  # time.sleep(1)
  # topo.nodes[0].send_self(Event(topo.nodes[0], UsrpNodeEventTypes.STARTBROADCAST, None))

    topo.start()
    i = 0
    #test for only 1 random node sending a message to another random node with sufficent waiting between messages, this basically tests failure rate
    print("Reporting the overall statistics")
    print("Testing channel failure rate by sending messages 1 by 1 with time inbetween")
    while(i < 100):
        random_node = random.randint(0,3)
        topo.nodes[random_node].appl.send_self(Event(topo.nodes[random_node], UsrpApplicationLayerEventTypes.STARTBROADCAST, None))
        time.sleep(0.1)
        i = i + 1
    time.sleep(1)
    total_data_sent = 0
    total_ack_sent = 0
    total_data_received = 0
    total_ack_received = 0
    for node in range(4):
        node = topo.nodes[node].appl
        total_data_sent +=sent_data_counter
        total_ack_sent +=sent_ack_counter
        total_data_received += received_data_counter
        total_ack_received +=received_ack_counter
        print(f"Node.{node.componentinstancenumber}, sent.{node.sent_data_counter} Data, received.{node.received_data_counter} Data, ACKed.{node.sent_ack_counter}, received.{node.received_ack_counter} ACKs")

    data_success_rate = total_data_received / total_data_sent
    ack_success_rate = total_ack_received/total_ack_sent 
    total_success_rate = (total_data_received +  total_ack_received)/ (total_data_sent+total_ack_sent)
    print("Data message success rate is:",data_success_rate, " ACK message success rate is:",ack_success_rate, " Total success rate is:",total_success_rate)
if __name__ == "__main__":
    main()
