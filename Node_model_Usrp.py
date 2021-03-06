#Disclaimer!!!
#Written by Doğu Erkan Arkadaş by modifying the physical layer tests from https://github.com/cengwins/ahc_v2_tests/tree/main/PhysicalLayers
#About half of the functions are not majorly changed

import os
import sys
import time, random, math
from enum import Enum
from pickle import FALSE
from MAC.CSMA_RTS_CTS import MacCsmaRTS_CTS_ConfigurationParameters,MacCsmaRTS_CTS
from adhoccomputing.Networking.MacProtocol.CSMA import MacCsmaPPersistent, MacCsmaPPersistentConfigurationParameters

from adhoccomputing.GenericModel import GenericModel
from adhoccomputing.Generics import *
from adhoccomputing.Experimentation.Topology import Topology
from adhoccomputing.Networking.PhysicalLayer.UsrpB210OfdmFlexFramePhy import  UsrpB210OfdmFlexFramePhy
from adhoccomputing.Networking.MacProtocol.CSMA import MacCsmaPPersistent, MacCsmaPPersistentConfigurationParameters
from adhoccomputing.Networking.LogicalChannels.GenericChannel import FIFOBroadcastPerfectChannel

number_of_nodes = 4

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
        self.received_ack_counter=0
        #Lists for DATA and ACK to not count duplicate packets
        self.ACK_sequence_list = []
        self.Data_sequence_list = []
        for i in range(number_of_nodes):
            self.Data_sequence_list.append(-1)
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology)
        #new event handler for packet generation, same otherwise
        self.eventhandlers[UsrpApplicationLayerEventTypes.STARTBROADCAST] = self.on_startbroadcast

    def on_message_from_top(self, eventobj: Event):
        self.send_down(Event(self, EventTypes.MFRT, eventobj.eventcontent))
    
    def on_message_from_bottom(self, eventobj: Event):
        evt = Event(self, EventTypes.MFRT, eventobj.eventcontent)

        #Check if the message was for this node (unnecessary when using CSMA with RTS/CTS)
        if self.componentinstancenumber == eventobj.eventcontent.header.messageto:
            #Generate and send the ACK message to reply
            if(eventobj.eventcontent.header.messagetype == ApplicationLayerMessageTypes.DATA):
                if(self.Data_sequence_list[eventobj.eventcontent.header.messagefrom]<eventobj.eventcontent.header.sequencenumber):
                    self.Data_sequence_list[eventobj.eventcontent.header.messagefrom]=eventobj.eventcontent.header.sequencenumber
                    self.received_data_counter += 1
                #Print the received DATA message content
                #print(f"Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} {eventobj.eventcontent.payload}")
                evt.eventcontent.header.messagetype = ApplicationLayerMessageTypes.ACK   
                evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                evt.eventcontent.header.messagefrom = self.componentinstancenumber
                evt.eventcontent.payload = "ACK_MSG"
                self.send_down(evt)  # Send the ACK
            #Count the ACK messages    
            elif(eventobj.eventcontent.header.messagetype == ApplicationLayerMessageTypes.ACK):
                #check if the ack is duplicate for not
                if self.ACK_sequence_list [eventobj.eventcontent.header.sequencenumber]==False:
                    self.ACK_sequence_list [eventobj.eventcontent.header.sequencenumber]=True
                    self.received_ack_counter += 1
                #print(f"Node.{self.componentinstancenumber}, received ACK from Node.{eventobj.eventcontent.header.messagefrom} For: {eventobj.eventcontent.payload}")
            #IF an unidentified message comes print for feedback    
            else:
                print(f"Unidentified message type")  

    #handler function for message generation event
    def on_startbroadcast(self, eventobj: Event):
        #select a random destination node that is not yourself
        destination_node = random.randint(0,number_of_nodes-1)
        while destination_node == self.componentinstancenumber:
            destination_node = random.randint(0,number_of_nodes-1)
        #Create the packet    
        hdr = GenericMessageHeader(ApplicationLayerMessageTypes.DATA,self.componentinstancenumber , destination_node,sequencenumber=self.sent_data_counter)
        self.sent_data_counter += 1
        #Add entry for the ACK of this packet to come
        self.ACK_sequence_list.append(False)
        payload = "Message" + str(self.sent_data_counter) + " from NODE-" + str(self.componentinstancenumber) + "PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING"
        payload = payload + "PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING"
        #print("size of payload is:",sys.getsizeof(payload))
        broadcastmessage = GenericMessage(hdr, payload)
        evt = Event(self, EventTypes.MFRT, broadcastmessage)
        #print(f"I am Node.{self.componentinstancenumber}, sending a message to Node.{hdr.messageto}")
        self.send_down(evt)
    
         
