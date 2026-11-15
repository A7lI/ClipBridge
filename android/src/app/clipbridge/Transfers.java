package app.clipbridge;

import android.content.*;
import android.database.Cursor;
import android.graphics.*;
import android.media.ExifInterface;
import android.net.Uri;
import android.provider.OpenableColumns;
import java.io.*;
import java.util.*;
import org.json.*;

final class Transfers {
    static final int LIMIT=300*1024*1024;
    static final int IMAGE_LIMIT=12*1024*1024;
    static String safeName(String value){
        String name=value==null?"file":value.replaceAll("[\\x00-\\x1f<>:\"/\\\\|?*]","_").replaceAll("[ .]+$","");
        if(name.isEmpty()||name.equals(".")||name.equals(".."))name="file";
        if(name.matches("(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\\..*)?$"))name="_"+name;
        if(name.length()>180){int dot=name.lastIndexOf('.');String ext=dot>0&&name.length()-dot<20?name.substring(dot):"";name=name.substring(0,160)+ext;}
        return name;
    }
    static String name(Context c,Uri uri){
        try(Cursor cursor=c.getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
            if(cursor!=null&&cursor.moveToFirst())return safeName(cursor.getString(0));
        }catch(Exception ignored){}
        return safeName(uri.getLastPathSegment());
    }
    static JSONObject files(Context c,List<Uri> uris)throws Exception{
        if(uris.isEmpty()||uris.size()>20)throw new Exception("Select 1–20 files.");
        JSONArray files=new JSONArray();int total=0;
        for(Uri uri:uris){
            if(!"content".equals(uri.getScheme()))throw new Exception("Choose files through the Android file picker or Share menu.");
            files.put(new JSONObject().put("name",name(c,uri)).put("uri",uri.toString()));
        }
        return new JSONObject().put("kind","files").put("files",files);
    }
    static JSONObject image(Context c,Uri uri)throws Exception{
        byte[] bytes;try(InputStream in=c.getContentResolver().openInputStream(uri)){if(in==null)throw new Exception("Photo unavailable.");bytes=Client.read(in,32*1024*1024);}
        BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(bytes,0,bytes.length,options);
        if(options.outWidth<=0||options.outHeight<=0)throw new Exception("This image format cannot be copied.");
        options.inJustDecodeBounds=false;options.inSampleSize=1;
        while((long)(options.outWidth/options.inSampleSize)*(options.outHeight/options.inSampleSize)>24000000)options.inSampleSize*=2;
        Bitmap image=BitmapFactory.decodeByteArray(bytes,0,bytes.length,options);if(image==null)throw new Exception("Could not decode photo.");
        try{
            int orientation=new ExifInterface(new ByteArrayInputStream(bytes)).getAttributeInt(ExifInterface.TAG_ORIENTATION,1);
            Matrix matrix=new Matrix();
            switch(orientation){case 2:matrix.setScale(-1,1);break;case 3:matrix.setRotate(180);break;case 4:matrix.setScale(1,-1);break;case 5:matrix.setRotate(90);matrix.postScale(-1,1);break;case 6:matrix.setRotate(90);break;case 7:matrix.setRotate(270);matrix.postScale(-1,1);break;case 8:matrix.setRotate(270);break;}
            if(!matrix.isIdentity()){Bitmap rotated=Bitmap.createBitmap(image,0,0,image.getWidth(),image.getHeight(),matrix,true);if(rotated!=image)image.recycle();image=rotated;}
            ByteArrayOutputStream out=new ByteArrayOutputStream();image.compress(Bitmap.CompressFormat.PNG,100,out);
            if(out.size()>IMAGE_LIMIT)throw new Exception("PNG exceeds 12 MB. Send it using Send files instead.");
            return new JSONObject().put("kind","image").put("data",Client.b64(out.toByteArray()));
        }finally{image.recycle();}
    }
    static void send(Context c,JSONObject item)throws Exception{
        if(!Prefs.paired(c))throw new Exception("Pair with your PC first.");
        try{if("files".equals(item.optString("kind")))sendFiles(c,item);else Client.request(c,"/v1/clipboard",new JSONObject().put("item",item));}
        catch(java.io.IOException e){
            // A lost response can already have applied the item. Do not retry uploads.
            Client.rediscover(c);throw new Exception("Not delivered or not confirmed. Check the PC connection and try again.");
        }
    }
    static int copy(InputStream in,OutputStream out,int remaining)throws Exception{
        byte[] buffer=new byte[192*1024];int count=0,n;
        while((n=in.read(buffer))!=-1){if(n>remaining-count)throw new Exception("Files exceed 300 MB in total.");out.write(buffer,0,n);count+=n;}
        return count;
    }
    static InputStream openEntry(Context c,JSONObject entry)throws Exception{
        if(entry.has("cached")){
            String name=entry.getString("cached");if(!name.matches("cb-[a-f0-9-]+"))throw new Exception("Invalid cache file.");
            return new FileInputStream(new File(c.getCacheDir(),name));
        }
        return new ByteArrayInputStream(Client.unb64(entry.getString("data")));
    }
    static void sendFiles(Context c,JSONObject item)throws Exception{
        JSONArray files=item.getJSONArray("files"),names=new JSONArray(),sizes=new JSONArray();
        for(int i=0;i<files.length();i++)names.put(new JSONObject().put("name",files.getJSONObject(i).getString("name")));
        String id=Client.request(c,"/v1/files/begin",new JSONObject().put("files",names)).getString("id");
        boolean committed=false;int total=0;
        try{
            for(int i=0;i<files.length();i++){
                JSONObject entry=files.getJSONObject(i);int offset=0;
                try(InputStream in=entry.has("uri")?c.getContentResolver().openInputStream(Uri.parse(entry.getString("uri"))):openEntry(c,entry)){
                    if(in==null)throw new IOException("File unavailable.");
                    byte[] buffer=new byte[192*1024];int n;
                    while((n=in.read(buffer))!=-1){
                        if(n==0)continue;
                        total+=n;if(total>LIMIT)throw new Exception("Files exceed 300 MB in total.");
                        Client.request(c,"/v1/files/put",new JSONObject().put("id",id).put("index",i).put("offset",offset).put("data",Client.b64(Arrays.copyOf(buffer,n))));offset+=n;
                    }
                }
                sizes.put(offset);
            }
            Client.request(c,"/v1/files/commit",new JSONObject().put("id",id).put("sizes",sizes));committed=true;
        }finally{if(!committed)try{Client.request(c,"/v1/files/cancel",new JSONObject().put("id",id));}catch(Exception ignored){}}
    }
    static JSONObject receive(Context c,JSONObject item)throws Exception{
        if(item==null||!item.has("chunk_id"))return item;
        JSONArray files=item.getJSONArray("files"),result=new JSONArray();ArrayList<File> created=new ArrayList<>();long total=0;
        try{
            if(files.length()<1||files.length()>20)throw new Exception("Invalid file count.");
            for(int i=0;i<files.length();i++){
                JSONObject entry=files.getJSONObject(i);long size=entry.getLong("size");total+=size;
                if(size<0||total>LIMIT)throw new Exception("Files exceed 300 MB in total.");
                File file=new File(c.getCacheDir(),"cb-"+UUID.randomUUID());created.add(file);
                try(OutputStream out=new FileOutputStream(file)){
                    for(int offset=0;offset<size;){
                        JSONObject reply=Client.request(c,"/v1/files/get",new JSONObject().put("id",item.getString("chunk_id")).put("index",i).put("offset",offset));
                        byte[] bytes=Client.unb64(reply.getString("data"));
                        if(bytes.length!=Math.min(192*1024,size-offset))throw new IOException("Incomplete file chunk.");
                        out.write(bytes);offset+=bytes.length;
                    }
                }
                result.put(new JSONObject().put("name",safeName(entry.getString("name"))).put("cached",file.getName()));
            }
            return new JSONObject().put("kind","files").put("files",result);
        }catch(Exception e){for(File f:created)f.delete();throw e;}
    }
    static void cleanup(Context c,JSONObject item){
        if(item==null||!"files".equals(item.optString("kind")))return;
        JSONArray files=item.optJSONArray("files");if(files==null)return;
        for(int i=0;i<files.length();i++){String name=files.optJSONObject(i).optString("cached");if(name.matches("cb-[a-f0-9-]+"))new File(c.getCacheDir(),name).delete();}
    }
    static ClipData localClip(Context c,JSONObject item)throws Exception{
        String kind=item.getString("kind");ClipData clip;
        if(kind.equals("text"))clip=ClipData.newPlainText("ClipBridge",item.getString("text"));
        else if(kind.equals("image")){
            File file=new File(c.getCacheDir(),UUID.randomUUID()+".png");byte[] bytes=Client.unb64(item.getString("data"));if(bytes.length>IMAGE_LIMIT)throw new Exception("Photo too large.");
            try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}
            clip=ClipData.newUri(c.getContentResolver(),"ClipBridge photo",Uri.parse("content://app.clipbridge.images/"+file.getName()));
            File[] old=c.getCacheDir().listFiles();if(old!=null)for(File previous:old)if(previous.getName().endsWith(".png")&&System.currentTimeMillis()-previous.lastModified()>86400000)previous.delete();
        }else{
            JSONArray files=item.getJSONArray("files");if(files.length()<1||files.length()>20)throw new Exception("Invalid file count.");
            File root=new File(c.getCacheDir(),"received");root.mkdirs();clip=null;int total=0;
            for(int i=0;i<files.length();i++){
                JSONObject entry=files.getJSONObject(i);
                File folder=new File(root,UUID.randomUUID().toString());folder.mkdirs();File file=new File(folder,safeName(entry.getString("name")));
                if(entry.has("cached")){
                    File cached=new File(c.getCacheDir(),entry.getString("cached"));
                    long size=cached.length();if(size>LIMIT-total)throw new Exception("Files exceed 300 MB in total.");
                    if(!cached.renameTo(file))throw new IOException("Could not save received file.");total+=(int)size;
                }else try(InputStream in=openEntry(c,entry);FileOutputStream out=new FileOutputStream(file)){total+=copy(in,out,LIMIT-total);}
                Uri uri=Uri.parse("content://app.clipbridge.files/"+folder.getName()+"/"+Uri.encode(file.getName()));
                if(clip==null)clip=ClipData.newUri(c.getContentResolver(),"ClipBridge files",uri);else clip.addItem(new ClipData.Item(uri));
            }
        }
        android.os.PersistableBundle origin=new android.os.PersistableBundle();origin.putBoolean("app.clipbridge.remote",true);clip.getDescription().setExtras(origin);
        return clip;
    }
}
