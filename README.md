# AD-HOC_CSMA_NODE
CSMA node for the ceng797 projects milestone

Design
My node model is very simple each node handles 2 message types namely ”DATA” and ”ACK” which are self-explanatory. Nodes has 3 main functions, which are:

1. Start broadcast: Sends a DATA message to a random node that is not itself
2. On receiving DATA message: Increment data message counter and send ACK message back to the sender.
3. On receiving ACK message: Increment ACK counter

This simple structure lets me do basic benchmarks about packet failure rate and average throughput.

First of all changing node count or degree seemed unnecessary to me as maximum of 4 nodes can be used and 4 is a small number. Nodes are also mesh connected making diameter of the network constant at 1 regardless of the number of nodes. Hence, every experiment is with 4 nodes each having degree 4 and diameter of network as 1. size of my payload strings are about 70 bytes, I could not determine the size of the entire Event package.

Average throughput is calculated with (packet_success_rate * 70byte / waiting_time_between_packets)