class UsrpNode(GenericModel):
    def on_init(self, eventobj: Event):
        super().on_init(eventobj)
    
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology)
        # SUBCOMPONENTS
        
        #Configure the p-persisten MAC
        #macconfig = MacCsmaPPersistentConfigurationParameters(0.5,-51)
        macconfig = MacCsmaRTS_CTS_ConfigurationParameters(cca_threshold=-51,message_threshold=10000)
        sdrconfig = SDRConfiguration(freq =2484000000.0, bandwidth = 20000000, chan = 0, hw_tx_gain = 76, hw_rx_gain = 20, sw_tx_gain = -12.0)

        self.appl = UsrpApplicationLayer("UsrpApplicationLayer", componentinstancenumber, topology=topology)
        #self.phy = UsrpB210OfdmFlexFramePhy("UsrpB210OfdmFlexFramePhy", componentinstancenumber, topology=topology)
        self.phy = UsrpB210OfdmFlexFramePhy("UsrpB210OfdmFlexFramePhy", componentinstancenumber,usrpconfig=sdrconfig, topology=topology)
        #self.mac = MacCsmaPPersistent("MacCsmaPPersistent", componentinstancenumber,  configurationparameters=macconfig, sdr=self.phy.sdrdev,topology=topology)
        self.mac = MacCsmaRTS_CTS("MacCsmaPPersistent", componentinstancenumber,  configurationparameters=macconfig, sdr=self.phy.sdrdev,topology=topology)
        
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

#wait_time is waiting time between packet scheduling, number_of_messages is the total number of message that will be sent  
def run_test(my_topology, wait_time, number_of_nodes, number_of_messages):
    print("Testing with inter frame waiting time:",wait_time, " number of nodes",number_of_nodes," number of messages:",number_of_messages)
    i = 0
    #Tests messages between random nodes, messages are sent through the application with given wait_time inbetween
    print("Reporting the overall statistics")
    start_time=time.time()
    while(i < number_of_messages):
        random_node = random.randint(0,number_of_nodes-1)
        my_topology.nodes[random_node].appl.send_self(Event(my_topology.nodes[random_node], UsrpApplicationLayerEventTypes.STARTBROADCAST, None))
        time.sleep(wait_time)
        i = i + 1
    #Don't stop untill all the mac layers finished sending everything    
    running_flag=True
    while running_flag:
        time.sleep(1)
        running_flag=False
        for i in range(number_of_nodes):
            if my_topology.nodes[i].mac.framequeue.qsize()>0:
                running_flag=True
    #Calculate and print various statistics of the test            
    run_time=time.time()-start_time
    total_data_sent = 0
    total_ack_sent = 0
    total_data_received = 0
    total_ack_received = 0
    for node in range(number_of_nodes):
        node = my_topology.nodes[node].appl
        total_data_sent +=node.sent_data_counter
        total_ack_sent +=node.received_data_counter
        total_data_received += node.received_data_counter
        total_ack_received +=node.received_ack_counter
        print(f"Node.{node.componentinstancenumber}, sent.{node.sent_data_counter} Data, received.{node.received_data_counter} Data, ACKed.{node.received_data_counter}, received.{node.received_ack_counter} ACKs")

    data_fail_rate = 1-(total_data_received / total_data_sent)
    ack_fail_rate = 1-(total_ack_received/total_ack_sent) 
    total_fail_rate = 1-((total_data_received +  total_ack_received)/ (total_data_sent+total_ack_sent))
    total_successfull_transmissions = total_ack_received/total_data_sent
    example_Data_payload="Message10 from NODE-1" + "PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING" + "PADDING PADDING PADDING PADDING PADDING PADDING PADDING PADDING"
    example_ACK_payload = "ACK_MSG"
    print("Run time is: ",run_time)
    print("Data message failure rate is:",data_fail_rate, " ACK message failure rate is:",ack_fail_rate, " Total failure rate is:",total_fail_rate)
    print("Succesfull Transmission rate (DATA and ACK successfull) is:",total_successfull_transmissions)
    total_transfered_data = sys.getsizeof(example_Data_payload) * number_of_messages * (1-data_fail_rate)
    total_transfered_data += sys.getsizeof(example_ACK_payload) * number_of_messages * (1-ack_fail_rate)
    print("Average Throughput is: ", total_transfered_data/run_time," bytes/sec")         

def main():
    topo = Topology()
# Note that the topology has to specific: usrp winslab_b210_0 is run by instance 0 of the component
# Therefore, the usrps have to have names winslab_b210_x where x \in (0 to nodecount-1)
    #topo.construct_winslab_topology_with_channels(number_of_nodes, UsrpNode, FIFOBroadcastPerfectChannel)
    topo.construct_winslab_topology_without_channels(number_of_nodes, UsrpNode)
    topo.start()
    run_test(topo,0.01,number_of_nodes,200)
    topo.exit()

if __name__ == "__main__":
    main()
