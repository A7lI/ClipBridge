package app.clipbridge;

import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;
import java.io.*;
import java.util.*;

public class FileProvider extends ContentProvider {
    @Override public boolean onCreate(){return true;}
    File file(Uri uri)throws FileNotFoundException{
        List<String> parts=uri.getPathSegments();boolean capture=parts.size()==3&&"capture".equals(parts.get(0));if(capture)parts=parts.subList(1,3);
        if(parts.size()!=2||!parts.get(0).matches("[a-f0-9-]{36}")||!parts.get(1).equals(Transfers.safeName(parts.get(1))))throw new FileNotFoundException();
        try{
            File root=new File(getContext().getCacheDir(),capture?"camera":"received").getCanonicalFile();File f=new File(new File(root,parts.get(0)),parts.get(1)).getCanonicalFile();
            if(!f.toPath().startsWith(root.toPath())||!f.isFile())throw new FileNotFoundException();return f;
        }catch(IOException e){throw new FileNotFoundException();}
    }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
        // The camera receives a temporary grant to its pre-created output only.
        boolean capture=uri.getPathSegments().size()==3&&"capture".equals(uri.getPathSegments().get(0));
        if(!"r".equals(mode)&&!(capture&&"camera.jpg".equals(uri.getLastPathSegment())))throw new FileNotFoundException();
        int flags=ParcelFileDescriptor.parseMode(mode);
        return ParcelFileDescriptor.open(file(uri),flags);
    }
    @Override public String getType(Uri uri){String ext=MimeTypeMap.getFileExtensionFromUrl(uri.toString());String type=MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext.toLowerCase(Locale.ROOT));return type==null?"application/octet-stream":type;}
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){
        try{File f=file(uri);String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor result=new MatrixCursor(cols);Object[] row=new Object[cols.length];for(int i=0;i<cols.length;i++)row[i]=cols[i].equals(OpenableColumns.DISPLAY_NAME)?f.getName():cols[i].equals(OpenableColumns.SIZE)?f.length():null;result.addRow(row);return result;}catch(Exception e){return null;}
    }
    @Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
    @Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
    @Override public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
