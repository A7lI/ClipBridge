package app.clipbridge;

import android.Manifest;
import android.content.*;
import android.content.pm.PackageManager;
import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.MediaStore;
import java.util.*;
import java.util.concurrent.*;

/** Watches newly saved screenshot media, never the screen or older gallery items. */
final class ScreenshotWatcher {
    interface Delivery {void send(Uri uri)throws Exception; void error(String message);}
    private final Context context;
    private final Delivery delivery;
    private final ScheduledExecutorService worker=Executors.newSingleThreadScheduledExecutor();
    private final Set<Long> sent=new HashSet<>();
    private volatile boolean active=true;
    private final long started=System.currentTimeMillis()/1000;
    private long baseline;
    private boolean observing=false;
    private final ContentObserver observer=new ContentObserver(new Handler(Looper.getMainLooper())){
        @Override public void onChange(boolean selfChange,Uri uri){schedule();}
    };
    static boolean permitted(Context c){return c.checkSelfPermission(Build.VERSION.SDK_INT>=33?Manifest.permission.READ_MEDIA_IMAGES:Manifest.permission.READ_EXTERNAL_STORAGE)==PackageManager.PERMISSION_GRANTED;}
    static boolean screenshot(String name,String path){String value=(name+"/"+path).toLowerCase(Locale.ROOT);return value.contains("screenshot")||value.contains("screen_shot")||value.contains("screen-shot");}
    ScreenshotWatcher(Context c,Delivery d){
        context=c;delivery=d;
        // Establish a baseline before watching so enabling sync never sends old photos.
        baseline=newest();
        try{context.getContentResolver().registerContentObserver(MediaStore.Images.Media.EXTERNAL_CONTENT_URI,true,observer);observing=true;}catch(SecurityException ignored){}
        worker.scheduleWithFixedDelay(()->scan(),1,2,TimeUnit.SECONDS);
    }
    private long newest(){
        try(Cursor cursor=context.getContentResolver().query(MediaStore.Images.Media.EXTERNAL_CONTENT_URI,new String[]{"_id"},null,null,"_id DESC")){if(cursor!=null&&cursor.moveToFirst())return cursor.getLong(0);}catch(Exception ignored){}return 0;
    }
    private void schedule(){if(active)try{worker.schedule(()->scan(),400,TimeUnit.MILLISECONDS);}catch(RejectedExecutionException ignored){}}
    private void scan(){
        if(!active)return;
        if(!Prefs.enabled(context)||!Prefs.get(context).getBoolean("screenshots",false)||!permitted(context)||!SyncService.connected||SyncService.pcPaused){baseline=Math.max(baseline,newest());return;}
        long since=Math.max(started,Prefs.get(context).getLong("screenshots_since",started));
        try(Cursor cursor=context.getContentResolver().query(MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                new String[]{"_id","_display_name","relative_path","is_pending","date_added","_size"},"_id > ? AND date_added >= ?",new String[]{""+baseline,""+since},"_id ASC")){
            if(cursor==null)return;
            while(active&&cursor.moveToNext()){
                long id=cursor.getLong(0);if(sent.contains(id)||cursor.getInt(3)!=0||cursor.getLong(5)<=0||!screenshot(cursor.getString(1),cursor.getString(2)))continue;
                // Expire missed captures instead of unexpectedly replacing a later clipboard.
                if(System.currentTimeMillis()/1000-cursor.getLong(4)>30){sent.add(id);continue;}
                if(!Prefs.get(context).getBoolean("screenshots",false)||!Prefs.enabled(context)||!SyncService.connected||SyncService.pcPaused)return;
                Uri uri=ContentUris.withAppendedId(MediaStore.Images.Media.EXTERNAL_CONTENT_URI,id);
                try{delivery.send(uri);sent.add(id);}
                catch(Exception e){sent.add(id);delivery.error("Screenshot not sent · "+e.getMessage());}
            }
            if(sent.size()>256){baseline=Math.max(baseline,Collections.max(sent));sent.clear();}
        }catch(SecurityException denied){delivery.error("Screenshot sync needs full photo access. Share the screenshot to ClipBridge instead.");}
        catch(Exception ignored){} // MediaStore may be temporarily unavailable during capture.
    }
    void close(){active=false;if(observing)context.getContentResolver().unregisterContentObserver(observer);worker.shutdownNow();}
}
