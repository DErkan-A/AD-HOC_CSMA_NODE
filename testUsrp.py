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


# define your own message types
class ApplicationLayerMessageTypes(Enum):
    DATA = "DATA"
    ACK = "ACK"


class UsrpApplicationLayerEventTypes(Enum):
    STARTBROADCAST = "startbroadcast"


class UsrpApplicationLayer(GenericModel):
    def on_init(self, eventobj: Event):
        self.counter = 0
    
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology)
        self.eventhandlers[UsrpApplicationLayerEventTypes.STARTBROADCAST] = self.on_startbroadcast

    def on_message_from_top(self, eventobj: Event):
    # print(f"I am {self.componentname}.{self.componentinstancenumber},sending down eventcontent={eventobj.eventcontent}\n")
        self.send_down(Event(self, EventTypes.MFRT, eventobj.eventcontent))
    
    def on_message_from_bottom(self, eventobj: Event):
        evt = Event(self, EventTypes.MFRT, eventobj.eventcontent)        
        if self.componentinstancenumber == eventobj.eventcontent.header.messageto:
            if(eventobj.eventcontent.header.messagetype == ApplicationLayerMessageTypes.DATA):
                print(f"I am Node.{self.componentinstancenumber}, received DATA from Node.{eventobj.eventcontent.header.messagefrom} a message: {eventobj.eventcontent.payload}")
                evt.eventcontent.header.messagetype = ApplicationLayerMessageTypes.ACK   
                evt.eventcontent.header.messageto = eventobj.eventcontent.header.messagefrom
                evt.eventcontent.header.messagefrom = self.componentinstancenumber
                evt.eventcontent.payload ="ACK for: " + eventobj.eventcontent.payload
                #print(f"I am {self.componentname}.{self.componentinstancenumber}, sending down eventcontent={eventobj.eventcontent.payload}\n")
                self.send_down(evt)  # PINGPONG
            elif(eventobj.eventcontent.header.messagetype == ApplicationLayerMessageTypes.ACK):
                print(f"I am Node.{self.componentinstancenumber}, received ACK from Node.{eventobj.eventcontent.header.messagefrom} a message: {eventobj.eventcontent.payload}")

    def on_startbroadcast(self, eventobj: Event):
        hdr = GenericMessageHeader(ApplicationLayerMessageTypes.DATA,self.componentinstancenumber , random.randint(0, 3))
        self.counter = self.counter + 1       
        payload ="DATA: BMSG-" + str(self.counter)
        broadcastmessage = GenericMessage(hdr, payload)
        evt = Event(self, EventTypes.MFRT, broadcastmessage)
         print(f"I am Node.{self.componentinstancenumber}, sending a message to.{hdr.messageto}")
        # time.sleep(3)
        self.send_down(evt)
        #print("Starting broadcast")
    
         
class UsrpNode(GenericModel):
    counter = 0
    def on_init(self, eventobj: Event):
        pass
    
    def __init__(self, componentname, componentinstancenumber, context=None, configurationparameters=None, num_worker_threads=1, topology=None):
        super().__init__(componentname, componentinstancenumber, context, configurationparameters, num_worker_threads, topology)
        # SUBCOMPONENTS
        
        macconfig = MacCsmaPPersistentConfigurationParameters(0.5)
        
        self.appl = UsrpApplicationLayer("UsrpApplicationLayer", componentinstancenumber, topology=topology)
        self.phy = UsrpB210OfdmFlexFramePhy("UsrpB210OfdmFlexFramePhy", componentinstancenumber, topology=topology)
        self.mac = MacCsmaPPersistent("MacCsmaPPersistent", componentinstancenumber,  configurationparameters=macconfig, uhd=self.phy.ahcuhd,topology=topology)
        
        self.components.append(self.appl)
        self.components.append(self.phy)
        self.components.append(self.mac)

        # CONNECTIONS AMONG SUBCOMPONENTS
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
    while(i < 10):
        random_node = random.randint(0,3)
        topo.nodes[random_node].appl.send_self(Event(topo.nodes[random_node], UsrpApplicationLayerEventTypes.STARTBROADCAST, None))
        time.sleep(1)
        i = i + 1
    time.sleep(20)

if __name__ == "__main__":
    main()
