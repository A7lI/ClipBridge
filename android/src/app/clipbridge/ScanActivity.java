package app.clipbridge;

import android.app.Activity;
import android.content.Intent;
import android.hardware.Camera;
import android.graphics.ImageFormat;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;

/** Offline QR decoding: camera frames never leave the phone. */
@SuppressWarnings("deprecation")
public class ScanActivity extends Activity implements SurfaceHolder.Callback {
    private Camera camera;
    private SurfaceView preview;
    private TextView hint;
    private volatile boolean decoding=false,finished=false;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private long lastFrame;
    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setBackgroundColor(MainActivity.BG);root.setPadding(0,32,0,24);
        hint=new TextView(this);hint.setText("Point at a QR code\nText is copied straight to your PC. A ClipBridge code pairs your phone.");hint.setTextColor(MainActivity.FG);hint.setTextSize(17);hint.setPadding(24,24,24,24);root.addView(hint);
        preview=new SurfaceView(this);root.addView(preview,new LinearLayout.LayoutParams(-1,0,1));preview.getHolder().addCallback(this);
        Button cancel=new Button(this);cancel.setText("Cancel");cancel.setOnClickListener(v->finish());root.addView(cancel);setContentView(root);
    }
    @Override public void surfaceCreated(SurfaceHolder holder){open();}
    @Override public void surfaceChanged(SurfaceHolder h,int f,int w,int height){}
    @Override public void surfaceDestroyed(SurfaceHolder h){release();}
    @Override protected void onResume(){super.onResume();if(preview!=null&&preview.getHolder().getSurface().isValid())open();}
    private void open(){
        if(camera!=null||finished)return;
        try{
            int id=0;Camera.CameraInfo info=new Camera.CameraInfo();
            for(int i=0;i<Camera.getNumberOfCameras();i++){Camera.getCameraInfo(i,info);if(info.facing==Camera.CameraInfo.CAMERA_FACING_BACK){id=i;break;}}
            Camera.getCameraInfo(id,info);camera=Camera.open(id);Camera.Parameters p=camera.getParameters();
            Camera.Size best=null;long distance=Long.MAX_VALUE;
            for(Camera.Size size:p.getSupportedPreviewSizes()){long delta=Math.abs((long)size.width*size.height-921600);if(delta<distance){best=size;distance=delta;}}
            if(best!=null)p.setPreviewSize(best.width,best.height);p.setPreviewFormat(ImageFormat.NV21);
            List<String> modes=p.getSupportedFocusModes();if(modes!=null&&modes.contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE))p.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE);
            camera.setParameters(p);int rotation=getWindowManager().getDefaultDisplay().getRotation()*90;
            camera.setDisplayOrientation((info.orientation-rotation+360)%360);camera.setPreviewDisplay(preview.getHolder());
            camera.setPreviewCallback((data,source)->{
                long now=SystemClock.elapsedRealtime();if(decoding||finished||now-lastFrame<200)return;lastFrame=now;decoding=true;
                Camera.Size size=source.getParameters().getPreviewSize();byte[] frame=data.clone();
                worker.execute(()->{
                    try{
                        String text=QrDecoder.decode(frame,size.width,size.height);finished=true;runOnUiThread(()->{release();setResult(RESULT_OK,new Intent().putExtra("text",text));finish();});
                    }catch(Exception ignored){}finally{decoding=false;}
                });
            });camera.startPreview();
        }catch(Exception e){release();hint.setText("Could not open the camera. Allow camera access and close other camera apps, then try again.");}
    }
    private void release(){if(camera!=null){camera.setPreviewCallback(null);camera.stopPreview();camera.release();camera=null;}}
    @Override protected void onPause(){release();super.onPause();}
    @Override protected void onDestroy(){finished=true;worker.shutdownNow();super.onDestroy();}
}
