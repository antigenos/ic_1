"""Windows host guard for competing solver/timing lanes on the selected physical core."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import struct
import time

K = C.WinDLL("kernel32", use_last_error=True)
K.CreateToolhelp32Snapshot.restype = W.HANDLE
K.OpenProcess.restype = W.HANDLE
K.CloseHandle.argtypes = [W.HANDLE]
K.GetProcessAffinityMask.argtypes = [W.HANDLE,C.POINTER(C.c_size_t),C.POINTER(C.c_size_t)]


class Process(C.Structure):
    _fields_ = [("size",W.DWORD),("usage",W.DWORD),("pid",W.DWORD),("heap",C.c_size_t),
                ("module",W.DWORD),("threads",W.DWORD),("parent",W.DWORD),("pri",W.LONG),
                ("flags",W.DWORD),("name",W.WCHAR*260)]


def cores():
    length = W.DWORD()
    K.GetLogicalProcessorInformationEx(0,None,C.byref(length))
    buf=C.create_string_buffer(length.value)
    if not K.GetLogicalProcessorInformationEx(0,buf,C.byref(length)):
        raise C.WinError(C.get_last_error())
    pos,found=0,[]
    while pos<length.value:
        kind,size=struct.unpack_from("II",buf,pos)
        assert kind==0 and size>=48 and struct.unpack_from("H",buf,pos+30)[0]==1
        mask=struct.unpack_from("Q",buf,pos+32)[0]
        found.append([i for i in range(64) if mask>>i&1])
        pos+=size
    return found


def competitors(mask, owner):
    # Other lanes run ABC, or a pinned Python/C controller. Broad-affinity ordinary
    # desktop services are not benchmark lanes. Audit covers observed processes.
    snap=K.CreateToolhelp32Snapshot(2,0)
    if snap==C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    item=Process()
    item.size=C.sizeof(item)
    found=[]
    try:
        more=K.Process32FirstW(W.HANDLE(snap),C.byref(item))
        if not more:
            raise C.WinError(C.get_last_error())
        while more:
            name=item.name.lower()
            if (item.pid not in (owner,os.getpid()) and item.parent!=owner and
                (name.startswith("abc") or name in ("python.exe","pythonw.exe","pexact.exe"))):
                proc=K.OpenProcess(0x1000,0,item.pid)
                if proc:
                    try:
                        user,system=C.c_size_t(),C.c_size_t()
                        ok=K.GetProcessAffinityMask(proc,C.byref(user),C.byref(system))
                        solver=name.startswith("abc") or name=="pexact.exe"
                        if (not ok and solver) or (user.value&mask and (solver or user.value!=system.value)):
                            found.append([item.pid,name,user.value])
                    finally:
                        K.CloseHandle(proc)
                elif C.get_last_error()!=87 and name.startswith("abc"):
                    found.append([item.pid,name,"unknown"])
            more=K.Process32NextW(W.HANDLE(snap),C.byref(item))
    finally:
        K.CloseHandle(snap)
    return found


def watch(folder,cpu,owner):
    physical=next(c for c in cores() if cpu in c)
    mask=sum(1<<v for v in physical)
    target=folder/"guard.jsonl"
    with target.open("x",encoding="utf8",buffering=1) as f:
        while not (folder/"guard.stop").exists():
            foreign=competitors(mask,owner)
            f.write(json.dumps(dict(t=time.time(),physical=physical,foreign=foreign))+"\n")
            if foreign:
                (folder/"contended").touch()
            time.sleep(0.2)


if __name__=="__main__":
    import sys
    watch(Path(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]))
