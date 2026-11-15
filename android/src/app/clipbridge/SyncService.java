package app.clipbridge;

import android.app.*;
import android.content.*;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.concurrent.*;
import org.json.JSONObject;

public class SyncService extends Service {
    public static volatile String status="Sync is off";
    public static volatile boolean connected=false, pcPaused=true, voiceReady=false;
    public static volatile boolean running=false;
    private volatile boolean alive=false;
    private ClipboardManager clipboard;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService outgoing=Executors.newSingleThreadExecutor();
    private Thread poller;
    private ScreenshotWatcher screenshots;
    private volatile String lastSignature="";
    private long revision=-1;
    private volatile long clipboardGeneration=0;
    private final ClipboardManager.OnPrimaryClipChangedListener listener=()->capture();

    static String fingerprint(JSONObject item)throws Exception{
        String kind=item.getString("kind");
        byte[] raw=kind.equals("text")?item.getString("text").getBytes("UTF-8"):kind.equals("files")?item.getJSONArray("files").toString().getBytes("UTF-8"):Client.unb64(item.getString("data"));
        MessageDigest digest=MessageDigest.getInstance("SHA-256");digest.update(item.getString("kind").getBytes("UTF-8"));
        return Client.b64(digest.digest(raw));
    }
    @Override public void onCreate(){
        super.onCreate(); clipboard=getSystemService(ClipboardManager.class);
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("sync","Clipboard connection",NotificationManager.IMPORTANCE_LOW));
    }
    private Notification notification(){
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,SyncService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this,"sync").setSmallIcon(R.drawable.ic_bridge).setContentTitle("ClipBridge")
            .setContentText(status).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(null,"Stop",stop).build()).build();
    }
    private void update(String text){status=text;getSystemService(NotificationManager.class).notify(1,notification());}
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent!=null && "stop".equals(intent.getAction())){Prefs.get(this).edit().putBoolean("enabled",false).apply();stopSelf();return START_NOT_STICKY;}
        if(!Prefs.enabled(this)||!Prefs.paired(this)){stopSelf();return START_NOT_STICKY;}
        status="Connecting to your PC…";startForeground(1,notification());running=true;
        if(!alive){alive=true;clipboard.addPrimaryClipChangedListener(listener);poller=new Thread(()->poll(),"ClipBridgePoll");poller.start();
            screenshots=new ScreenshotWatcher(this,new ScreenshotWatcher.Delivery(){
                public void send(Uri uri)throws Exception{
                    JSONObject item=Transfers.image(SyncService.this,uri);
                    if(!alive||!Prefs.get(SyncService.this).getBoolean("screenshots",false)||pcPaused)return;
                    Transfers.send(SyncService.this,item);
                    main.post(()->{if(alive){apply(item);update("Screenshot copied to PC · paste with Ctrl+V");}});
                }
                public void error(String message){if(alive)update(message);}
            });
        }
        return START_STICKY;
    }
    private void poll(){
        long lastDiscovery=-15000;
        while(alive){
            try{
                long expected=clipboardGeneration;
                JSONObject response=Client.request(this,"/v1/poll",new JSONObject().put("after",revision).put("file_delivery",1).put("file_chunks",1));
                if(!alive)break;
                connected=true;pcPaused=response.getBoolean("paused");voiceReady=response.optBoolean("voice");revision=response.getLong("revision");
                JSONObject transfer=response.optJSONObject("transfer");
                if(transfer!=null&&!pcPaused){
                    JSONObject ack=new JSONObject().put("id",transfer.getString("id"));
                    try{transfer.put("item",Transfers.receive(this,transfer.getJSONObject("item")));Downloads.save(this,transfer);ack.put("saved",true);}
                    catch(Exception e){ack.put("saved",false).put("error",e.getMessage()==null?"Could not save files in Downloads.":e.getMessage());}
                    Transfers.cleanup(this,transfer.optJSONObject("item"));
                    Client.request(this,"/v1/files/ack",ack);
                }
                JSONObject item=Transfers.receive(this,response.optJSONObject("item"));
                if(item!=null && !pcPaused) {
                    // Do not overwrite a newer local copy made while this poll was in flight.
                    CountDownLatch applied=new CountDownLatch(1);
                    main.post(()->{try{if(alive){if(expected==clipboardGeneration)apply(item);else if("files".equals(item.optString("kind")))Transfers.localClip(this,item);Transfers.cleanup(this,item);}}catch(Exception e){update("Could not save received files");}finally{applied.countDown();}});
                    applied.await(8,TimeUnit.SECONDS);
                }
                update(pcPaused?"Connected · paused on PC":"Connected · text, photos + files");
            }catch(Exception e){
                connected=false;voiceReady=false;if(!alive)break;update("Reconnecting to your paired PC…");
                long now=SystemClock.elapsedRealtime();
                if(now-lastDiscovery>=15000){lastDiscovery=now;if(Client.rediscover(this)){revision=-1;continue;}}
                try{Thread.sleep(2500);}catch(InterruptedException x){break;}
            }
        }
    }
    private void apply(JSONObject item){
        try{
            String sig=fingerprint(item);if(sig.equals(lastSignature))return;
            ClipData clip=Transfers.localClip(this,item);
            lastSignature=sig;clipboard.setPrimaryClip(clip);
        }catch(Exception e){update("Could not place received item on clipboard");}
    }
    private void capture(){
        clipboardGeneration++;
        if(!alive||!connected||pcPaused||!Prefs.isKeyboard(this))return;
        final ClipData clip;
        try {clip=clipboard.getPrimaryClip();}catch(SecurityException denied){return;}
        if(clip==null||clip.getItemCount()==0)return;
        // Honor Android's explicit sensitive-clipboard flag. Password-manager
        // autofill never enters this listener unless the user actually copies.
        PersistableBundle extras=clip.getDescription().getExtras();
        if(extras!=null&&extras.getBoolean("app.clipbridge.remote",false))return;
        if(extras!=null&&extras.getBoolean("android.content.extra.IS_SENSITIVE",false)){update("Sensitive clipboard item skipped");return;}
        outgoing.execute(()->{
            try{
                if(!alive||pcPaused||!Prefs.isKeyboard(this))return;
                JSONObject item=new JSONObject();ClipData.Item first=clip.getItemAt(0);Uri uri=first.getUri();
                if(uri!=null){
                    if("app.clipbridge.images".equals(uri.getAuthority())||"app.clipbridge.files".equals(uri.getAuthority()))return;
                    String type=getContentResolver().getType(uri);
                    if(clip.getItemCount()==1&&type!=null&&type.startsWith("image/"))item=Transfers.image(this,uri);
                    else{java.util.ArrayList<Uri> uris=new java.util.ArrayList<>();for(int i=0;i<clip.getItemCount();i++){Uri u=clip.getItemAt(i).getUri();if(u==null)return;uris.add(u);}item=Transfers.files(this,uris);}
                }else{
                    CharSequence text=first.getText();if(text==null)return;
                    if(text.toString().getBytes("UTF-8").length>1024*1024)throw new Exception("Text exceeds 1 MB");
                    item.put("kind","text").put("text",text.toString());
                }
                String sig=fingerprint(item);synchronized(this){if(sig.equals(lastSignature))return;}
                if(!alive||pcPaused)return;
                Transfers.send(this,item);
                lastSignature=sig;
            }catch(Exception e){update("Clipboard not sent · "+(e.getMessage()==null?"copy again":e.getMessage()));}
        });
    }
    @Override public void onDestroy(){alive=false;running=false;connected=false;voiceReady=false;if(screenshots!=null)screenshots.close();clipboard.removePrimaryClipChangedListener(listener);outgoing.shutdownNow();if(poller!=null)poller.interrupt();status="Sync is off";super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
