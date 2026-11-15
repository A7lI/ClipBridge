package app.clipbridge;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;

public class ImageProvider extends ContentProvider {
    @Override public boolean onCreate(){return true;}
    private File image(Uri uri) throws FileNotFoundException {
        String name=uri.getLastPathSegment();
        if(name==null || !name.matches("[a-f0-9-]{36}\\.png"))throw new FileNotFoundException();
        File file=new File(getContext().getCacheDir(),name);
        if(!file.isFile())throw new FileNotFoundException(); return file;
    }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
        if(!"r".equals(mode))throw new FileNotFoundException();
        return ParcelFileDescriptor.open(image(uri),ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public String getType(Uri uri){return "image/png";}
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] selectionArgs,String sortOrder){
        try {
            File file=image(uri); String[] columns=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;
            MatrixCursor c=new MatrixCursor(columns); Object[] row=new Object[columns.length];
            for(int i=0;i<columns.length;i++)row[i]=columns[i].equals(OpenableColumns.DISPLAY_NAME)?file.getName():columns[i].equals(OpenableColumns.SIZE)?file.length():null;
            c.addRow(row);return c;
        }catch(Exception e){return null;}
    }
    @Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
    @Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
    @Override public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
