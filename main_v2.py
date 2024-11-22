'''
This automation is intended to show/demo 802.1Qbv

Topology
                          DUT
Ixia Port 1 ----------- NXP spw0
Ixia Port 2 ----------- NXP spw1 ( Egress )
Ixia Port 3 ----------- NXP spw2

Cycle Time = 1,000 microseconds
4 Windows
Window 1 -   0 to  250 Microseconds - Vlan Priorities 0,1,2,3  = 0 0 0 0 1 1 1 1 
Window 2 - 250 to  500 Microseconds - Vlan Priorities 4        = 0 0 0 1 0 0 0 1
Window 1 - 500 to  750 Microseconds - Vlan Priorities 5        = 0 0 1 0 0 0 0 1
Window 1 - 750 to 1000 Microseconds - Vlan Priorities 6,7      = 1 1 0 0 0 0 0 1 

DUT Config - NXP ls1028ardb

1. Config Switch with Vlan 100
#!/bin/bash
vidmin=100
vidmax=100

ip link set eno2 up
ip link add name switch type bridge vlan_filtering 1
ip link set switch up

#add swp0, swp1, swp2, swp3 to same bridge
#add vlan 100
for port in swp0 swp1 swp2 swp3 ; do
        ip addr flush dev $port
        ip link set $port master switch && ip link set $port up

        for (( vid=$vidmin ; vid<=$vidmax ; vid++ )) ; do
                bridge vlan add dev $port vid $vid
                echo "port $port , vid $vid"
        done

done

echo "Switch configuration applied"

2. gPtp - Please refer to Documentation for more details
NXP Semiconductors Document identifier: REALTIMEEDGEUG
User Guide Rev. 2.2, 29 March 2022
root@ls1028ardb:~/tsn_scripts/tsn_scripts# avb.sh  ( gPtP running AS2020  - Single Domain )

3. Gate Config  - Done in the Egress Port ( spw1 in the example below )
#!/bin/bash

#set up Qbv rules
#priority 2 from swp0 and 0,1,3,4,5,6,7 from swp1
tc qdisc replace dev swp1 parent root handle 100 taprio \
        num_tc 8 queues 1@0 1@1 1@2 1@3 1@4 1@5 1@6 1@7 \
        map 0 1 2 3 4 5 6 7 \
        base-time 0 \
        sched-entry S 0F 250000 \
        sched-entry S 10 250000 \
        sched-entry S 20 250000 \
        sched-entry S C0 250000 \
        flags 2
echo "Qbv configuration for swp1 applied"

tc qdisc show dev swp1

+++++ END OF DUT CONFIG +++++++++++++++++++



'''

import sys
from ixnetwork_restpy import *
import locale

locale.setlocale(locale.LC_ALL, '')
import time
from helperFunctions import *
import math
from datetime import datetime, timedelta
from decimal import Decimal, getcontext


TestVars = testVars()
TestVars.chassisIp : str = '10.80.81.2'
TestVars.sessionIp : str = 'localhost'
TestVars.UrlPrefix = None

# Session ID for now is None; meaning we are creating a new session.
TestVars.sessionId : str = 1
TestVars.port1 : str = '2/14'
TestVars.port2 : str = '2/15'
TestVars.port3 : str = '2/16'
TestVars.cleanConfig : bool = True
TestVars.takePorts : bool = True
TestVars.user : str =  'admin'
TestVars.password : str = 'admin' #'Keysight#12345'
TestVars.UrlPrefix=None
# Pkt Sizes to test 'min:max:incrBy'
TestVars.pktSize_in_bytes: int = 100
TestVars.txClycleTime_in_microseconds : int = '1000'
TestVars.Preamble_in_bytes : int = 8
TestVars.InterFrameGap_in_bytes : int = 12
TestVars.vlan_id : int = 100
# Expecting Lists of Lists....to calculate number of queues
TestVars.vlan_priorities : list = [[0],[4],[5],[7]]
TestVars.cycle_time_in_microseconds : list = [250,250,250,250]
TestVars.preamble_in_bytes : int = 8
TestVars.inter_frame_gap_in_bytes : int = 12
TestVars.data_rate_in_Gbps : int = 1
TestVars.gPtp_profile : str = 'ieee8021asrev'
TestVars.session_name = 'cc'
TestVars.rest_port = 11009

