package app.clipbridge;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.webkit.MimeTypeMap;
import java.io.*;
import java.util.*;
import org.json.*;

/** Save explicit PC file deliveries in shared Downloads without a storage permission. */
final class Downloads {
    static final String FOLDER=Environment.DIRECTORY_DOWNLOADS+"/ClipBridge/";
    static void save(Context context,JSONObject transfer)throws Exception{
        String id=transfer.getString("id");if(!id.matches("[a-f0-9-]{36}"))throw new Exception("Invalid transfer ID.");
        if(id.equals(Prefs.get(context).getString("last_saved_transfer","")))return;
        JSONObject item=transfer.getJSONObject("item");if(!"files".equals(item.optString("kind")))throw new Exception("Expected files.");
        JSONArray files=item.getJSONArray("files");if(files.length()<1||files.length()>20)throw new Exception("Select 1–20 files.");
        ContentResolver resolver=context.getContentResolver();ArrayList<Uri> created=new ArrayList<>();int total=0;
        try{
            for(int i=0;i<files.length();i++){
                JSONObject entry=files.getJSONObject(i);String name=Transfers.safeName(entry.getString("name"));
                
                int dot=name.lastIndexOf('.');String type=MimeTypeMap.getSingleton().getMimeTypeFromExtension(dot<0?"":name.substring(dot+1).toLowerCase(Locale.ROOT));
                ContentValues values=new ContentValues();values.put(MediaStore.Downloads.DISPLAY_NAME,name);values.put(MediaStore.Downloads.MIME_TYPE,type==null?"application/octet-stream":type);
                values.put(MediaStore.Downloads.RELATIVE_PATH,FOLDER);values.put(MediaStore.Downloads.IS_PENDING,1);
                Uri uri=resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);if(uri==null)throw new IOException("Could not create file in Downloads.");created.add(uri);
                try(OutputStream out=resolver.openOutputStream(uri,"w")){if(out==null)throw new IOException("Could not write file.");try(InputStream in=Transfers.openEntry(context,entry)){total+=Transfers.copy(in,out,Transfers.LIMIT-total);}}
            }
            for(Uri uri:created){ContentValues ready=new ContentValues();ready.put(MediaStore.Downloads.IS_PENDING,0);if(resolver.update(uri,ready,null,null)!=1)throw new IOException("Could not finish saving files.");}
            if(!Prefs.get(context).edit().putString("last_saved_transfer",id).commit())throw new IOException("Could not record delivery.");
        }catch(Exception error){for(Uri uri:created)try{resolver.delete(uri,null,null);}catch(Exception ignored){}throw error;}
        PendingIntent open=PendingIntent.getActivity(context,5,new Intent(context,FilesActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(context,"sync").setSmallIcon(R.drawable.ic_bridge).setContentTitle("Files received from PC")
            .setContentText(files.length()+" file(s) saved to Downloads/ClipBridge").setContentIntent(open).setAutoCancel(true).build();
        try{context.getSystemService(NotificationManager.class).notify(5,notification);}catch(SecurityException ignored){}
    }
}
