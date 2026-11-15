package app.clipbridge;

import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.*;
import android.widget.*;
import java.io.*;
import java.util.*;

/** The shared phone UI, with bounded native saving and clipboard access. */
public class PhoneShareActivity extends Activity {
    static final String HOME="https://www.a7li.dev/apps/clipbridge/web/phone.html";
    private WebView web;
    private ValueCallback<Uri[]> picker;
    private PermissionRequest camera;
    private final SaveBridge bridge=new SaveBridge();

    static boolean allowed(Uri uri){return "https".equals(uri.getScheme())&&"www.a7li.dev".equals(uri.getHost())&&(uri.getPort()==-1||uri.getPort()==443)&&uri.getUserInfo()==null&&uri.getPath()!=null&&uri.getPath().startsWith("/apps/clipbridge/web/");}
    static boolean invitation(String value){try{Uri uri=Uri.parse(value);return allowed(uri)&&("/apps/clipbridge/web/phone.html".equals(uri.getPath())||"/apps/clipbridge/web/phone".equals(uri.getPath()))&&uri.getFragment()!=null;}catch(Exception e){return false;}}

    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().setStatusBarColor(MainActivity.BG);getWindow().setNavigationBarColor(MainActivity.BG);
        LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setBackgroundColor(MainActivity.BG);
        root.setOnApplyWindowInsetsListener((v,insets)->{android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars());v.setPadding(bars.left,bars.top,bars.right,bars.bottom);return insets;});
        LinearLayout bar=new LinearLayout(this);root.addView(bar);
        Button back=new Button(this);back.setText("← ClipBridge");bar.addView(back);back.setOnClickListener(v->finish());
        Button received=new Button(this);received.setText("Saved files");bar.addView(received);received.setOnClickListener(v->startActivity(new Intent(this,FilesActivity.class)));
        web=new WebView(this);root.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setMediaPlaybackRequiresUserGesture(true);
        web.addJavascriptInterface(bridge,"ClipBridgePhone");
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();if(allowed(uri))return false;
                if(request.isForMainFrame()&&"https".equals(uri.getScheme()))try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(Exception ignored){}
                return true;
            }
            @Override public void onReceivedSslError(WebView view,android.webkit.SslErrorHandler handler,android.net.http.SslError error){handler.cancel();}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(picker!=null)picker.onReceiveValue(null);picker=callback;
                Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                String[] accepted=params.getAcceptTypes();if(accepted.length==1&&accepted[0].startsWith("image/"))intent.setType("image/*");
                try{startActivityForResult(intent,60);}catch(Exception e){picker.onReceiveValue(null);picker=null;toast("No file picker available.");}return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request){
                if(!allowed(request.getOrigin().buildUpon().path("/apps/clipbridge/web/").build())||!Arrays.asList(request.getResources()).equals(Collections.singletonList(PermissionRequest.RESOURCE_VIDEO_CAPTURE))){request.deny();return;}
                if(checkSelfPermission(Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED)request.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
                else{if(camera!=null)camera.deny();camera=request;requestPermissions(new String[]{Manifest.permission.CAMERA},61);}
            }
            @Override public void onPermissionRequestCanceled(PermissionRequest request){if(camera==request)camera=null;}
        });
        String link=getIntent().getStringExtra("invitation");web.loadUrl(invitation(link==null?"":link)?link:HOME);
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==60&&picker!=null){ValueCallback<Uri[]> callback=picker;picker=null;ArrayList<Uri> uris=new ArrayList<>();if(result==RESULT_OK&&data!=null){if(data.getClipData()!=null)for(int i=0;i<data.getClipData().getItemCount();i++)uris.add(data.getClipData().getItemAt(i).getUri());else if(data.getData()!=null)uris.add(data.getData());}if(uris.size()>20){toast("Choose up to 20 files.");callback.onReceiveValue(null);}else callback.onReceiveValue(uris.isEmpty()?null:uris.toArray(new Uri[0]));}}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] grants){super.onRequestPermissionsResult(request,permissions,grants);if(request==61&&camera!=null){if(grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED)camera.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});else camera.deny();camera=null;}}
    @Override protected void onDestroy(){if(picker!=null)picker.onReceiveValue(null);if(camera!=null)camera.deny();bridge.clear();if(web!=null){web.removeJavascriptInterface("ClipBridgePhone");web.destroy();}super.onDestroy();}
    void toast(String value){runOnUiThread(()->Toast.makeText(this,value,Toast.LENGTH_LONG).show());}
    static ClipData remote(ClipData clip){android.os.PersistableBundle origin=new android.os.PersistableBundle();origin.putBoolean("app.clipbridge.remote",true);clip.getDescription().setExtras(origin);return clip;}

    final class SaveBridge {
        private File temporary;
        private OutputStream output;
        private String ticket,name,type;
        private long expected,written;
        private boolean copy;
        synchronized void clear(){if(output!=null)try{output.close();}catch(IOException ignored){}output=null;if(temporary!=null)temporary.delete();temporary=null;ticket=null;}
        @JavascriptInterface public synchronized String beginSave(String filename,String mime,long size,boolean copyAfter){
            if(ticket!=null||size<0||size>Transfers.LIMIT)return "";
            try{temporary=File.createTempFile("phone-save-",".tmp",getCacheDir());output=new FileOutputStream(temporary);ticket=UUID.randomUUID().toString();name=Transfers.safeName(filename);type=mime!=null&&mime.length()<128&&mime.matches("[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+")?mime:"application/octet-stream";expected=size;written=0;copy=copyAfter;return ticket;}catch(IOException e){clear();return "";}
        }
        @JavascriptInterface public synchronized boolean appendSave(String id,String encoded){
            if(ticket==null||!ticket.equals(id)||encoded==null||encoded.length()>24000)return false;
            try{byte[] raw=Base64.decode(encoded,Base64.NO_WRAP);if(raw.length==0||raw.length>16384||written+raw.length>expected)return false;output.write(raw);written+=raw.length;return true;}catch(Exception e){clear();return false;}
        }
        @JavascriptInterface public synchronized void cancelSave(String id){if(ticket!=null&&ticket.equals(id))clear();}
        @JavascriptInterface public synchronized boolean finishSave(String id){
            if(ticket==null||!ticket.equals(id)||written!=expected)return false;
            Uri uri=null;
            try{
                output.close();output=null;
                ContentValues values=new ContentValues();values.put(MediaStore.Downloads.DISPLAY_NAME,name);values.put(MediaStore.Downloads.MIME_TYPE,type);values.put(MediaStore.Downloads.RELATIVE_PATH,Downloads.FOLDER);values.put(MediaStore.Downloads.IS_PENDING,1);
                uri=getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);if(uri==null)throw new IOException();
                try(InputStream in=new FileInputStream(temporary);OutputStream out=getContentResolver().openOutputStream(uri,"w")){if(out==null)throw new IOException();Transfers.copy(in,out,Transfers.LIMIT);}
                ContentValues ready=new ContentValues();ready.put(MediaStore.Downloads.IS_PENDING,0);if(getContentResolver().update(uri,ready,null,null)!=1)throw new IOException();
                final Uri saved=uri;final boolean copySaved=copy;
                runOnUiThread(()->{if(copySaved)getSystemService(ClipboardManager.class).setPrimaryClip(remote(ClipData.newUri(getContentResolver(),"ClipBridge phone file",saved)));toast(copySaved?"Saved to Downloads/ClipBridge and copied.":"Saved to Downloads/ClipBridge.");});
                return true;
            }catch(Exception e){if(uri!=null)try{getContentResolver().delete(uri,null,null);}catch(Exception ignored){}toast("Could not save this file. Free storage space and try again.");return false;}
            finally{clear();}
        }
        @JavascriptInterface public void copyText(String text){if(text!=null&&text.length()<=4096)runOnUiThread(()->getSystemService(ClipboardManager.class).setPrimaryClip(remote(ClipData.newPlainText("ClipBridge",text))));}
    }
}
