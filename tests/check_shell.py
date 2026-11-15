"""Exercise the native COM DLL against real Windows shell item arrays, without Explorer or registration."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import shutil
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

parser=argparse.ArgumentParser()
parser.add_argument('--compiler',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
HRESULT=C.c_long
PTR=C.c_void_p
GUID=C.c_ubyte*16
def guid(value):return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)
def method(pointer,index,result,*parameters):
    table=C.cast(pointer,C.POINTER(C.POINTER(PTR))).contents
    return C.WINFUNCTYPE(result,PTR,*parameters)(table[index])
ole=C.WinDLL('ole32');shell=C.WinDLL('shell32');ole.CoInitializeEx(None,2)
ole.CoTaskMemFree.argtypes=[PTR];ole.CoTaskMemAlloc.argtypes=[C.c_size_t];ole.CoTaskMemAlloc.restype=PTR
shell.SHParseDisplayName.argtypes=[W.LPCWSTR,PTR,C.POINTER(PTR),W.DWORD,C.POINTER(W.DWORD)];shell.SHParseDisplayName.restype=HRESULT
shell.SHCreateShellItemArrayFromIDLists.argtypes=[W.UINT,C.POINTER(PTR),C.POINTER(PTR)];shell.SHCreateShellItemArrayFromIDLists.restype=HRESULT
shell.CommandLineToArgvW.argtypes=[W.LPCWSTR,C.POINTER(C.c_int)];shell.CommandLineToArgvW.restype=C.POINTER(W.LPWSTR)
kernel=C.WinDLL('kernel32');kernel.LocalFree.argtypes=[PTR]
with tempfile.TemporaryDirectory(prefix='ClipBridge shell ') as temp:
    folder=Path(temp);(folder/'shell').mkdir()
    dll_path=folder/'shell/ClipBridge-Shell.dll';shutil.copyfile(root/'shell/ClipBridge-Shell.dll',dll_path)
    helper=folder/'capture.c'
    helper.write_text('#define UNICODE\n#include <windows.h>\n#include <wchar.h>\nint main(){WCHAR path[2048];DWORD n;HANDLE f;GetModuleFileNameW(NULL,path,2000);*wcsrchr(path,92)=0;lstrcatW(path,L"\\\\argv.txt");f=CreateFileW(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,0,NULL);WriteFile(f,GetCommandLineW(),lstrlenW(GetCommandLineW())*2,&n,NULL);CloseHandle(f);return 0;}','utf-8')
    subprocess.run([str(args.compiler),str(helper),'-o',str(folder/'ClipBridge-PC.exe')],check=True)
    dll=C.WinDLL(str(dll_path));dll.DllGetClassObject.argtypes=[C.POINTER(GUID),C.POINTER(GUID),C.POINTER(PTR)];dll.DllGetClassObject.restype=HRESULT
    factory=PTR();assert dll.DllGetClassObject(guid('03b9580f-25c4-44a6-b150-a7b58f06fc10'),guid('00000001-0000-0000-c000-000000000046'),C.byref(factory))==0
    command=PTR();assert method(factory,3,HRESULT,PTR,C.POINTER(GUID),C.POINTER(PTR))(factory,None,guid('a08ce4d0-fa25-44ab-b57c-c7b1c323e0b9'),C.byref(command))==0
    title=PTR();assert method(command,3,HRESULT,PTR,C.POINTER(PTR))(command,None,C.byref(title))==0
    assert C.wstring_at(title)=='Share to My Phone (ClipBridge)';ole.CoTaskMemFree(title)
    no_selection=W.DWORD(99)
    assert method(command,7,HRESULT,PTR,W.BOOL,C.POINTER(W.DWORD))(command,None,False,C.byref(no_selection))==0 and no_selection.value==0
    paths=[folder/'spaces & العربية.txt',folder/'second file.txt']
    for p in paths:p.write_text('test','utf-8')
    pidls=[]
    for p in paths:
        pidl=PTR();assert shell.SHParseDisplayName(str(p),None,C.byref(pidl),0,None)==0;pidls.append(pidl)
    selection=PTR();array=(PTR*len(pidls))(*[p.value for p in pidls]);assert shell.SHCreateShellItemArrayFromIDLists(len(pidls),array,C.byref(selection))==0
    state=W.DWORD();assert method(command,7,HRESULT,PTR,W.BOOL,C.POINTER(W.DWORD))(command,selection,True,C.byref(state))==0 and state.value==0
    assert method(command,8,HRESULT,PTR,PTR)(command,selection,None)==0
    output=folder/'argv.txt'
    for _ in range(50):
        if output.exists():break
        time.sleep(.1)
    count=C.c_int();argv=shell.CommandLineToArgvW(output.read_bytes().decode('utf-16-le'),C.byref(count))
    captured=[argv[i] for i in range(count.value)];kernel.LocalFree(argv)
    assert captured[1:]==['--send-files','--',*[str(p) for p in paths]],captured
    for pointer in [selection,command,factory]:method(pointer,2,W.ULONG)(pointer)
    for pointer in pidls:ole.CoTaskMemFree(pointer)
    assert dll.DllCanUnloadNow()==0
    kernel.FreeLibrary.argtypes=[W.HMODULE];kernel.FreeLibrary(dll._handle)
print('Native command factory, title, actual shell selection, Unicode/multiple-file argument routing, and reference lifetime passed.')
