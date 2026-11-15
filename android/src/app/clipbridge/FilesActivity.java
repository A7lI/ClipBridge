package app.clipbridge;

import android.app.Activity;
import android.content.*;
import android.net.Uri;
import android.os.Bundle;
import android.database.Cursor;
import android.provider.MediaStore;
import android.widget.*;
import java.io.*;
import java.util.*;

public class FilesActivity extends Activity {
    private Uri saving;
    @Override public void onCreate(Bundle state){
        super.onCreate(state);if(state!=null){String value=state.getString("saving");if(value!=null)saving=Uri.parse(value);}
        ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setPadding(24,48,24,40);root.setBackgroundColor(MainActivity.BG);scroll.addView(root);
        TextView title=new TextView(this);title.setText("Received files");title.setTextSize(26);title.setTextColor(MainActivity.FG);root.addView(title);
        TextView note=new TextView(this);note.setText("Files from PCs and phone-to-phone sharing are saved in Downloads/ClipBridge. Older clipboard files are cached; use Save to keep those.");note.setTextColor(MainActivity.MUTED);root.addView(note);
        int downloaded=0;
        try(Cursor cursor=getContentResolver().query(MediaStore.Downloads.EXTERNAL_CONTENT_URI,new String[]{"_id","_display_name","_size"},"relative_path = ? AND is_pending = 0",new String[]{Downloads.FOLDER},"date_added DESC")){
            if(cursor!=null)while(cursor.moveToNext()){
                downloaded++;addFile(root,ContentUris.withAppendedId(MediaStore.Downloads.EXTERNAL_CONTENT_URI,cursor.getLong(0)),cursor.getString(1),cursor.getLong(2),true);
            }
        }catch(Exception ignored){TextView hint=new TextView(this);hint.setText("Open your phone’s Files app → Downloads → ClipBridge to browse saved files.");hint.setTextColor(MainActivity.MUTED);root.addView(hint);}
        ArrayList<File> files=new ArrayList<>();File[] folders=new File(getCacheDir(),"received").listFiles();if(folders!=null)for(File folder:folders){File[] children=folder.listFiles();if(children!=null)for(File f:children)if(f.isFile())files.add(f);}
        files.sort((a,b)->Long.compare(b.lastModified(),a.lastModified()));
        for(File f:files){
            Uri uri=Uri.parse("content://app.clipbridge.files/"+f.getParentFile().getName()+"/"+Uri.encode(f.getName()));
            addFile(root,uri,f.getName(),f.length(),false);
        }
        if(files.isEmpty()&&downloaded==0){TextView empty=new TextView(this);empty.setText("No received files yet. On your PC, right-click a file and choose Share to My Phone, or use Send files in ClipBridge.");empty.setTextColor(MainActivity.FG);root.addView(empty);}
        setContentView(scroll);
    }
    private void addFile(LinearLayout root,Uri uri,String filename,long bytes,boolean saved){
        TextView name=new TextView(this);name.setText(filename+" · "+bytes+" bytes"+(saved?" · Downloads":" · cached"));name.setTextColor(MainActivity.FG);name.setPadding(0,24,0,4);root.addView(name);
        LinearLayout row=new LinearLayout(this);root.addView(row);
        if(!saved){Button save=new Button(this);save.setText("Save…");row.addView(save);save.setOnClickListener(v->{saving=uri;try{startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(getContentResolver().getType(uri)).putExtra(Intent.EXTRA_TITLE,filename),1);}catch(Exception e){toast("No file destination available.");}});}
        Button share=new Button(this);share.setText("Share");row.addView(share);share.setOnClickListener(v->{Intent send=new Intent(Intent.ACTION_SEND).setType(getContentResolver().getType(uri)).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);send.setClipData(ClipData.newRawUri("File",uri));try{startActivity(Intent.createChooser(send,"Share file"));}catch(Exception e){toast("No app available for this file.");}});
    }
    void toast(String value){Toast.makeText(this,value,Toast.LENGTH_LONG).show();}
    @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);if(saving!=null)state.putString("saving",saving.toString());}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==1&&result==RESULT_OK&&data!=null&&saving!=null){Uri source=saving,destination=data.getData();new Thread(()->{try(InputStream in=getContentResolver().openInputStream(source);OutputStream out=getContentResolver().openOutputStream(destination)){if(in==null||out==null)throw new IOException();byte[] buf=new byte[8192];int n;while((n=in.read(buf))!=-1)out.write(buf,0,n);runOnUiThread(()->toast("File saved."));}catch(Exception e){runOnUiThread(()->toast("Could not save file."));}},"ClipBridgeSave").start();}}
}