# Mini Automation 
TestVars.mini_flag : bool = False
if TestVars.mini_flag:
    TestVars.rest_port = 80  
    TestVars.sessionId = None
    TestVars.UrlPrefix="ixnetwork-mw"
    TestVars.user  =  None
    TestVars.session_name = None
    TestVars.chassisIp : str = 'localchassis'
    
def main():

    # description
    outLogFile : str = 'mainqvb_' + time.strftime("%Y%m%d-%H%M%S") + '.log'
    if TestVars.session_name: 
        TestVars.session_name : str = 'mainqvb_' + "me" + time.strftime("%Y%m%d-%H%M")
    vport_dic = dict()
    myStep = Step()
    # Calculate the total number of bits in the packet including payload , preamble and IFG
    total_bits = ( TestVars.pktSize_in_bytes * 8 ) + ( TestVars.preamble_in_bytes * 8 ) + ( TestVars.inter_frame_gap_in_bytes * 8 )
    transmission_time_in_microseconds = (total_bits / (TestVars.data_rate_in_Gbps * 1_000_000_000)) * 1_000_000
    num_of_cycle_windows = len(TestVars.vlan_priorities)
    packets_per_second = (1_000 / transmission_time_in_microseconds) * num_of_cycle_windows
    pps_per_stream = ( math.floor(packets_per_second / 1000) * 1000 ) / num_of_cycle_windows


    macs = MacAddressGenerator()

    try:
        session = SessionAssistant(IpAddress=TestVars.sessionIp,
                                   UserName=TestVars.user,
                                   Password=TestVars.password,
                                   RestPort=TestVars.rest_port,
                                   SessionId=TestVars.sessionId,
                                   SessionName=TestVars.session_name,
                                   ClearConfig=TestVars.cleanConfig,
                                   LogLevel='info',
                                   UrlPrefix=TestVars.UrlPrefix,
                                   LogFilename=outLogFile)

        ixnet_session = session.Ixnetwork
        # ixnet / globals / stats / advance/ timestamp
        ixnet_session.Statistics.TimestampPrecision = 9
        ixnet_session.info(f"Step {myStep.add()} - Init - Rest Session {session.Session.Id} established.")
        ixnet_session.info(f"Step {myStep.add()} - Init - Enable Use Schedule Start Transmit in Test Options -> Global Settings.")
        
        # Set Cycle Time Based on input table
        ixnet_session.Traffic.UseScheduledStartTransmit = True
        ixnet_session.info(f"Step {myStep.add()} - Init - Config Cycle Time to {TestVars.txClycleTime_in_microseconds} microSeconds.")
        ixnet_session.Traffic.CycleTimeForScheduledStart = TestVars.txClycleTime_in_microseconds
        ixnet_session.Traffic.CycleTimeUnitForScheduledStart = 'microseconds'

        ixnet_session.info(f"Step {myStep.add()} - Init - Config Global Stats latency to cutThrough mode.")
        ixnet_session.Traffic.Statistics.Latency.Enabled = True
        ixnet_session.Traffic.Statistics.Latency.update(Mode='cutThrough')
        #Set Latency Delay Mode to Store and Forward
