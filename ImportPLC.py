import pycomm3

from pycomm3 import LogixDriver

# PLC IP address and slot number
PLC_IP = '192.168.25.186/11' 

with LogixDriver(PLC_IP) as PLC:
    print(PLC.revision_major)
    print(PLC._cip_path)
