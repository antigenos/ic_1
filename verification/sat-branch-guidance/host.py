"""Windows single-group topology and independent solver affinity census."""
import ctypes as c
from ctypes import wintypes as w
import os

k = c.WinDLL('kernel32',use_last_error=True)
size_t = c.c_size_t
k.CreateToolhelp32Snapshot.restype = w.HANDLE
k.OpenProcess.restype = w.HANDLE

class Entry(c.Structure):
    _fields_ = [('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),('heap',size_t),
                ('module',w.DWORD),('threads',w.DWORD),('ppid',w.DWORD),('priority',w.LONG),
                ('flags',w.DWORD),('exe',w.WCHAR*260)]

def physical_mask(cpu):
    n = w.DWORD()
    k.GetLogicalProcessorInformationEx(0,None,c.byref(n))
    buf = c.create_string_buffer(n.value)
    if not k.GetLogicalProcessorInformationEx(0,buf,c.byref(n)):
        raise c.WinError(c.get_last_error())
    pos = 0
    while pos < n.value:
        length = int.from_bytes(buf[pos+4:pos+8],'little')
        mask = int.from_bytes(buf[pos+32:pos+40],'little')
        group = int.from_bytes(buf[pos+40:pos+42],'little')
        if group == 0 and mask & (1<<cpu): return mask
        pos += length
    raise ValueError(cpu)

def conflicts(mask,owner):
    snap = k.CreateToolhelp32Snapshot(2,0)
    if snap == w.HANDLE(-1).value: raise c.WinError(c.get_last_error())
    result = []
    try:
        item = Entry()
        item.size = c.sizeof(item)
        more = k.Process32FirstW(w.HANDLE(snap),c.byref(item))
        if not more: raise c.WinError(c.get_last_error())
        while more:
            name = item.exe.lower()
            if name in ('abc.exe','python.exe','pythonw.exe') and item.pid not in (owner,os.getpid()) and item.ppid != owner:
                h = k.OpenProcess(0x1000,False,item.pid)
                affinity,system = size_t(),size_t()
                if h:
                    try: ok = k.GetProcessAffinityMask(w.HANDLE(h),c.byref(affinity),c.byref(system))
                    finally: k.CloseHandle(w.HANDLE(h))
                else: ok = False
                pinned = ok and bool(affinity.value) and affinity.value & (affinity.value-1) == 0
                if (name == 'abc.exe' and not ok) or (ok and affinity.value & mask and (name == 'abc.exe' or pinned)):
                    result.append([item.pid,item.ppid,affinity.value if ok else None])
            more = k.Process32NextW(w.HANDLE(snap),c.byref(item))
    finally: k.CloseHandle(w.HANDLE(snap))
    return result
