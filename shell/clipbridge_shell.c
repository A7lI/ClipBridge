/* Small native IExplorerCommand replacement. No network or file reads in Explorer.
   Windows ABI declarations below avoid depending on a particular SDK header version. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
__declspec(dllimport) void *WINAPI CoTaskMemAlloc(SIZE_T size);
__declspec(dllimport) void WINAPI CoTaskMemFree(void *memory);

static HMODULE module;
static LONG objects;
static const GUID command_id={0x03b9580f,0x25c4,0x44a6,{0xb1,0x50,0xa7,0xb5,0x8f,0x06,0xfc,0x10}};
static const GUID unknown_id={0,0,0,{0xc0,0,0,0,0,0,0,0x46}};
static const GUID factory_id={1,0,0,{0xc0,0,0,0,0,0,0,0x46}};
static const GUID explorer_id={0xa08ce4d0,0xfa25,0x44ab,{0xb5,0x7c,0xc7,0xb1,0xc3,0x23,0xe0,0xb9}};
typedef struct Object { const void **vtable; LONG references; } Object;
typedef struct Interface { void **vtable; } Interface;
typedef HRESULT (WINAPI *GetCountFn)(void *,DWORD *);
typedef HRESULT (WINAPI *GetItemFn)(void *,DWORD,void **);
typedef HRESULT (WINAPI *GetNameFn)(void *,DWORD,LPWSTR *);
typedef HRESULT (WINAPI *GetAttributesFn)(void *,DWORD,DWORD *);
typedef ULONG (WINAPI *ReleaseFn)(void *);
static const void *command_vtable[];
static const void *factory_vtable[];

static ULONG WINAPI addref(Object *self){return InterlockedIncrement(&self->references);}
static ULONG WINAPI release(Object *self){LONG refs=InterlockedDecrement(&self->references);if(!refs){free(self);InterlockedDecrement(&objects);}return refs;}
static HRESULT WINAPI command_query(Object *self,REFIID iid,void **out){
    if(!out)return E_POINTER;*out=NULL;
    if(!memcmp(iid,&unknown_id,sizeof(GUID))||!memcmp(iid,&explorer_id,sizeof(GUID))){*out=self;addref(self);return S_OK;}return E_NOINTERFACE;
}
static HRESULT text_copy(LPCWSTR value,LPWSTR *out){
    size_t length=(wcslen(value)+1)*sizeof(WCHAR);if(!out)return E_POINTER;
    *out=CoTaskMemAlloc(length);if(!*out)return E_OUTOFMEMORY;memcpy(*out,value,length);return S_OK;
}
static HRESULT WINAPI title(Object *self,void *selection,LPWSTR *out){return text_copy(L"Share to My Phone (ClipBridge)",out);}
static HRESULT WINAPI tooltip(Object *self,void *selection,LPWSTR *out){return text_copy(L"Send with ClipBridge to Downloads/ClipBridge on your phone",out);}
static BOOL folder_path(LPWSTR out,DWORD count){
    DWORD length=GetModuleFileNameW(module,out,count);WCHAR *slash;if(!length||length>=count)return FALSE;
    slash=wcsrchr(out,L'\\');if(!slash)return FALSE;slash[1]=0;return TRUE;
}
static HRESULT WINAPI icon(Object *self,void *selection,LPWSTR *out){
    WCHAR path[2048];if(!folder_path(path,2000))return E_FAIL;lstrcatW(path,L"ClipBridge-Phone.ico");return text_copy(path,out);
}
static HRESULT WINAPI canonical(Object *self,GUID *out){if(!out)return E_POINTER;*out=command_id;return S_OK;}
static HRESULT count_items(Interface *selection,DWORD *count){if(!selection)return E_INVALIDARG;return ((GetCountFn)selection->vtable[7])(selection,count);}
static HRESULT WINAPI state(Object *self,Interface *selection,BOOL slow,DWORD *out){
    DWORD count=0;if(!out)return E_POINTER;*out=0;
    /* Explorer can ask for state before supplying a selection. Do not hide
       the verb in that case; Invoke and the sender validate the real files. */
    if(selection&&SUCCEEDED(count_items(selection,&count))&&count>20)*out=1;
    return S_OK;
}
static HRESULT WINAPI invoke(Object *self,Interface *selection,void *bind){
    WCHAR *command=calloc(32768,sizeof(WCHAR)),*executable=calloc(32768,sizeof(WCHAR));
    DWORD count=0,index;HRESULT hr=E_INVALIDARG;STARTUPINFOW startup;PROCESS_INFORMATION process;
    if(!command||!executable){hr=E_OUTOFMEMORY;goto cleanup;}
    if(FAILED(count_items(selection,&count))||count<1||count>20)goto cleanup;
    if(!folder_path(executable,32000)){hr=E_FAIL;goto cleanup;}
    lstrcatW(executable,L"..\\ClipBridge-PC.exe");
    lstrcpyW(command,L"\"");lstrcatW(command,executable);lstrcatW(command,L"\" --send-files --");
    for(index=0;index<count;index++){
        Interface *item=NULL;LPWSTR name=NULL;
        hr=((GetItemFn)selection->vtable[8])(selection,index,(void **)&item);if(FAILED(hr))goto cleanup;
        hr=((GetNameFn)item->vtable[5])(item,0x80058000,&name);((ReleaseFn)item->vtable[2])(item);
        if(FAILED(hr))goto cleanup;
        if(wcschr(name,L'"')||wcslen(command)+wcslen(name)+5>=32767){CoTaskMemFree(name);hr=E_INVALIDARG;goto cleanup;}
        lstrcatW(command,L" \"");lstrcatW(command,name);lstrcatW(command,L"\"");CoTaskMemFree(name);
    }
    ZeroMemory(&startup,sizeof(startup));startup.cb=sizeof(startup);ZeroMemory(&process,sizeof(process));
    if(!CreateProcessW(executable,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,NULL,&startup,&process)){hr=HRESULT_FROM_WIN32(GetLastError());goto cleanup;}
    CloseHandle(process.hThread);CloseHandle(process.hProcess);hr=S_OK;
cleanup:
    free(command);free(executable);
    if(FAILED(hr))MessageBoxW(NULL,L"ClipBridge could not send this selection. Select up to 20 local files and check that ClipBridge-PC.exe is still beside its shell folder.",L"Share to My Phone · ClipBridge",MB_OK|MB_ICONINFORMATION);
    return hr;
}
static HRESULT WINAPI flags(Object *self,DWORD *out){if(!out)return E_POINTER;*out=0;return S_OK;}
static HRESULT WINAPI subcommands(Object *self,void **out){if(out)*out=NULL;return E_NOTIMPL;}
static const void *command_vtable[]={command_query,addref,release,title,icon,tooltip,canonical,state,invoke,flags,subcommands};
static HRESULT WINAPI factory_query(Object *self,REFIID iid,void **out){
    if(!out)return E_POINTER;*out=NULL;if(!memcmp(iid,&unknown_id,sizeof(GUID))||!memcmp(iid,&factory_id,sizeof(GUID))){*out=self;addref(self);return S_OK;}return E_NOINTERFACE;
}
static HRESULT WINAPI create(Object *self,void *outer,REFIID iid,void **out){
    Object *object;HRESULT hr;if(outer)return CLASS_E_NOAGGREGATION;
    object=calloc(1,sizeof(Object));if(!object)return E_OUTOFMEMORY;object->vtable=command_vtable;object->references=1;InterlockedIncrement(&objects);
    hr=command_query(object,iid,out);release(object);return hr;
}
static HRESULT WINAPI lock_server(Object *self,BOOL lock){if(lock)InterlockedIncrement(&objects);else InterlockedDecrement(&objects);return S_OK;}
static const void *factory_vtable[]={factory_query,addref,release,create,lock_server};
__declspec(dllexport) HRESULT WINAPI DllGetClassObject(REFCLSID clsid,REFIID iid,void **out){
    Object *factory;HRESULT hr;if(memcmp(clsid,&command_id,sizeof(GUID)))return CLASS_E_CLASSNOTAVAILABLE;
    factory=calloc(1,sizeof(Object));if(!factory)return E_OUTOFMEMORY;factory->vtable=factory_vtable;factory->references=1;InterlockedIncrement(&objects);
    hr=factory_query(factory,iid,out);release(factory);return hr;
}
__declspec(dllexport) HRESULT WINAPI DllCanUnloadNow(void){return objects?S_FALSE:S_OK;}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved){if(reason==DLL_PROCESS_ATTACH){module=instance;DisableThreadLibraryCalls(instance);}return TRUE;}