#        ixnet_session.Traffic.Statistics.DelayVariation.LatencyMode = 'storeForward'

        ixnet_session.info(f"Step {myStep.add()} - Init - Assign Ports to Session.")
        port_map = session.PortMapAssistant()
        mySlot, portIndex = TestVars.port1.split("/")
        vport_dic["Grand"] =  port_map.Map(TestVars.chassisIp, mySlot, portIndex, Name="GrandMaster")
        mySlot, portIndex = TestVars.port2.split("/")
        vport_dic["Follower"] =port_map.Map(TestVars.chassisIp, mySlot, portIndex, Name="Follower")
        mySlot, portIndex = TestVars.port3.split("/")
        vport_dic["BkgTraff"] =port_map.Map(TestVars.chassisIp, mySlot, portIndex, Name="BkgTraff")
        port_map.Connect(ForceOwnership=TestVars.takePorts,IgnoreLinkUp=True)  


        ixnet_session.info(f"Step {myStep.add()} - Verify -  Checking if all ports are up")
        portStats = StatViewAssistant(ixnet_session, 'Port Statistics')
        boolPortsAreUp = portStats.CheckCondition('Link State', StatViewAssistant.REGEX, 'Link\s+Up',Timeout=20,RaiseException=False)

        # Setting TX mode to interleaved
        if not TestVars.mini_flag:
            for vport in vport_dic:
                thisPort = ixnet_session.Vport.find(Name=vport)
                #thisPort.Type = 'novusTenGigLanFcoe'
                portType = thisPort.Type[0].upper() + thisPort.Type[1:]
                ixnet_session.info(f"Step {myStep.add()} - Init - Setting port {vport} to Interleaved mode")
                thisPort.TxMode = 'interleaved'
                portObj = getattr(thisPort.L1Config, portType)
                #portObj.EnabledFlowControl = False
                if not boolPortsAreUp:
                    ixnet_session.info(f" Step {myStep.add_minor()} - Init - Ports are not up trying to change the media")
                    if portObj.Media and portObj.Media == 'fiber':
                        portObj.Media = 'copper'
                    elif  portObj.Media and portObj.Media == 'copper':
                        portObj.Media = 'fiber'

            # If ports are not up now we are done.....
            if not boolPortsAreUp:
                ixnet_session.info(f"Step {myStep.add()} - Init - Checking once more if all ports are up - Abort otherwise")
                portStats.CheckCondition('Link State', StatViewAssistant.REGEX, 'Link\s+Up', Timeout=30,RaiseException=True)

        # GrandMaster 
        ixnet_session.info(f"Step {myStep.add()} - Init - Setting up gPTP GrandMaster Side on port {TestVars.port1}")
        topo1 = ixnet_session.Topology.add(Name='802.1AS Master Topology', Ports=vport_dic["Grand"])
        dev1 = topo1.DeviceGroup.add(Name='GrandMaster - DG', Multiplier='1')
        eth1 = dev1.Ethernet.add(Name='ether')
        eth1.Mac.Single(macs.generate_mac_address())
        gPtpHandle = eth1.Ptp.add(Name='GM')
        gPtpHandle.Profile.Single(TestVars.gPtp_profile)
        gPtpHandle.Role.Single('master')
        gPtpHandle.StrictGrant.Single(True)
        
        # Traff Generating Stack
        dev1_1 = topo1.DeviceGroup.add(Name='Controlled Traff', Multiplier='1')
        eth1_traff = dev1_1.Ethernet.add(Name ='eth1_traff')
        eth1_traff.Mac.Single(macs.generate_mac_address())
        eth1_traff.EnableVlans.Single(True)
        eth1_traff.Vlan.find().VlanId.Single(TestVars.vlan_id)
        ip1_traff = eth1_traff.Ipv4.add(Name='Ip1 0.16')
        ip1_traff.Address.Increment(start_value="172.16.0.1", step_value="0.0.0.0")
        ip1_traff.GatewayIp.Increment(start_value="172.16.1.1", step_value="0.0.0.0")
        ip1_traff.Prefix.Single(16)
        ip1_traff.ResolveGateway.Single(value=True)

        # Follower
        ixnet_session.info(f"Step {myStep.add()} - Init - Setting up gPTP Follower Side on port {TestVars.port2}")
        topo2 = ixnet_session.Topology.add(Name='802.1AS Follower Topology', Ports=vport_dic["Follower"])
        dev2 = topo2.DeviceGroup.add(Name='Follower - DG', Multiplier='1')
        eth2 = dev2.Ethernet.add(Name='ether')
        eth2.Mac.Single(macs.generate_mac_address())
        gPtpSHandle = eth2.Ptp.add(Name='Follower')
        gPtpSHandle.Profile.Single(TestVars.gPtp_profile)
        # TRaffic Gen Stack
        dev2_1 = topo2.DeviceGroup.add(Name='Egress Port', Multiplier='1')
        eth2_traff = dev2_1.Ethernet.add(Name='ether2_traff')
        eth2_traff.Mac.Single(macs.generate_mac_address())
        eth2_traff.EnableVlans.Single(True)
        eth2_traff.Vlan.find().VlanId.Single(TestVars.vlan_id)
        ip2_traff = eth2_traff.Ipv4.add(Name='Ip2 1.16')
        ip2_traff.Address.Increment(start_value="172.16.1.1", step_value="0.0.0.0")
        ip2_traff.GatewayIp.Increment(start_value="172.16.0.1", step_value="0.0.0.0")
        ip2_traff.Prefix.Single(16)
        ip2_traff.ResolveGateway.Single(value=True)

        # BackGround Traffic
        ixnet_session.info(f"Step {myStep.add()} - Init - Setting up background traffic on port {TestVars.port3}")
        topo3 = ixnet_session.Topology.add(Name='Bkg Traffic Topo', Ports=vport_dic["BkgTraff"])
        dev3 = topo3.DeviceGroup.add(Name='BkgTraff - DG', Multiplier='10')
        eth3 = dev3.Ethernet.add(Name='ether')
        eth3.Mac.Increment(start_value= macs.generate_mac_address(), step_value= "00:00:00:00:00:01")
        eth3.EnableVlans.Single(True)
        eth3.Vlan.find().VlanId.Single(TestVars.vlan_id)
        ip3 = eth3.Ipv4.add(Name='Ip1 2.16')
        ip3.Address.Increment(start_value="172.16.2.1", step_value="0.0.0.1")
        ip3.GatewayIp.Increment(start_value="172.16.1.1", step_value="0.0.0.0")
        ip3.Prefix.Single(16)
        ip3.ResolveGateway.Single(value=True)

        ixnet_session.info(f'Step {myStep.add()} - Init -  Staring Protocols')
        ixnet_session.StartAllProtocols(Arg1='sync')
        
        ixnet_session.info(f'Step {myStep.add()} - Verify -  PTP sessions are UP')
        protocolsSummary = StatViewAssistant(ixnet_session, 'Protocols Summary')
        protocolsSummary.AddRowFilter('Protocol Type', StatViewAssistant.REGEX, '(?i)^PTP?')
        protocolsSummary.CheckCondition('Sessions Up', StatViewAssistant.EQUAL, '2')
        protocolsSummary.CheckCondition('Sessions Not Started', StatViewAssistant.EQUAL, '0')

        ixnet_session.info(f'Step{myStep.add()} - Verify -  IP sessions are UP')
        protocolsSummary = StatViewAssistant(ixnet_session, 'Protocols Summary')
        protocolsSummary.AddRowFilter('Protocol Type', StatViewAssistant.REGEX, '(?i)^IPv4?')
        protocolsSummary.CheckCondition('Sessions Not Started', StatViewAssistant.EQUAL, '0')

        ixnet_session.info(f'Step {myStep.add()} - Init -  Create Unidirectional Ipv4 Traffic Item')
        etherTraffItem = ixnet_session.Traffic.TrafficItem.add(Name='EtherVlanTraff Item', BiDirectional=False,TrafficType='ipv4',TrafficItemType='l2L3')
        
        indexNum = 0
        cycleIndex = 1
        cycle_init_time = 0
        for _ in range(num_of_cycle_windows):
            flow = etherTraffItem.EndpointSet.add(Sources= ip1_traff , Destinations=ip2_traff)
            flow.Name = "Cycle" + str(cycleIndex)
            highLevelStream = etherTraffItem.HighLevelStream.find()[indexNum]
            highLevelStream.Name = "Cycle" + str(cycleIndex)
            configElement = etherTraffItem.ConfigElement.find()[indexNum]
            configElement.FrameRate.update(Type='framesPerSecond', Rate=int(pps_per_stream))
            configElement.FrameSize.update(Type='fixed', FixedSize = TestVars.pktSize_in_bytes)
            configElement.TransmissionControl.update(StartDelayUnits = 'microseconds')
            configElement.TransmissionControl.update(StartDelay = cycle_init_time)
            cycle_init_time += TestVars.cycle_time_in_microseconds[indexNum]
            vlanStackObj = configElement.Stack.find(DisplayName='VLAN')
            vlanIdPriority = vlanStackObj.Field.find(DisplayName='VLAN Priority')
            vlanIdPriority.ValueType = 'valueList'
            vlanIdPriority.ValueList = TestVars.vlan_priorities[indexNum]
            indexNum += 1
            cycleIndex += 1
        etherTraffItem.Tracking.find()[0].TrackBy = ["trackingenabled0", "flowGroup0", "vlanVlanUserPriority0"]
        etherTraffItem.Generate()

        ixnet_session.info(f'Step {myStep.add()} - Init - Create Line Rate Background Traffic')
        bkTraffItem = ixnet_session.Traffic.TrafficItem.add(Name='BackGround Traffic Item', BiDirectional=False,TrafficType='ipv4',TrafficItemType='l2L3')
        bkflow = bkTraffItem.EndpointSet.add(Sources=ip3, Destinations=ip2_traff)
        bkflow.Name = "BkGround"
        bkTraffItem.HighLevelStream.find()[0].Name = "BkGround"

        bkconfigElement = bkTraffItem.ConfigElement.find()[0]
        bkconfigElement.FrameRate.update(Type='percentLineRate', Rate=100)
        bkconfigElement.FrameSize.update(Type='fixed', FixedSize=TestVars.pktSize_in_bytes)
        bkvlanStackObj = bkconfigElement.Stack.find(DisplayName='VLAN')
        bkvlanIdPriority = bkvlanStackObj.Field.find(DisplayName='VLAN Priority')
        bkvlanIdPriority.ValueType = 'valueList'
        bkvlanIdPriority.ValueList = [1,2,3,5,6,7]
        bkTraffItem.Tracking.find()[0].TrackBy = ["trackingenabled0", "flowGroup0", "vlanVlanUserPriority0"]
        bkTraffItem.Generate()
        bkTraffItem.HighLevelStream.find()[0].Suspend = True
        ixnet_session.Traffic.Apply()

        ixnet_session.info(f'Step {myStep.add()} - Test - Send Traffic for 30 seconds')
        ixnet_session.Traffic.Start()  
        time.sleep(30)
        ixnet_session.Traffic.Stop()  
        checkTrafficState(ixnet_session, state= 'stopped')
        time.sleep(10)

        # CHeck #1 -- All Traffic went thru
        ixnet_session.info(f'Step {myStep.add()} - Verify - All traffic sent was received')
        traffItemStatistics = StatViewAssistant(ixnet_session, 'Traffic Item Statistics')
        traffItemStatistics.AddRowFilter('Traffic Item', StatViewAssistant.REGEX, 'EtherVlanTraff Item')
        for flowStat in traffItemStatistics.Rows: 
            if abs(float(flowStat['Rx Frames']) - float(flowStat['Tx Frames'])) < 1 and float(flowStat['Tx Frames']) > 1:
                ixnet_session.info(f"Tx Frames {int(flowStat['Tx Frames']):,} and Rx Frames {int(flowStat['Rx Frames']):,} -- PASS")
            else:
                ixnet_session.info(f"Tx Frames {int(flowStat['Tx Frames']):,} and Rx Frames {int(flowStat['Rx Frames']):,} -- FAILED")
    
        resultsDict = dict()
        flowGrpStatistics = StatViewAssistant(ixnet_session, 'Flow Statistics')
        flowGrpStatistics.AddRowFilter('Tx Port', StatViewAssistant.REGEX, 'GrandMaster')
        for flowStat in flowGrpStatistics.Rows:
             queueId = flowStat['VLAN:VLAN Priority']
             resultsDict[queueId] = dict()
             resultsDict[queueId]['First'] = getNanoSeconds(flowStat['Absolute First TimeStamp'])
             resultsDict[queueId]['Last'] = getNanoSeconds(flowStat['Absolute Last TimeStamp'])
             resultsDict[queueId]['avg_latency'] = flowStat['Store-Forward Avg Latency (ns)']

        value_0_first = int(resultsDict['0']['First'])
        value_4_first = int(resultsDict['4']['First'])
        value_5_first = int(resultsDict['5']['First'])
        value_6_first = int(resultsDict['6']['First'])

        cycle1Val = value_4_first - value_0_first
        cycle2Val = value_5_first - value_4_first
        cycle3Val = value_6_first - value_5_first
        
        ixnet_session.info(f'Step {myStep.add()} - Verify - Based on Absolute First Packet time check window time spacing')
        if compare_numbers(cycle1Val, 250000, thresholdNum = 0.99):
            ixnet_session.info(f"The Absolute value between cycle 0 and cycle 1 is {cycle1Val:,} ns -- PASS")
        else:
            ixnet_session.info(f"The Absolute value between cycle 0 and cycle 1 is {cycle1Val:,} ns -- FAIL Expecting 250,000")

        if compare_numbers(cycle2Val, 250000, thresholdNum = 0.99):
            ixnet_session.info(f"The Absolute value between cycle 2 and cycle 1 is {cycle2Val:,} ns -- PASS")
        else:
            ixnet_session.info(f"The Absolute value between cycle 2 and cycle 1 is {cycle2Val:,} ns -- FAIL Expecting 250,000")

        if compare_numbers(cycle3Val, 250000, thresholdNum = 0.99):
            ixnet_session.info(f"The Absolute value between cycle 3 and cycle 2 is {cycle3Val:,} ns  -- PASS")
        else:
            ixnet_session.info(f"The Absolute value between cycle 3 and cycle 2 is {cycle3Val:,} ns  -- FAIL Expecting 250,000")

        avg_latency_values = [int(entry['avg_latency']) for entry in resultsDict.values()]
        # Calculate the average
        average_latency = sum(avg_latency_values) / len(avg_latency_values)
        # Check if each value is within 1% of the average
        ixnet_session.info(f'Step {myStep.add()} - Verify - Latency for controlled traffic should be pretty similar no variation')
        within_range = all((average_latency - value) / average_latency <= 0.01 for value in avg_latency_values)
        if within_range:
            ixnet_session.info(f"The avg latency value for all entries are within 1% of the overall {average_latency:,}  -- PASS")
        else:
            ixnet_session.info(f"The avg latency value for all entries are NOT within 1% of the overall {average_latency:,} -- FAIL")

        # Check #2 -- Background Traffic Will NOT interfere with our CRITICAL traffic on Priority 4
        ixnet_session.info(f'Step {myStep.add()} - Test - Send Background traffic for all vlan priorities except Priority 4 for 30 seconds.')    
        bkTraffItem.HighLevelStream.find()[0].Suspend = False
        ixnet_session.Traffic.Start()
        time.sleep(30)
        ixnet_session.Traffic.Stop()
        checkTrafficState(ixnet_session, state='stopped')
        time.sleep(10)

        resultsDict = dict()
        flowGrpStatistics = StatViewAssistant(ixnet_session, 'Flow Statistics')
        flowGrpStatistics.AddRowFilter('Tx Port', StatViewAssistant.REGEX, 'GrandMaster')
        for flowStat in flowGrpStatistics.Rows:
             queueId = flowStat['VLAN:VLAN Priority']
             resultsDict[queueId] = dict()
             resultsDict[queueId]['avg_latency'] = flowStat['Store-Forward Avg Latency (ns)']

        avg_latency_values = [int(entry['avg_latency']) for entry in resultsDict.values()]

        # Expected Result is that ALL Avg Latencies have gone UP except Vlan priority 4
        ixnet_session.info(f'Step {myStep.add()} - Verify - Latency for ALL priorities except Vlan Priority 4 increased.')    
        for vlanPri in [0,1,2,3,5,6,7]:
            if avg_latency_values[vlanPri] > average_latency * 1.10:
                percentage_difference = abs((avg_latency_values[vlanPri] - average_latency) / ((avg_latency_values[vlanPri] + average_latency) / 2)) * 100
                ixnet_session.info(f"The avg latency for Vlan prioriy {vlanPri} {avg_latency_values[vlanPri]}  is {percentage_difference:.2f}% greater than the overall avg {average_latency} now -- PASS")
            else:
                ixnet_session.info(f"The avg latency for Vlan prioriy {vlanPri} {avg_latency_values[vlanPri]} is NOT greater than 10% of the overall avg {average_latency} now -- FAIL")

        ixnet_session.info(f'Step {myStep.add()} - Verify - Latency for priority 4 did not change.')    
        if compare_numbers(avg_latency_values[4],average_latency,0.9):
            ixnet_session.info(f"The avg latency for Vlan prioriy {4} {avg_latency_values[4]}  remains within 10% as pervious avg {average_latency} now -- PASS")
        else:
            ixnet_session.info(f"The avg latency for Vlan prioriy {4} {avg_latency_values[4]}  DOES NOT remains the same as avg {average_latency} now -- -- FAIL")

        ixnet_session.info(f'Step {myStep.add()} - Clean up - Stopping all protocols ')
        ixnet_session.StopAllProtocols()        

        if TestVars.sessionId == None:
            ixnet_session.info(f"Step {myStep.add_minor()} - Clean up - Removing Session we created...bye")
            session.Session.remove()
        else: 
            ixnet_session.info(f"Step {myStep.add_minor()} - Clean up - Cleaning up session and leaving it up...bye")
            ixnet_session.NewConfig()

        ixnet_session.info(f"Step {myStep.add()} - Clean up - The End")

    except Exception as errMsg:
        print(f"{errMsg}")

if __name__ == '__main__':
    main()  



 