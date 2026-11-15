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
        ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setPadding(Ui.dp(this,16),Ui.dp(this,20),Ui.dp(this,16),Ui.dp(this,20));root.setBackgroundColor(MainActivity.BG);scroll.addView(root);
        TextView title=new TextView(this);title.setText("Received files");title.setTextSize(23);title.setTextColor(MainActivity.FG);root.addView(title);
        TextView note=new TextView(this);note.setText("Downloads / ClipBridge");note.setTextColor(MainActivity.MUTED);root.addView(note);
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
        if(files.isEmpty()&&downloaded==0){TextView empty=new TextView(this);empty.setText("Your received files will appear here.");empty.setTextColor(MainActivity.FG);root.addView(empty);}
        Ui.action(Ui.row(root),"← Back",()->finish(),false);
        setContentView(scroll);
    }
    private void addFile(LinearLayout root,Uri uri,String filename,long bytes,boolean saved){
        LinearLayout card=Ui.card(root,"");TextView name=Ui.text(this,filename,15,Ui.FG);name.setMaxLines(2);name.setEllipsize(android.text.TextUtils.TruncateAt.END);card.addView(name);card.addView(Ui.text(this,Ui.size(bytes)+(saved?" · Saved":" · Save to keep"),11,Ui.MUTED));
        LinearLayout row=Ui.row(card);
        if(!saved)Ui.action(row,"Save…",()->{saving=uri;try{String type=getContentResolver().getType(uri);startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(type==null?"application/octet-stream":type).putExtra(Intent.EXTRA_TITLE,filename),1);}catch(Exception e){toast("No file destination available.");}},true);
        Ui.action(row,"Copy",()->{getSystemService(ClipboardManager.class).setPrimaryClip(PhoneShareActivity.remote(ClipData.newUri(getContentResolver(),"ClipBridge file",uri)));toast("Copied. Paste in an app that accepts files.");},false);
        Ui.action(row,"Share",()->{Intent send=new Intent(Intent.ACTION_SEND).setType(getContentResolver().getType(uri)).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);send.setClipData(ClipData.newRawUri("File",uri));try{startActivity(Intent.createChooser(send,"Share file"));}catch(Exception e){toast("No app available for this file.");}},false);
    }
    void toast(String value){Toast.makeText(this,value,Toast.LENGTH_LONG).show();}
    @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);if(saving!=null)state.putString("saving",saving.toString());}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==1&&result==RESULT_OK&&data!=null&&saving!=null){Uri source=saving,destination=data.getData();new Thread(()->{try(InputStream in=getContentResolver().openInputStream(source);OutputStream out=getContentResolver().openOutputStream(destination)){if(in==null||out==null)throw new IOException();byte[] buf=new byte[8192];int n;while((n=in.read(buf))!=-1)out.write(buf,0,n);runOnUiThread(()->toast("File saved."));}catch(Exception e){runOnUiThread(()->toast("Could not save file."));}},"ClipBridgeSave").start();}}
}
